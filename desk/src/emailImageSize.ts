/**
 * How wide an inline picture goes out in an email.
 *
 * Mark, 2026-08-26: *"i also want the ability to resize the image if it lands
 * inline too big."* The email that prompted it carried `width="1407"` — the
 * natural size of a 1440px screenshot, inserted by the editor without anyone
 * choosing it.
 *
 * A `width` attribute is the only lever there is. Outlook renders HTML through
 * Word, which ignores `max-width` on images, so a picture with no width blows
 * the reading pane out sideways and a picture with a bad one stays bad wherever
 * it's opened. That makes the size a decision the agent has to be able to make
 * — and, since most of the time nobody wants to think about it, one that has a
 * sane answer by default.
 *
 * Shared by both reply surfaces so they can't drift: the quick bars pick a step
 * per thumbnail, and the full editor clamps on insert and then hands over to
 * its own drag handle.
 */

/**
 * What an unattended picture goes out at. Wide enough that a screenshot of a
 * dialog is still readable, narrow enough to sit inside a reading pane without
 * a horizontal scrollbar.
 */
export const MAX_EMAIL_WIDTH = 640;

export type SizeKey = "small" | "medium" | "large" | "full";

export interface SizeStep {
  key: SizeKey;
  /** What the chip on the thumbnail reads. */
  label: string;
  /** Target width in px; null means "however big it actually is". */
  px: number | null;
}

export const SIZE_STEPS: SizeStep[] = [
  { key: "small", label: "S", px: 320 },
  { key: "medium", label: "M", px: MAX_EMAIL_WIDTH },
  { key: "large", label: "L", px: 1024 },
  { key: "full", label: "Full", px: null },
];

export const DEFAULT_SIZE: SizeKey = "medium";

const MEDIUM = SIZE_STEPS[1] as SizeStep;

export function stepFor(key: SizeKey): SizeStep {
  return SIZE_STEPS.find((s) => s.key === key) ?? MEDIUM;
}

/**
 * The width to actually send, in px, or null when we never learned how big the
 * picture is (a failed probe — cosmetic, and better than guessing).
 *
 * Never upscales: asking for "L" on a 200px icon sends 200px, because a browser
 * stretching a small picture to 1024 looks broken in a way that reads as our
 * fault rather than the screenshot's.
 */
export function emailWidth(key: SizeKey, natural: number | null): number | null {
  const { px } = stepFor(key);
  if (!natural) return px;
  return px ? Math.min(px, natural) : natural;
}

/**
 * The next size to offer, skipping steps this particular picture is too small
 * to use. A 300px icon cycles between S and Full and never pretends L means
 * anything.
 */
export function nextSize(key: SizeKey, natural: number | null): SizeKey {
  const usable = SIZE_STEPS.filter(
    (s) => s.px === null || !natural || s.px < natural
  );
  if (!usable.length) return "full";
  const at = usable.findIndex((s) => s.key === key);
  return (usable[(at + 1) % usable.length] as SizeStep).key;
}

/**
 * Whether this picture has more than one size worth offering. A 200px icon
 * doesn't — every step collapses to 200px — so the caller hides the control
 * rather than leaving a button that does nothing when pressed.
 */
export function isResizable(natural: number | null): boolean {
  if (!natural) return true;
  return SIZE_STEPS.some((s) => s.px !== null && s.px < natural);
}

/** Chip text: the step's label, or the real width once it's the natural one. */
export function sizeLabel(key: SizeKey, natural: number | null): string {
  const width = emailWidth(key, natural);
  if (key === "full" || (natural && width === natural)) {
    return width ? `${width}px` : "Full";
  }
  return stepFor(key).label;
}
