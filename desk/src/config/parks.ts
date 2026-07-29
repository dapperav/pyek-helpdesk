// PYEK park brand colors + labels, shared by the dashboard and the ticket list
// so both use identical park colors. Mirrors the Barcuda app's parks config.
// The raw value comes from the HD Ticket custom field `pyek_property` (set by
// the enricher): TTH/TTA/CBB/CBC/CBV/ALL/DTL, "Corporate (PYK)", or blank.

export const PARK_COLORS: Record<string, string> = {
  TTH: "#E91E8C",
  TTA: "#2563EB",
  CBB: "#0891B2",
  CBC: "#D97706",
  CBV: "#7C3AED",
  ALL: "#16A34A",
  DTL: "#0EA5E9",
  // AP tags corporate/all-park invoices "PYK" (the rest of the stack uses
  // CORP / "Corporate (PYK)"). Give it the same corporate slate so AP rows +
  // dashboards don't render it as an unknown grey.
  PYK: "#475569",
};

export const PARK_FALLBACK = "#94A3B8"; // unspecified / unknown
export const CORPORATE_COLOR = "#475569";

// Normalize a raw pyek_property value to a short display label.
export function parkLabel(v?: string | null): string {
  if (!v) return "Unspecified";
  if (String(v).toLowerCase().startsWith("corporate")) return "Corporate";
  return String(v);
}

// Brand color for a normalized park label.
export function parkColor(label: string): string {
  if (PARK_COLORS[label]) return PARK_COLORS[label];
  if (label === "Corporate") return CORPORATE_COLOR;
  return PARK_FALLBACK;
}
