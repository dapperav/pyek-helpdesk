// The suggested-reply text, assembled locally from what the enricher already
// wrote (pyek_suggestions) — no AI call, so generating one costs nothing.
// Shared by AiAssistPanel (the AI tab's "Draft reply") and MobileReplyFlow
// (the chip above the phone's quick-reply bar), so the two surfaces can never
// drift apart on wording.

interface AccessRequest {
  user?: string;
  system?: string;
  scope?: string;
}

interface SuggestionBranch {
  fields?: { label: string; value: string }[];
  artifact?: string;
  missing?: string[];
  access_request?: AccessRequest;
}

interface PyekSuggestions {
  build_sheet?: SuggestionBranch;
  it_assist?: SuggestionBranch;
}

export function parsePyekSuggestions(doc: any): PyekSuggestions | null {
  const raw = doc?.pyek_suggestions;
  if (!raw) return null;
  try {
    return JSON.parse(raw) || null;
  } catch {
    return null;
  }
}

// Chip gate: only a draft grounded in an enricher branch is worth floating
// over the composer. The generic acknowledgement below still exists for the
// AI tab's button, but it doesn't earn interruption real estate.
export function hasAiReplyDraft(doc: any): boolean {
  const s = parsePyekSuggestions(doc);
  return !!(s?.build_sheet || s?.it_assist);
}

export function buildAiReplyDraft(doc: any): string {
  const s = parsePyekSuggestions(doc);
  const bs = s?.build_sheet || null;
  const it = s?.it_assist || null;

  // Summary-only tickets — analysed but with no build-sheet or IT branch —
  // get a plain acknowledgement. Deliberately does NOT echo pyek_summary
  // back: it's written in the third person for an agent to read and reads
  // oddly returned to the person who wrote in.
  if (!bs && !it) {
    return [
      "Hi,",
      "",
      "Thanks for flagging this — I'm looking into it now and will follow up shortly.",
      "",
      "Thanks!",
    ].join("\n");
  }

  const lines = ["Hi,", ""];
  if (bs) {
    const artifactUrls = String(bs.artifact || "")
      .split(/\s+/)
      .map((u) => u.trim())
      .filter((u) => u.startsWith("http"));
    if (artifactUrls.length) {
      lines.push(
        artifactUrls.length > 1 ? "Here are the links:" : "Here's the link:"
      );
      artifactUrls.forEach((u) => lines.push(u));
    } else if (bs.fields?.length) {
      lines.push("Done — here's what was set up:");
      bs.fields.forEach((f) => lines.push(`• ${f.label}: ${f.value}`));
    }
  } else if (it) {
    // Deliberately does NOT list it.steps: those are the agent's internal
    // checklist and don't belong in a requester-facing reply.
    const a = it.access_request;
    if (a?.system) {
      const who = a.user ? ` for ${a.user}` : "";
      const scope = a.scope ? ` (${a.scope})` : "";
      lines.push(`I'm taking care of the ${a.system} access${who}${scope}.`);
    } else {
      lines.push("Thanks for flagging this — I'm looking into it now.");
    }
  }
  const missingItems: string[] = (bs || it)?.missing || [];
  if (missingItems.length) {
    lines.push("");
    lines.push(
      `Before I can finish, could you confirm: ${missingItems.join("; ")}?`
    );
  }
  lines.push("", "Thanks!");
  return lines.join("\n");
}

// One line for tight UI (the chip): the first line that says something,
// skipping the greeting.
export function aiDraftPreview(draft: string): string {
  return (
    draft
      .split("\n")
      .map((l) => l.trim())
      .find((l) => l && !/^hi[,!.]?$/i.test(l)) || draft
  );
}
