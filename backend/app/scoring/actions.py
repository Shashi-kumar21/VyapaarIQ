"""Rule-generated next actions, ranked by severity then deadline (§7 Actions).

Templates are deterministic. An LLM may later rephrase ``rationale`` only.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.rules.config import get_config
from app.schemas import Action, Check, CheckStatus, DueDateResult

# check_id -> (title, rationale, owner_role)
TEMPLATES: dict[str, tuple[str, str, str]] = {
    "C01": ("Get the PO number confirmed and reissue the invoice citing it",
            "Buyers' AP teams routinely hold invoices that do not match a PO.", "supplier_accounts"),
    "C02": ("Correct the invoice amounts (GST math / PO value) and issue a credit/debit note",
            "An amount mismatch is the most common reason an invoice is put on hold.", "supplier_accounts"),
    "C03": ("Reconcile line items with the PO or obtain a PO amendment",
            "Quantities or rates above the PO need the buyer's written approval.", "sales"),
    "C04": ("Fix the buyer name/GSTIN so every document names the same legal entity",
            "A GSTIN mismatch can block the buyer's input-tax credit and the payment.", "supplier_accounts"),
    "C05": ("Attach the delivery challan / LR for this invoice",
            "Without delivery proof the supplier cannot show goods were delivered.", "dispatch"),
    "C06": ("Ship the balance quantity or raise a credit note for the short delivery",
            "The buyer will pay only for quantities actually delivered.", "dispatch"),
    "C07": ("Obtain the buyer's receiving stamp and signature on the challan",
            "A signed challan is the strongest proof of receipt short of a GRN.", "dispatch"),
    "C08": ("Check and explain the document date order",
            "Out-of-order dates invite questions during payment approval.", "supplier_accounts"),
    "C09": ("Attach the e-way bill (or record why it was not required)",
            "Missing or mismatched e-way bills can be questioned in GST audits.", "dispatch"),
    "C10": ("Request GRN / acceptance acknowledgement from the buyer's receiving department",
            "Acceptance starts the MSMED payment clock; without it acceptance is only deemed.", "sales"),
    "C11": ("Send written payment terms (PO acknowledgement or terms letter)",
            "Without written terms the MSMED 15-day default applies, which buyers often dispute.", "sales"),
    "C12": ("Note that terms exceed 45 days and plan the follow-up around the 45-day limit",
            "MSMED s.15 limits the agreed period to 45 days from acceptance (verify).", "supplier_accounts"),
    "C13": ("Add the Udyam registration number to invoices",
            "MSMED delayed-payment protections depend on Udyam registration.", "supplier_accounts"),
    "C14": ("Check for a duplicate invoice number and cancel or renumber",
            "Duplicate invoice numbers are rejected by buyers and the GST portal.", "supplier_accounts"),
}
UNCERTAIN_TEMPLATE = ("Manually verify: {name}",
                      "The document could not be read reliably; a person should confirm it.",
                      "supplier_accounts")
SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}


def build_actions(checks: list[Check], due: Optional[DueDateResult], *,
                  today: Optional[date] = None, cfg: Optional[dict[str, Any]] = None) -> list[Action]:
    if cfg is None:
        cfg = get_config()
    today = today or date.today()
    lead = int(cfg["actions"]["lead_days_before_due"])
    target = None
    if due and due.due_date:
        target = max(today, due.due_date - timedelta(days=lead))

    rows: list[tuple[tuple, Action]] = []
    for c in checks:
        if c.status == CheckStatus.passed or c.severity.value == "info" and c.status == CheckStatus.missing:
            continue
        if c.status == CheckStatus.uncertain:
            t, r, owner = UNCERTAIN_TEMPLATE
            title = t.format(name=c.name)
        else:
            title, r, owner = TEMPLATES[c.check_id]
        due_by = target
        if c.check_id == "C10" and target:
            title = f"{title} before {target.isoformat()}"
        sev = SEVERITY_RANK.get(c.severity.value, 3) + (0.5 if c.status == CheckStatus.uncertain else 0)
        key = (sev, due_by or date.max, c.check_id)
        rows.append((key, Action(priority=0, check_id=c.check_id, title=title,
                                 rationale=f"{r} {c.detail}", due_by=due_by, owner_role=owner)))
    rows.sort(key=lambda kv: kv[0])
    out = []
    for i, (_, a) in enumerate(rows, 1):
        a.priority = i
        out.append(a)
    return out
