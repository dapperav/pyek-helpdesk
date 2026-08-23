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
 * Placement is "after the text, in the order added" rather than at the caret:
 * a textarea has no way to anchor a node to a moving cursor, and an offset
 * remembered at paste time drifts silently as the reply is edited. Agents who
 * need an image mid-paragraph have the full editor one click away.
 */
import { __ } from "@/translation";
import { removeAttachmentFromServer, uploadFunction } from "@/utils";
import { toast } from "frappe-ui";
import { computed, ref } from "vue";

const IMAGE_MIME = /^image\//i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg|avif|heic|heif)$/i;

/** Widest an inline image is allowed to render at in the mail body. */
const MAX_EMAIL_WIDTH = 640;

export interface InlineImage {
  /** `File` docname — what the delete call needs. */
  name: string;
  file_url: string;
  file_name: string;
  /** Natural width in px, capped for the email; null while unknown. */
  width: number | null;
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
 * Read an image's natural width so the mail can carry a `width` attribute.
 * Outlook desktop ignores `max-width` on images, so a 3000px screenshot would
 * blow the layout out without it. Resolves to null rather than rejecting — a
 * missing width is cosmetic, a failed send is not.
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
 */
export function useInlineReplyImages(
  ticketId: string,
  onOther: (file: any) => void
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
    const width = await probeWidth(uploaded.file_url);
    images.value.push({
      name: String(uploaded.name ?? ""),
      file_url: uploaded.file_url,
      file_name: uploaded.file_name || uploaded.file_url,
      width: width ? Math.min(width, MAX_EMAIL_WIDTH) : null,
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
          const width = await probeWidth(uploaded.file_url);
          images.value.push({
            name: String(uploaded.name ?? ""),
            file_url: uploaded.file_url,
            file_name: uploaded.file_name || file.name,
            width: width ? Math.min(width, MAX_EMAIL_WIDTH) : null,
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
        const width = i.width ? ` width="${i.width}"` : "";
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
    if (!event.dataTransfer?.types?.includes("Files")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    dragging.value = true;
  }

  function onDragLeave(event: DragEvent) {
    // Ignore the leave events fired while crossing the bar's own children.
    const next = event.relatedTarget as Node | null;
    if (next && (event.currentTarget as Node)?.contains(next)) return;
    dragging.value = false;
  }

  function onDrop(event: DragEvent) {
    dragging.value = false;
    const files = collectFiles(event.dataTransfer);
    if (!files.length) return;
    event.preventDefault();
    void addFiles(files);
  }

  return {
    images,
    busy,
    hasImages,
    dragging,
    addFiles,
    addUploaded,
    remove,
    reset,
    html,
    onPaste,
    onDragOver,
    onDragLeave,
    onDrop,
  };
}
