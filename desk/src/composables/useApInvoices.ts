import { computed } from "vue";
import { dayjs } from "frappe-ui";
import { getMeta } from "@/stores/meta";

/**
 * `ap_invoices` is created by the enricher's ensure_ap_fields() on ITS next deploy,
 * which is a different pipeline from the portal's — so the portal can be live before
 * the field exists. Asking frappe.client.get_value for an unknown fieldname throws,
 * which would take out the whole invoice card, so every caller must gate the request
 * on this. Schema-based for the same reason as useIsAp.
 */
export function useHasApInvoicesField() {
  const { getField } = getMeta("HD Ticket");
  return computed(() => !!getField("ap_invoices"));
}

/**
 * The invoices attached to one AP ticket, each with its OWN Intacct filename.
 *
 * Most AP tickets carry exactly one invoice, and for those the ticket's own fields
 * (pyek_property / ap_invoice_date / ap_vendor / ap_amount) ARE the invoice — that's
 * the case the card has always handled, and the one where a human correction in the
 * sidebar must rename the download straight away.
 *
 * A minority carry several. The enricher reads every attachment but writes only the
 * "primary" one into the scalar fields (ap_amount is the primary's amount, NOT a sum),
 * so those tickets need the per-attachment detail it now records in `ap_invoices`:
 * one JSON element per attachment with its own park/date/vendor/amount. Without it a
 * 4-receipt reimbursement downloads a single PDF stamped with the ticket total.
 *
 * Precedence, deliberately:
 *   1. `ap_invoices` JSON, when present  — the multi-invoice case
 *   2. `ap_invoice_file`                 — legacy single-invoice tickets
 *   3. the largest PDF on the thread     — tickets the enricher never pointed
 *
 * The PRIMARY line always takes its tokens from the live ticket fields rather than
 * from the stored JSON, so Nedra correcting Vendor or Amount still renames that file
 * immediately — the whole point of deriving the name instead of reading back a value
 * the enricher froze at first extraction. Non-primary lines have no editable home on
 * the ticket, so they use their own stored read.
 */

/**
 * Normalise a file reference to a comparable path: no origin, no query string.
 *
 * `ap_invoices` stores "/private/files/x.png" while the email body may carry
 * "https://ap.pyekmail.com/private/files/x.png?foo" for the same file.
 */
export function normalizeFileUrl(value: unknown): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  try {
    const path = raw.startsWith("http") ? new URL(raw).pathname : raw.split("?")[0];
    try {
      return decodeURIComponent(path);
    } catch {
      // A stray % that isn't an escape sequence — compare the raw path instead.
      return path;
    }
  } catch {
    return raw.split("?")[0];
  }
}

function isPdfLine(line: any): boolean {
  return String(line?.file_name || line?.file_url || "")
    .toLowerCase()
    .endsWith(".pdf");
}

/**
 * The file URLs that the thread's own HTML renders as <img> — i.e. the email's
 * furniture rather than its documents.
 *
 * An Outlook signature logo arrives as an ordinary file attachment; the only thing
 * that distinguishes it from a photographed receipt is that the message body embeds
 * it (a `cid:` reference Frappe rewrites to the file URL). That distinction has to
 * be structural, because nothing in the AI's answer separates them: handed the email
 * subject and body as context, it labels the logo with the invoice's own values. On
 * ticket 1205 `image001.png` came back doc_type "Invoice", amount 422.59,
 * readable true — and was then chosen as the primary invoice, so `ap_invoice_file`
 * pointed at a logo instead of the Ferguson PDF (same on 1206 and 0192).
 */
export function inlineAttachmentUrls(communications: any[]): Set<string> {
  const urls = new Set<string>();
  for (const c of communications || []) {
    const html = String(c?.content || "");
    if (!html) continue;
    for (const m of html.matchAll(/<img[^>]+src\s*=\s*["']([^"']+)["']/gi)) {
      const src = m[1];
      if (!src || src.startsWith("data:")) continue;
      const norm = normalizeFileUrl(src);
      if (norm) urls.add(norm);
    }
  }
  return urls;
}

/** Reactive wrapper over inlineAttachmentUrls for the ticket's activities resource. */
export function useInlineAttachmentUrls(activities: () => any) {
  return computed(() =>
    inlineAttachmentUrls(activities()?.data?.communications || [])
  );
}

export interface ApInvoice {
  fileUrl: string;
  fileName: string;
  /** Intacct name: ParkName_InvoiceDate_VendorName_Amount.pdf */
  downloadName: string;
  amount: number | null;
  readable: boolean;
  primary: boolean;
}

/**
 * Vendor token: stripped to A-Z0-9, uppercased, capped at 24. Mirrors the enricher's
 * extract._short() so a hand-typed "Suter Law" and an extracted "SUTERLAW" agree.
 */
