"""Deterministic follow-up drafts relative to the due date (BUILD_SPEC §10).

Cadence comes from ``config.yaml`` (``followups.steps``, default D-7, D-1,
D+3, D+10, D+25). Two tones: friendly and firm. Every draft names the invoice
number, amount and due date and lists what is attached. Drafts are never sent;
status is always ``draft``. An LLM may later polish wording only.
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
    due_date: date
    due_reasoning: str
    buyer_name: str
    supplier_name: str
    msmed_applies: bool = True
    missing: list[str] = field(default_factory=list)  # buyer-facing requests, see buyer_requests()
    attachments: list[str] = field(default_factory=list)  # e.g. "Purchase order KAA/PO/1100"


@dataclass
class Draft:
    step: int
    send_on: date
    channel: str
    tone: str
    subject: str
    text: str
    status: str = "draft"


def _attach_line(ctx: FollowupContext) -> str:
    return "Attached: " + ("; ".join(ctx.attachments) if ctx.attachments else "invoice copy") + "."


def _missing_line(ctx: FollowupContext) -> str:
    if not ctx.missing:
        return ""
    return "To close our records, could you please share " + "; and ".join(ctx.missing) + "."


def _body(step: int, tone: str, ctx: FollowupContext, send_on: date) -> tuple[str, str]:
    """Return (subject, body) for one step."""
    amt, due, inv = inr(ctx.amount), d(ctx.due_date), ctx.invoice_no
    firm = tone == "firm"
    ref_l = f"invoice {inv} for {amt}, due {due}"
    ref = ref_l[0].upper() + ref_l[1:]

    if step < 0:
        days = -step
        subject = f"Upcoming payment: invoice {inv} due {due}"
        if firm:
            lead = (f"This is a reminder that payment of {amt} against invoice {inv} falls due on "
                    f"{due}, {days} day(s) from now. Please schedule it for release on or before that date.")
        else:
            lead = (f"Hope all is well. A quick note that invoice {inv} for {amt} is due on {due} "
                    f"({days} day(s) away). Please let us know if anything is needed from our side.")
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
            law = ("As a registered MSME supplier, we would note that the MSMED Act, 2006 (s.15) limits "
                   "payment to 45 days from acceptance, and s.43B(h) of the Income-tax Act allows the "
                   "buyer's deduction for such dues only on payment (please verify with your advisers).")
        if firm:
            lead = (f"{ref} remains unpaid, {step} days past the due date. We request payment within "
                    "3 working days.")
        else:
            lead = (f"Following up on {ref_l}, which is now {step} days overdue. We would be grateful "
                    "for a payment date.")
        parts = [lead, law]
    else:
        subject = f"Escalation: invoice {inv} overdue by {step} days"
        est = estimate_interest(ctx.amount or 0.0, ctx.due_date, send_on) if ctx.msmed_applies else None
        interest = ""
        if est and est.computable and est.interest:
            interest = (f"Estimated statutory interest under MSMED s.16 to {d(send_on)} is about "
                        f"{inr(est.interest)} (estimate, not legal advice).")
        route = ("If the matter is not resolved, we may consider a delayed-payment reference through the "
                 "MSME ODR portal (verify the current process)." if ctx.msmed_applies else
                 "If the matter is not resolved, we will need to escalate it.")
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
    paras = [p for p in body.split("\n\n")[1:-1]]
    return "\n".join([f"*{subject}*"] + paras)


def build_followups(ctx: FollowupContext, *, tone: str = "friendly", channel: str = "email",
                    cfg: Optional[dict[str, Any]] = None) -> list[Draft]:
    if tone not in TONES:
        raise ValueError(f"tone must be one of {TONES}")
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    if cfg is None:
        cfg = get_config()
    out = []
    for step in sorted(int(x) for x in cfg["followups"]["steps"]):
        send_on = ctx.due_date + timedelta(days=step)
        subject, body = _body(step, tone, ctx, send_on)
        text = body if channel == "email" else _whatsapp(subject, body)
        out.append(Draft(step=step, send_on=send_on, channel=channel, tone=tone, subject=subject,
                         text=f"[{DRAFT_LABEL}]\n\n" + (f"Subject: {subject}\n\n{text}" if channel == "email"
                                                        else text)))
    return out
