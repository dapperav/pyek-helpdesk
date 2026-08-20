"""On-demand mail tick — the enricher's sixty-second poke.

Frappe's scheduler ticks every 240 seconds (`DEFAULT_SCHEDULER_TICK`), and the
IMAP pull is a *cron* job that can only fire on one of those ticks. Its cron is
`0/10`, so in practice inbound mail landed every 8 or 12 minutes: measured over
60 messages on 2026-08-20, header date to Communication row, median 6.0 min,
p90 10.7, worst 14.7. Outbound sat behind `frappe.email.queue.flush`, an "All"
job on the same tick, for up to 4 minutes more, and the deferred requester
acknowledgement waited for a tick after that.

The obvious lever — dropping `scheduler_tick_interval` to 60 in site config —
also quadruples how often the search index build, corpus download, calendar
sync and monitor flush run, for no benefit to mail. So instead the enricher,
which already wakes every 60 seconds on Railway, calls this endpoint each
cycle and we enqueue only the three mail-critical jobs.

Every enqueue here is deduplicated, so a pull that takes longer than a minute
can never pile up behind itself: `pull()` guards per account with its own
`pull_from_email_account|<account>` job name, and the other two carry explicit
`job_id`s. The scheduler keeps running all three on its normal 4-minute tick,
so if the enricher is down mail still flows — just at the old speed.
"""

import frappe

from frappe.utils.background_jobs import enqueue

# Sent to the short queue: all three are I/O against Microsoft 365 and finish
# in seconds. The long queue is for the index builds.
_QUEUE = "short"


@frappe.whitelist(methods=["POST"])
def tick() -> dict:
    """Run the mail-critical scheduled jobs now. Returns what was enqueued."""
    # The enricher authenticates as Administrator via its API key. Anyone else
    # needs System Manager — this triggers IMAP fetches and flushes outbound
    # mail, so it is not something an agent should be able to poke.
    if frappe.session.user != "Administrator":
        frappe.only_for("System Manager")

    done = {}

    # 1. Inbound. pull() enumerates the enabled accounts and enqueues one job
    #    per account, skipping any that is already queued.
    try:
        from frappe.email.doctype.email_account.email_account import pull

        pull()
        done["pull"] = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PYEK mail tick: pull failed")
        done["pull"] = False

    # 2. Outbound. Agent replies go out inline now (HD Settings
    #    instantly_send_email), but acknowledgements, feedback requests and
    #    notification mail still queue.
    try:
        enqueue(
            "frappe.email.queue.flush",
            queue=_QUEUE,
            job_id="pyek-mail-flush",
            deduplicate=True,
        )
        done["flush"] = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PYEK mail tick: flush failed")
        done["flush"] = False

    # 3. The deferred requester acknowledgement, which waits on the enricher's
    #    summary. Cheap when there is nothing pending — one indexed filter.
    try:
        enqueue(
            "helpdesk.helpdesk.doctype.hd_ticket.hd_ticket"
            ".send_pending_acknowledgements",
            queue=_QUEUE,
            job_id="pyek-ack-sweep",
            deduplicate=True,
        )
        done["ack_sweep"] = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PYEK mail tick: ack sweep failed")
        done["ack_sweep"] = False

    return done