function vendorToken(value: unknown): string {
  const tok = String(value ?? "")
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase()
    .slice(0, 24);
  return tok || "VENDOR";
}

/** Same shape and same placeholders as the enricher's _filename(). */
export function intacctName(parts: {
  park?: unknown;
  date?: unknown;
  vendor?: unknown;
  amount?: unknown;
}): string {
  const day = parts.date ? dayjs(parts.date as string) : null;
  const dateTok = day && day.isValid() ? day.format("MMDDYYYY") : "NODATE";
  const n = Number(parts.amount);
  const amtTok =
    parts.amount !== null &&
    parts.amount !== undefined &&
    parts.amount !== "" &&
    !Number.isNaN(n)
      ? n.toFixed(2)
      : "0.00";
  return `${parts.park || "NOPARK"}_${dateTok}_${vendorToken(parts.vendor)}_${amtTok}.pdf`;
}

/**
 * Is this attachment actually a document Nedra would key into Intacct?
 *
 * The enricher records EVERY attachment it tried to read, which is right for fidelity
 * but wrong to show verbatim: AP emails carry signature logos and pasted screenshots,
 * and Claude cheerfully "reads" a Pepsi logo — it comes back `readable: true` with
 * doc_type "Other" and no amount. Listing those as "Invoice 2" and "Invoice 3" under
 * the name NOPARK_NODATE_VENDOR_0.00.pdf would be worse than the single-file behaviour
 * this replaces (real case: ticket 0005, one Cintas PDF plus two junk PNGs).
 *
 * So `readable` is NOT the discriminator. The rule instead:
 *   - a PDF on an AP email is always a candidate document, even if unreadable — an
 *     invoice Claude choked on is exactly the one a human needs to open;
 *   - an image only counts when the AI actually pulled invoice data off it, which is
 *     what separates a photographed receipt or bank slip from a footer logo;
 *   - the attachment the ticket's own fields were read from always counts, whatever
 *     it looks like — the scalars demonstrably came from it.
 *
 * Filtering happens at DISPLAY time, not in the enricher, so the stored data stays
 * complete and this rule can be retuned without re-running (and re-paying for) the AI.
 */
function isLikelyDocument(
  line: any,
  isPointer: boolean,
  inlineUrls: Set<string>
): boolean {
  // Checked BEFORE the pointer rule, and deliberately so. The old rule trusted the
  // pointer absolutely — "the scalars demonstrably came from it" — but the enricher
  // picks the first attachment the AI called an Invoice, and a signature image sorts
  // first, so on a real subset of tickets the pointer IS the logo. An embedded image
  // is never the document Nedra keys into Intacct.
  if (!isPdfLine(line) && inlineUrls.has(normalizeFileUrl(line.file_url))) {
    return false;
  }
  if (isPointer) return true;
  if (isPdfLine(line)) return true;
  const hasAmount =
    line.amount !== null && line.amount !== undefined && line.amount !== "";
  return (
    hasAmount || ["Invoice", "Statement", "Reimbursement"].includes(line.doc_type)
  );
}

/**
 * Make every download name unique.
 *
 * Two attachments on one email can derive the SAME name whenever the tokens they'd
 * differ on are missing — same vendor, same date, and neither amount read, so both
 * land on NOPARK_<date>_<vendor>_0.00.pdf (real case: ticket 0027). Downloading them
 * in sequence then either overwrites the first or leaves the browser to silently
 * suffix "(1)", so one invoice quietly never arrives.
 *
 * Disambiguate with the invoice number the line actually refers to, which is the
 * meaningful identifier when park and amount are blank; fall back to a counter when
 * even that is missing, so the result is unique either way.
 */
function uniquifyNames(rows: ApInvoice[], numbers: (string | null)[]): ApInvoice[] {
  const seen = new Map<string, number>();
  return rows.map((r, i) => {
    const taken = seen.get(r.downloadName) || 0;
    seen.set(r.downloadName, taken + 1);
    if (!taken) return r;
    const stem = r.downloadName.replace(/\.pdf$/i, "");
    const invNo = String(numbers[i] ?? "").trim();
    const suffix = invNo ? `_${invNo}` : `_${taken + 1}`;
    let name = `${stem}${suffix}.pdf`;
    // The invoice number can itself repeat across lines — keep counting until free.
    let n = taken;
    while (seen.has(name)) name = `${stem}${suffix}_${++n}.pdf`;
    seen.set(name, 1);
    return { ...r, downloadName: name };
  });
}

function parseLines(raw: unknown): any[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const v = JSON.parse(String(raw));
    return Array.isArray(v) ? v : [];
  } catch {
    // A malformed value must degrade to the single-invoice path, never blank the card.
    return [];
  }
}

