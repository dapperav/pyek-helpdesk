import { computed } from "vue";
import { getMeta } from "@/stores/meta";

/**
 * True when this is the AP instance — i.e. this site's HD Ticket doctype defines
 * the `ap_vendor` custom field.
 *
 * This is SCHEMA-based (does the field exist) rather than VALUE-based (does this
 * doc have a non-null vendor). The old guard `"ap_vendor" in doc` broke on Query /
 * no-invoice tickets: the agent detail + list payloads drop null-valued custom
 * fields, so an AP ticket with an empty vendor had no `ap_vendor` key and was
 * misread as non-AP (IT layout) until a save reloaded a fuller doc. Keying off the
 * doctype meta is value-independent, so EVERY AP ticket gets the AP UI. On the IT
 * site (no such field) it's false.
 *
 * An optional value source (the ticket doc or a list row) is checked first as a
 * no-flash fast-path: if it already carries the AP keys we return true immediately,
 * without waiting for the doctype meta to finish loading.
 */
export function useIsAp(
  source?: () => Record<string, any> | null | undefined
) {
  const { getField } = getMeta("HD Ticket");
  return computed(() => {
    const s = source?.();
    if (s && ("ap_vendor" in s || "ap_doc_type" in s)) return true;
    return !!getField("ap_vendor");
  });
}
