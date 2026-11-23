"""Deterministic follow-up drafts relative to the due date (BUILD_SPEC §10).

Cadence comes from ``config.yaml`` (``followups.steps``, default D-7, D-1,
D+3, D+10, D+25). Two tones: friendly and firm. Every draft names the invoice
number, amount and estimated due date and lists what is attached. Drafts are
never sent; status is always ``draft``. An LLM may later polish wording only.

The due date is always an estimate. When it rests on deemed acceptance or an
unreadable input, a reviewer note asks the user to verify it before sending.
MSMED wording appears only for a micro/small supplier, and claims of Udyam
registration, s.16 interest and the ODR route only when C13 passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from app.fmt import d, inr
from app.rules.config import get_config
from app.rules.interest import estimate_interest

TONES = ("friendly", "firm")
CHANNELS = ("email", "whatsapp")
DRAFT_LABEL = "DRAFT - not sent. Review before sending."
AMOUNT_PLACEHOLDER = "[amount to be verified]"

# Failed check -> what the *buyer* can provide. Supplier-side fixes (GST math,
# duplicate number, Udyam on invoice) are not asked of the buyer.
BUYER_REQUESTS: dict[str, str] = {
    "C01": "confirmation of the PO number this invoice should be booked against",
    "C04": "confirmation of the correct legal name and GSTIN for billing",
    "C07": "a copy of the delivery challan with your receiving stamp and signature",
    "C10": "the GRN or a written acceptance of the goods delivered",
    "C11": "written confirmation of the agreed payment terms",
}


def buyer_requests(check_ids: list[str]) -> list[str]:
    """Buyer-facing requests for the given failed/missing check ids, in a stable order."""
    return [BUYER_REQUESTS[c] for c in sorted(set(check_ids)) if c in BUYER_REQUESTS]


@dataclass
class FollowupContext:
    invoice_no: str
    amount: Optional[float]
    due_date: date  # always an estimate (DueDateResult.estimated)
    due_reasoning: str
    buyer_name: str
    supplier_name: str
    msmed_applies: bool = True  # supplier class is micro/small (config)
    udyam_on_record: bool = False  # C13 passed: Udyam number appears on the supplier's documents
    due_basis: str = "unknown"  # DueDateResult.acceptance_basis
    due_uncertain: bool = False  # DueDateResult.uncertain
    missing: list[str] = field(default_factory=list)  # buyer-facing requests, see buyer_requests()
    attachments: list[str] = field(default_factory=list)  # e.g. "Purchase order KAA/PO/1100"

    @property
    def due_needs_verify(self) -> bool:
        return self.due_uncertain or self.due_basis in ("deemed", "unknown")


@dataclass
class Draft:
    step: int
    send_on: date
    channel: str
    tone: str
    subject: str
    text: str
    past: bool = False  # send date had already passed when generated; kept for reference
    status: str = "draft"


def _attach_line(ctx: FollowupContext) -> str:
    return "Attached: " + ("; ".join(ctx.attachments) if ctx.attachments else "invoice copy") + "."


def _missing_line(ctx: FollowupContext) -> str:
    if not ctx.missing:
        return ""
    return "To close our records, could you please share " + "; and ".join(ctx.missing) + "."


def _header(ctx: FollowupContext, send_on: date, today: Optional[date], last: bool) -> str:
    """Reviewer notes above the draft; not part of the message to the buyer."""
    lines = [f"[{DRAFT_LABEL}]"]
    if ctx.amount is None:
        lines.append(f"[VERIFY: the invoice total could not be read reliably. Replace {AMOUNT_PLACEHOLDER} "
                     "with the checked amount before sending.]")
    if ctx.due_needs_verify:
        why = ("deemed acceptance" if ctx.due_basis == "deemed"
               else "an input that could not be read reliably")
        lines.append(f"[VERIFY: the estimated due date {d(ctx.due_date)} rests on {why}. "
                     f"{ctx.due_reasoning} Confirm it before sending.]")
    if today is not None and send_on < today:
        nxt = ("Consider the dispute evidence pack as the next step." if last
               else "Use the latest step instead.")
        lines.append(f"[Scheduled send date {d(send_on)} has passed; kept for reference. {nxt}]")
    return "\n".join(lines)


def _body(step: int, tone: str, ctx: FollowupContext, send_on: date,
          cfg: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, body) for one step."""
    amt = inr(ctx.amount) if ctx.amount is not None else AMOUNT_PLACEHOLDER
    due, inv = d(ctx.due_date), ctx.invoice_no
    firm = tone == "firm"
    max_days = int(cfg["msmed"]["max_terms_days"])
    ref_l = f"invoice {inv} for {amt}, estimated due date {due}"
    ref = ref_l[0].upper() + ref_l[1:]

    if step < 0:
        days = -step
        subject = f"Upcoming payment: invoice {inv} due {due} (estimated)"
        if firm:
            lead = (f"This is a reminder that payment of {amt} against invoice {inv} falls due on our "
                    f"estimated due date of {due}, {days} day(s) from now. Please schedule it for "
                    "release on or before that date.")
        else:
            lead = (f"Hope all is well. A quick note that invoice {inv} for {amt} is due on {due} by our "
                    f"estimate ({days} day(s) away). Please let us know if anything is needed from our side.")
        parts = [lead, _missing_line(ctx)]
    elif step <= 3:
        subject = f"Payment overdue: invoice {inv} ({amt})"
        if firm:
            lead = (f"Payment for {ref_l}, has not been received and is now {step} day(s) overdue. "
                    "Please release it immediately and share the UTR reference.")
        else:
            lead = (f"We have not yet received payment for {ref_l}. It may already be in process; "
                    "could you please confirm the expected payment date?")
        parts = [lead, _missing_line(ctx)]
    elif step <= 10:
        subject = f"Second reminder: invoice {inv} overdue by {step} days"
        law = ""
        if ctx.msmed_applies:
            deduction_rule = cfg.get("legal_refs", {}).get("buyer_deduction_rule", "the Income-tax Act")
            who = ("As a Udyam-registered micro/small supplier, we" if ctx.udyam_on_record
                   else "For reference, we")
            law = (f"{who} would note that the MSMED Act, 2006 (s.15) limits payment to micro and small "
                   f"suppliers to {max_days} days from acceptance, and {deduction_rule} "
                   "allows the buyer's deduction for such dues only on payment (please verify with your "
                   "advisers).")
        if firm:
            lead = f"{ref} remains unpaid, {step} days past that date. We request payment within 3 working days."
        else:
            lead = (f"Following up on {ref_l}, which is now {step} days overdue. We would be grateful "
                    "for a payment date.")
        parts = [lead, law]
    else:
        subject = f"Escalation: invoice {inv} overdue by {step} days"
        interest = ""
        if ctx.msmed_applies and ctx.udyam_on_record:
            est = estimate_interest(ctx.amount or 0.0, ctx.due_date, send_on, cfg)
            if ctx.amount is not None and est.computable and est.interest:
                interest = (f"Estimated statutory interest under MSMED s.16 to {d(send_on)} is about "
                            f"{inr(est.interest)} (estimate, not legal advice).")
            route = ("If the matter is not resolved, we may consider a delayed-payment reference through "
                     "the MSME ODR portal (verify the current process).")
        else:
            route = "If the matter is not resolved, we will need to escalate it."
        if firm:
            lead = (f"Despite earlier reminders, {ref_l}, is {step} days overdue. Please arrange "
                    "payment within 7 days.")
        else:
            lead = (f"We are writing again about {ref_l}, now {step} days overdue. We value our "
                    "relationship and would like to settle this amicably.")
        parts = [lead, interest, route]

    greeting = f"Dear {ctx.buyer_name} Accounts Team,"
    sign = f"Regards,\nAccounts, {ctx.supplier_name}"
    body = "\n\n".join([greeting] + [p for p in parts if p] + [_attach_line(ctx), sign])
    return subject, body


def _whatsapp(subject: str, body: str) -> str:
    """Shorter text for WhatsApp: subject line + body without greeting/sign-off."""
    paras = body.split("\n\n")[1:-1]
    return "\n".join([f"*{subject}*"] + paras)


def build_followups(ctx: FollowupContext, *, tone: str = "friendly", channel: str = "email",
                    today: Optional[date] = None, cfg: Optional[dict[str, Any]] = None) -> list[Draft]:
    """Every step of the cadence; steps whose send date is before ``today`` are marked ``past``."""
    if tone not in TONES:
        raise ValueError(f"tone must be one of {TONES}")
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    if cfg is None:
        cfg = get_config()
    out = []
    steps = sorted(int(x) for x in cfg["followups"]["steps"])
    for step in steps:
        send_on = ctx.due_date + timedelta(days=step)
        subject, body = _body(step, tone, ctx, send_on, cfg)
        text = f"Subject: {subject}\n\n{body}" if channel == "email" else _whatsapp(subject, body)
        out.append(Draft(step=step, send_on=send_on, channel=channel, tone=tone, subject=subject,
                         text=_header(ctx, send_on, today, step == steps[-1]) + "\n\n" + text,
                         past=today is not None and send_on < today))
    return out
