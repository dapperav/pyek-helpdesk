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
  threadFallback?: () => { url: string; name: string } | null
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

    const lines = parseLines(x.ap_invoices ?? t.ap_invoices);
    if (lines.length) {
      const pointer = x.ap_invoice_file || "";
      // The backfill asserts no primary (it can't safely re-guess), so fall back to
      // matching the live ap_invoice_file pointer, then to the first line.
      let primaryIdx = lines.findIndex((l) => l?.primary);
      if (primaryIdx < 0 && pointer)
        primaryIdx = lines.findIndex((l) => l?.file_url === pointer);
      if (primaryIdx < 0) primaryIdx = 0;

      return lines
        .filter((l) => l && l.file_url)
        .map((l, i) => {
          const isPrimary = i === primaryIdx;
          const src = isPrimary
            ? live
            : {
                park: l.park,
                date: l.invoice_date,
                vendor: l.vendor,
                amount: l.amount,
              };
          const amt = isPrimary ? t.ap_amount : l.amount;
          return {
            fileUrl: l.file_url,
            fileName: l.file_name || String(l.file_url).split("/").pop() || "",
            downloadName: intacctName(src),
            amount: amt === null || amt === undefined || amt === "" ? null : Number(amt),
            readable: l.readable !== false,
            primary: isPrimary,
          };
        });
    }

    // --- single-invoice fallbacks ---
    const single = x.ap_invoice_file || threadFallback?.()?.url || "";
    if (!single) return [];
    return [
      {
        fileUrl: single,
        fileName:
          String(x.ap_invoice_file || "").split("/").pop() ||
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
