"""Seed synthetic demo history (BUILD_SPEC §5, task T3.5).

Creates 1 supplier, the 6 fictional buyers from ``samples/ground_truth.json``
and ~60 historical *paid* invoices with payment events, so buyer reliability
(§8) and the forecast (§9) have something to work with. Every seeded row is
flagged ``synthetic=True``; the UI must say it is synthetic demo data.

Deterministic (fixed RNG seed). Safe to re-run: existing seeded history is
left alone unless ``--reset`` is given.

    cd backend; ..\\.venv\\Scripts\\python -m app.seed [--reset]
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from app.db.models import Buyer, Invoice, PaymentEvent, Supplier
from app.db.session import init_db, session_scope
from app.matching.normalize import normalize_gstin, normalize_ref
from app.rules.config import get_config

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "samples" / "ground_truth.json"
RNG_SEED = 2026
INVOICES_PER_BUYER = 10
HISTORY_START = date(2025, 10, 1)

# Days late for each of a buyer's 10 invoices (order shuffled per buyer). Fixed
# lists keep the resulting labels stable: Reliable / Mixed / Slow.
BEHAVIOUR: dict[str, list[int]] = {
    "reliable": [-3, -2, -1, 0, 0, 1, 2, 3, 4, 5],
    "mixed": [0, 2, 5, 8, 10, 12, 14, 18, 25, 35],
    "slow": [15, 22, 28, 35, 40, 45, 55, 62, 75, 90],
}
BUYER_BEHAVIOUR = {"KAA": "reliable", "NEW": "mixed", "DAM": "slow",
                   "SPV": "reliable", "GEL": "mixed", "VIP": "slow"}

# Used only when ground_truth.json is missing; same fictional parties.
FALLBACK_SUPPLIER = {"name": "Shakti Precision Components Pvt Ltd", "gstin": "27AAECS4821K1Z6",
                     "udyam": "UDYAM-MH-26-0048213", "enterprise_class": "small"}
FALLBACK_BUYERS = [
    {"code": "KAA", "name": "Kaveri Auto Assemblies Pvt Ltd", "gstin": "27AABCK7712M1Z9"},
    {"code": "NEW", "name": "Narmada Engineering Works Ltd", "gstin": "24AACCN3390P1Z3"},
    {"code": "DAM", "name": "Deccan Agro Machines Pvt Ltd", "gstin": "36AAFCD5521Q1ZA"},
    {"code": "SPV", "name": "Sahyadri Pumps & Valves LLP", "gstin": "27ABEFS8834R1Z7"},
    {"code": "GEL", "name": "Ganga Electricals Pvt Ltd", "gstin": "09AAGCG1209L1ZK"},
    {"code": "VIP", "name": "Vindhya Infra Projects Ltd", "gstin": "23AAHCV6650N1ZV"},
]


def _parties() -> tuple[dict, list[dict]]:
    if GROUND_TRUTH.exists():
        gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
        return gt["supplier"], gt["buyers"]
    return FALLBACK_SUPPLIER, FALLBACK_BUYERS


def _upsert_supplier(s: Session, sup: dict) -> Supplier:
    row = s.exec(select(Supplier)).first()
    if row is None:
        row = Supplier(name=sup["name"], gstin=sup.get("gstin"), udyam_no=sup.get("udyam"),
                       enterprise_class=sup.get("enterprise_class")
                       or get_config()["supplier"]["enterprise_class"])
        s.add(row)
        s.commit()
        s.refresh(row)
    return row


def _upsert_buyer(s: Session, b: dict) -> Buyer:
    g = normalize_gstin(b["gstin"])
    for row in s.exec(select(Buyer)).all():
        if normalize_gstin(row.gstin) == g:
            row.synthetic = True
            s.add(row)
            s.commit()
            return row
    row = Buyer(name=b["name"], gstin=g, synthetic=True)
    s.add(row)
    s.commit()
    s.refresh(row)
    return row


def reset_history(s: Session) -> int:
    rows = s.exec(select(Invoice).where(Invoice.synthetic == True)).all()  # noqa: E712
    for inv in rows:
        for p in s.exec(select(PaymentEvent).where(PaymentEvent.invoice_id == inv.id)).all():
            s.delete(p)
        s.delete(inv)
    s.commit()
    return len(rows)


def seed(s: Session, *, reset: bool = False, rng_seed: int = RNG_SEED) -> dict:
    """Seed the demo history; returns counts. Idempotent unless ``reset``."""
    removed = reset_history(s) if reset else 0
    existing = s.exec(select(Invoice).where(Invoice.synthetic == True)).first()  # noqa: E712
    sup, buyers = _parties()
    _upsert_supplier(s, sup)
    if existing is not None:
        return {"created": 0, "removed": removed, "skipped": True}

    rng = random.Random(rng_seed)
    created = 0
    for b in buyers:
        buyer = _upsert_buyer(s, b)
        lates = list(BEHAVIOUR[BUYER_BEHAVIOUR.get(b["code"], "mixed")])
        rng.shuffle(lates)
        for i in range(INVOICES_PER_BUYER):
            inv_date = HISTORY_START + timedelta(days=21 * i + rng.randint(0, 6))
            terms = rng.choice([30, 30, 45])
            acceptance = inv_date + timedelta(days=rng.randint(2, 6))
            due = acceptance + timedelta(days=terms)
            paid_on = due + timedelta(days=lates[i % len(lates)])
            taxable = float(rng.randrange(40_000, 400_000, 500))
            gst = round(taxable * 0.18, 2)
            no = f"SPC/HIST/{b['code']}/{i + 1:03d}"
            inv = Invoice(buyer_id=buyer.id, invoice_no=no, invoice_no_norm=normalize_ref(no),
                          invoice_date=inv_date, amount_taxable=taxable, gst_amount=gst,
                          amount_total=round(taxable + gst, 2), payment_terms_days=terms,
                          due_date=due, status="paid", synthetic=True)
            s.add(inv)
            s.commit()
            s.refresh(inv)
            s.add(PaymentEvent(invoice_id=inv.id, paid_on=paid_on, amount=inv.amount_total))
            created += 1
    s.commit()
    return {"created": created, "removed": removed, "skipped": False}


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Seed synthetic demo history (flagged synthetic).")
    ap.add_argument("--reset", action="store_true", help="delete seeded history first")
    args = ap.parse_args(argv)
    init_db()
    with session_scope() as s:
        out = seed(s, reset=args.reset)
    if out["skipped"]:
        print("Seed history already present; nothing created (use --reset to rebuild).")
    else:
        print(f"Seeded {out['created']} synthetic historical invoices (removed {out['removed']}).")


if __name__ == "__main__":
    main()