export function useApInvoices(
  ticket: () => Record<string, any> | null | undefined,
  extra: () => Record<string, any> | null | undefined,
  threadFallback?: () => { url: string; name: string } | null,
  /** Files the thread renders inline — signature logos, not documents. */
  inlineUrls?: () => Set<string> | null | undefined
) {
  return computed<ApInvoice[]>(() => {
    const t = ticket() || {};
    const x = extra() || {};

    // Tokens from the live doc — used for the primary line and the single-invoice case.
    const live = {
      park: t.pyek_property,
      date: t.ap_invoice_date,
      vendor: t.ap_vendor,
      amount: t.ap_amount,
    };

    const pointer = x.ap_invoice_file || "";
    const inline = inlineUrls?.() || new Set<string>();
    // Filter BEFORE resolving the primary — the index has to refer to the same array
    // we map over, or a dropped line silently shifts which file counts as primary.
    const lines = parseLines(x.ap_invoices ?? t.ap_invoices).filter(
      (l) => l && l.file_url && isLikelyDocument(l, l.file_url === pointer, inline)
    );
    if (lines.length) {
      // The backfill asserts no primary (it can't safely re-guess), so fall back to
      // matching the live ap_invoice_file pointer, then to the first line.
      let primaryIdx = lines.findIndex((l) => l?.primary);
      if (primaryIdx < 0 && pointer)
        primaryIdx = lines.findIndex((l) => l?.file_url === pointer);
      if (primaryIdx < 0) primaryIdx = 0;

      // The stored `primary` can name a non-PDF the AI mislabelled. Where a real PDF
      // is present it is the document being keyed into Intacct, so it wins — this is
      // what stops a photographed-looking PNG opening in front of the actual invoice
      // on tickets whose stored primary is already wrong.
      if (!isPdfLine(lines[primaryIdx])) {
        const pdfIdx = lines.findIndex(isPdfLine);
        if (pdfIdx >= 0) primaryIdx = pdfIdx;
      }

      // With exactly one invoice, the ticket's fields ARE that invoice, so the live
      // values win outright and a sidebar correction renames the file at once (PR #56).
      //
      // With several, they are not. ap_amount is whatever describes the TICKET — on
      // #0680 it's Nedra's hand-typed $1,262.83, the sum of five receipts — so stamping
      // it on any single file reproduces exactly the bug Corey reported. The amount
      // therefore ALWAYS comes from the line itself here.
      //
      // The other tokens fall back to the ticket, because they are genuinely
      // ticket-level: the enricher records park per-attachment but reads it as null on
      // nearly every receipt, and a per-receipt vendor/date is often missing too. So
      // #0680's per-diem becomes TTH_07262026_SUTERLAW_130.00.pdf rather than the
      // NOPARK_NODATE_VENDOR_130.00.pdf the raw line alone would give.
      const single = lines.length === 1;
      const rows = lines.map((l, i) => {
        const isPrimary = i === primaryIdx;
        const src = single
          ? live
          : {
              park: l.park ?? live.park,
              date: l.invoice_date ?? live.date,
              vendor: l.vendor ?? live.vendor,
              amount: l.amount,
            };
        const amt = single ? t.ap_amount : l.amount;
        return {
          fileUrl: l.file_url,
          fileName: l.file_name || String(l.file_url).split("/").pop() || "",
          downloadName: intacctName(src),
          amount: amt === null || amt === undefined || amt === "" ? null : Number(amt),
          readable: l.readable !== false,
          primary: isPrimary,
        };
      });
      // Two lines can derive an identical name when park/amount are both blank —
      // downloading them in sequence would silently lose one.
      return uniquifyNames(
        rows,
        lines.map((l) => l.invoice_number ?? t.ap_invoice_number ?? null)
      );
    }

    // --- single-invoice fallbacks ---
    // Skip a pointer that is itself an inline image: on those tickets the enricher
    // never recorded per-attachment lines, so without this the card's only entry is
    // the signature logo.
    const pointerIsInline =
      !!pointer &&
      !isPdfLine({ file_url: pointer }) &&
      inline.has(normalizeFileUrl(pointer));
    const single =
      (pointerIsInline ? "" : x.ap_invoice_file) || threadFallback?.()?.url || "";
    if (!single) return [];
    return [
      {
        fileUrl: single,
        fileName:
          (pointerIsInline
            ? ""
            : String(x.ap_invoice_file || "").split("/").pop()) ||
          threadFallback?.()?.name ||
          "",
        downloadName: intacctName(live),
        amount:
          t.ap_amount === null || t.ap_amount === undefined || t.ap_amount === ""
            ? null
            : Number(t.ap_amount),
        readable: true,
        primary: true,
      },
    ];
  });
}
