// Reply-all for the ticket thread (Mark, 2026-08-20: "when I reply it
// actually reply all instead"). Built from the thread's newest email with the
// same rule EmailArea.replyAll applies to a single message: answer the newest
// sender, carry everyone else from that email's To/Cc in Cc, and strip
// ourselves plus the helpdesk's own send addresses (which would otherwise CC
// the shared inbox on itself). Used by both persistent reply bars; the full
// editors keep their own per-email reply/reply-all buttons.

export interface ReplyAllSet {
  to: string[];
  cc: string[];
}

interface ThreadEmail {
  outgoing?: boolean;
  sender?: { name?: string } | string;
  to?: string | string[];
  cc?: string | string[];
}

const BRACKETED_EMAIL = /<\s*([^<>\s]+@[^<>\s]+)\s*>/;

// "Bre Wold <bre.wold@x.com>" -> "bre.wold@x.com"; bare addresses pass through.
function addressOf(item: string): string {
  const m = item.match(BRACKETED_EMAIL);
  return (m ? m[1] : item).trim();
}

function asList(v: string | string[] | undefined): string[] {
  if (!v) return [];
  const arr = typeof v === "string" ? v.split(",") : v;
  return arr
    .map((s) => addressOf(String(s)))
    .filter((s) => s.includes("@"));
}

export function buildReplyAllSet(opts: {
  emails: ThreadEmail[];
  selfEmail: string;
  supportEmails: string[];
  raisedBy: string;
}): ReplyAllSet {
  const { emails, selfEmail, supportEmails, raisedBy } = opts;
  const newest = emails.length ? emails[emails.length - 1] : null;

  const dropped = (s: string) => {
    const low = s.toLowerCase();
    if (low === (selfEmail || "").toLowerCase()) return true;
    return supportEmails.some((addr) => addr && low.includes(addr));
  };

  let to: string[] = [];
  let cc: string[] = [];
  if (newest) {
    const sender = addressOf(
      typeof newest.sender === "string"
        ? newest.sender
        : newest.sender?.name || ""
    );
    const origTo = asList(newest.to);
    const origCc = asList(newest.cc);
    if (newest.outgoing) {
      // Our own reply is the newest message: keep talking to the same set.
      to = origTo;
      cc = origCc;
    } else {
      to = sender && sender.includes("@") ? [sender] : [];
      cc = [...origTo, ...origCc];
    }
  }
  if (!to.length && raisedBy) to = [raisedBy];

  const seen = new Set<string>();
  const dedup = (list: string[]) =>
    list.filter((s) => {
      const low = s.toLowerCase();
      if (dropped(s) || seen.has(low)) return false;
      seen.add(low);
      return true;
    });
  to = dedup(to);
  cc = dedup(cc); // `seen` already holds every To address, so no overlap.

  // Never leave the reply addressless: the requester is always a valid To.
  if (!to.length && raisedBy) to = [raisedBy];
  return { to, cc };
}

// Every address the helpdesk itself sends or receives as — the set reply-all
// must never target (it would CC the shared inbox on itself and echo the
// reply back onto the ticket). The agent's PERSONAL outgoing list alone is
// not enough: agents without User Email rows get an empty list there, which
// let pos.pyek@ ride into Cc (found live on 0493, 2026-08-20).
// `available_emails` is every outgoing-enabled Email Account, user-independent.
export function helpdeskSupportEmails(info: any): string[] {
  const rows = [
    ...(info?.outgoing_emails ?? []),
    ...(info?.available_emails ?? []),
  ];
  return [
    ...new Set(
      rows.map((e: any) => (e.email_id || "").toLowerCase()).filter(Boolean)
    ),
  ];
}

// Convenience for the reply bars: build the set straight from the raw
// Communication rows the ticket pages already hold (`recipients` is frappe's
// comma-separated To field).
export function replyAllFromCommunications(
  communications: any[] | undefined,
  selfEmail: string,
  supportEmails: string[],
  raisedBy: string
): ReplyAllSet {
  return buildReplyAllSet({
    emails: (communications || []).map((e: any) => ({
      outgoing: e.sent_or_received === "Sent",
      sender: e.sender,
      to: e.recipients,
      cc: e.cc,
    })),
    selfEmail,
    supportEmails,
    raisedBy,
  });
}

// "bre.wold@x.com" -> "Bre"; "Bre Wold" -> "Bre" — the short label the bars
// show in their "to …" summary line.
export function recipientFirstName(raw: string): string {
  const base = raw.includes("@")
    ? raw.split("@")[0].split(/[._]/)[0]
    : raw.split(" ")[0];
  return base ? base.charAt(0).toUpperCase() + base.slice(1) : "";
}

export function recipientSummary(set: ReplyAllSet): string {
  const all = [...set.to, ...set.cc];
  if (!all.length) return "";
  const names = all.slice(0, 2).map(recipientFirstName).filter(Boolean);
  const extra = all.length - names.length;
  return names.join(", ") + (extra > 0 ? ` +${extra}` : "");
}
