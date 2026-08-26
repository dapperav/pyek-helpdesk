/**
 * Inline images for the quick reply bars (desktop + phone).
 *
 * Mark, 2026-08-23: "if i want to put a screen shot in the reply it wont let
 * me. i would prefer to be able to drag the image into the text box for it to
 * go inline. or at least be able to copy an image and paste it in."
 *
 * The full email composer already does this — it is a tiptap editor and
 * frappe-ui's RichTextKit ships the image + mediaDrop extensions, so a paste or
 * a drop uploads and inserts an <img> at the caret. The quick bars can't: both
 * are a plain <textarea> (deliberately — the hand-rolled @mention picker and
 * the draft persistence both work on a string), and a textarea silently
 * swallows an image paste and lets the browser navigate away on a drop.
 *
 * So the bars keep their textarea and grow a second lane beside it: images
 * pasted, dropped, or picked are uploaded straight away and held here, shown as
 * removable thumbnails, and appended to the outgoing HTML as real <img> tags
 * after the typed text. `HD Ticket.parse_content` rewrites every `src` into an
 * `embed` attribute, and Frappe's `replace_filename_with_cid` turns those into
 * CID attachments — private files included — so the requester sees the
 * screenshot in the mail body rather than a download link.
 *
 * Each image carries a size step (S/M/L/Full, see emailImageSize.ts) that the
 * chip on its thumbnail cycles through, and that becomes the `width` attribute
 * on the outgoing tag. Width is the only sizing lever an email has — Outlook
 * renders through Word, which ignores `max-width` on images — so an unsized
 * screenshot goes out at its natural 1400-plus pixels and wrecks the reading
 * pane. Default is M (640px); the chip is how an agent overrides it.
 *
 * Placement is "after the text, in the order added" rather than at the caret:
 * a textarea has no way to anchor a node to a moving cursor, and an offset
 * remembered at paste time drifts silently as the reply is edited. Agents who
 * need an image mid-paragraph have the full editor one click away.
 */
import { __ } from "@/translation";
import { removeAttachmentFromServer, uploadFunction } from "@/utils";
import {
  DEFAULT_SIZE,
  emailWidth,
  isResizable,
  nextSize,
  sizeLabel,
  type SizeKey,
} from "@/emailImageSize";
import { toast } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const IMAGE_MIME = /^image\//i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg|avif|heic|heif)$/i;

export interface InlineImage {
  /** `File` docname — what the delete call needs. */
  name: string;
  file_url: string;
  file_name: string;
  /** Width as uploaded, in px; null when the probe failed. */
  natural: number | null;
  /** Which size step the agent picked. See emailImageSize.ts. */
  size: SizeKey;
}

/** Is this uploaded `File` doc an image? Works off the name, not the MIME. */
export function isImageFile(file: { file_name?: string; file_url?: string }) {
  return IMAGE_EXT.test(file?.file_name || file?.file_url || "");
}

function escapeAttr(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Read an image's natural width. Everything downstream needs it: the mail wants
 * a `width` attribute (Outlook ignores `max-width` on images, so a 3000px
 * screenshot would blow the layout out without one) and the size chip refuses
 * to offer a step wider than the picture actually is. Resolves to null rather
 * than rejecting — a missing width is cosmetic, a failed send is not.
 */
function probeWidth(url: string): Promise<number | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img.naturalWidth || null);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

/**
 * @param ticketId  Ticket the uploads attach to.
 * @param onOther   Non-image files fall through to the bar's normal attachment
 *                  list (a PDF is still a PDF).
 * @param isActive  Whether the bar is the visible reply surface. The
 *                  page-wide drop fallback stands down when a full editor has
 *                  taken over, so a stray drop can't land in a hidden bar.
 */
export function useInlineReplyImages(
  ticketId: string,
  onOther: (file: any) => void,
  isActive: () => boolean = () => true
) {
  const images = ref<InlineImage[]>([]);
  const uploading = ref(0);
  const dragging = ref(false);

  const busy = computed(() => uploading.value > 0);
  const hasImages = computed(() => images.value.length > 0);

  /**
   * Adopt a file the bar's own picker already uploaded. Same list, same
   * thumbnail, so the paperclip and a paste behave identically for images.
   */
  async function addUploaded(uploaded: any) {
    if (!uploaded?.file_url) return;
    images.value.push({
      name: String(uploaded.name ?? ""),
      file_url: uploaded.file_url,
      file_name: uploaded.file_name || uploaded.file_url,
      natural: await probeWidth(uploaded.file_url),
      size: DEFAULT_SIZE,
    });
  }

  async function addFiles(files: File[]) {
    if (!files.length) return;
    for (const file of files) {
      uploading.value += 1;
      try {
        const uploaded = await uploadFunction(file, "HD Ticket", ticketId);
        if (!uploaded?.file_url) throw new Error("no file_url");
        if (IMAGE_MIME.test(file.type) || isImageFile(uploaded)) {
          images.value.push({
            name: String(uploaded.name ?? ""),
            file_url: uploaded.file_url,
            file_name: uploaded.file_name || file.name,
            natural: await probeWidth(uploaded.file_url),
            size: DEFAULT_SIZE,
          });
        } else {
          onOther(uploaded);
        }
      } catch (e) {
        toast.error(__("Could not upload {0}", file.name));
      } finally {
        uploading.value -= 1;
      }
    }
  }

  async function remove(image: InlineImage) {
    images.value = images.value.filter((i) => i !== image);
    await removeAttachmentFromServer(image.name).catch(() => {});
  }

  /**
   * Step this picture to the next size. A cycle rather than a dropdown: the
   * target is a 56px thumbnail that has to work under a thumb on the phone, and
   * there are only four choices to walk through.
   */
  function resize(image: InlineImage) {
    image.size = nextSize(image.size, image.natural);
  }

  /** What the chip on a thumbnail reads — "M", or "480px" at natural size. */
  function label(image: InlineImage) {
    return sizeLabel(image.size, image.natural);
  }

  /** Whether to show the chip at all — see isResizable. */
  function resizable(image: InlineImage) {
    return isResizable(image.natural);
  }

  /** Drop the local list without touching the server (post-send reset). */
  function reset() {
    images.value = [];
    dragging.value = false;
  }

  /**
   * The images as HTML, ready to append after the typed body. Empty string when
   * there are none, so callers can concatenate unconditionally.
   */
  function html() {
    if (!images.value.length) return "";
    return images.value
      .map((i) => {
        const px = emailWidth(i.size, i.natural);
        const width = px ? ` width="${px}"` : "";
        return (
          `<p><img src="${escapeAttr(i.file_url)}"` +
          ` alt="${escapeAttr(i.file_name)}"${width}` +
          ` style="max-width:100%;height:auto"></p>`
        );
      })
      .join("");
  }

  /** Pull every `File` off a clipboard/drag payload. */
  function collectFiles(data: DataTransfer | null | undefined): File[] {
    const items = data?.items;
    if (!items?.length) return [...(data?.files ?? [])];
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        const file = items[i].getAsFile();
        if (file) files.push(file);
      }
    }
    return files;
  }

  /**
   * Paste handler for the bar's textarea. Claims the event only when the
   * clipboard carries files, so ordinary text pastes are untouched.
   *
   * Some sources put both on the clipboard at once — copying a range out of
   * Excel ships an image of the cells alongside the tab-separated text, and
   * copying an image off a web page can carry its alt text. Cancelling the
   * event kills the browser's text insert too, so the text is handed back to
   * the caller to write at the caret instead of being silently dropped.
   */
  function onPaste(event: ClipboardEvent, insertText?: (text: string) => void) {
    const files = collectFiles(event.clipboardData);
    if (!files.length) return;
    const text = event.clipboardData?.getData("text/plain") ?? "";
    event.preventDefault();
    if (text && insertText) insertText(text);
    void addFiles(files);
  }

  function onDragOver(event: DragEvent) {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    markDragging();
  }

  function onDrop(event: DragEvent) {
    if (dragTimer) clearTimeout(dragTimer);
    dragging.value = false;
    const files = collectFiles(event.dataTransfer);
    if (!files.length) return;
    event.preventDefault();
    void addFiles(files);
  }

  // ── Page-wide fallback ───────────────────────────────────────────────
  // The bar is a small target at the bottom of a tall thread, and a drop that
  // misses it hands the file to the browser, which navigates away from the
  // ticket and takes the half-typed reply with it. Nothing else on the ticket
  // page claims a file drag (checked on prod, 2026-08-23), so `window` is the
  // last stop: anything a real drop zone wanted has already called
  // preventDefault by the time the event bubbles this far, and whatever is
  // left belongs to the reply.
  let dragTimer: ReturnType<typeof setTimeout> | null = null;

  /**
   * `dragover` repeats every ~50-100ms for as long as a drag is live, so an
   * idle timer is a far more reliable "the drag ended" signal than dragleave,
   * which fires on every child boundary crossed.
   */
  function markDragging() {
    dragging.value = true;
    if (dragTimer) clearTimeout(dragTimer);
    dragTimer = setTimeout(() => (dragging.value = false), 250);
  }

  function carriesFiles(event: DragEvent) {
    return !!event.dataTransfer?.types?.includes("Files");
  }

  function windowDragOver(event: DragEvent) {
    if (event.defaultPrevented || !isActive() || !carriesFiles(event)) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    markDragging();
  }

  function windowDrop(event: DragEvent) {
    if (dragTimer) clearTimeout(dragTimer);
    dragging.value = false;
    if (event.defaultPrevented || !isActive()) return;
    const files = collectFiles(event.dataTransfer);
    if (!files.length) return;
    event.preventDefault();
    void addFiles(files);
  }

  onMounted(() => {
    window.addEventListener("dragover", windowDragOver);
    window.addEventListener("drop", windowDrop);
  });
  onBeforeUnmount(() => {
    if (dragTimer) clearTimeout(dragTimer);
    window.removeEventListener("dragover", windowDragOver);
    window.removeEventListener("drop", windowDrop);
  });

  return {
    images,
    busy,
    hasImages,
    dragging,
    addFiles,
    addUploaded,
    remove,
    resize,
    label,
    resizable,
    reset,
    html,
    onPaste,
    onDragOver,
    onDrop,
  };
}
