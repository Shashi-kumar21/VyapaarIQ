"""Verification checks C01-C14 (BUILD_SPEC §7). Deterministic, no LLM.

Field states (see ``state``):
  known      value present, confidence >= threshold
  absent     value None, confidence >= threshold   (extractor is sure it is not there)
  uncertain  anything below threshold              (could not read it reliably)

A check that depends on an uncertain field returns ``uncertain`` instead of
guessing pass/fail. A check whose prerequisite document is absent and that is
already flagged by another check returns ``missing`` with severity ``info`` so
the same gap is not penalised twice.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.matching.normalize import (
    desc_similarity,
    gstin_valid,
    normalize_gstin,
    party_similarity,
    refs_match,
)
from app.fmt import inr
from app.rules.config import get_config
from app.rules.due_date import MSMED_CLASSES
from app.schemas import (
    F,
    BaseDoc,
    ChallanDoc,
    Check,
    CheckStatus,
    ContractDoc,
    DocType,
    EwayDoc,
    ExtractedPackage,
    GRNDoc,
    InvoiceDoc,
    PODoc,
    Severity,
)

PASS, FAIL, MISSING, UNCERTAIN = (
    CheckStatus.passed, CheckStatus.fail, CheckStatus.missing, CheckStatus.uncertain,
)
BLOCKER, WARNING, INFO = Severity.blocker, Severity.warning, Severity.info

CHECK_NAMES = {
    "C01": "Invoice ↔ PO reference",
    "C02": "Amount reconciliation",
    "C03": "Line items vs PO",
    "C04": "Party consistency",
    "C05": "Delivery proof exists",
    "C06": "Delivered qty ≥ invoiced qty",
    "C07": "Receiving evidence",
    "C08": "Date logic",
    "C09": "E-way bill",
    "C10": "GRN / acceptance",
    "C11": "Payment terms defined",
    "C12": "Terms ≤ 45 days",
    "C13": "Supplier Udyam present",
    "C14": "Duplicate invoice",
}

# graph node ids used in evidence_refs
NODE = {DocType.invoice: "inv", DocType.po: "po", DocType.challan: "challan",
        DocType.eway: "eway", DocType.grn: "grn", DocType.contract: "contract"}

DuplicateLookup = Callable[[str, Optional[str], Optional[str]], Optional[bool]]


class NoInvoiceError(ValueError):
    """Raised when a package has no invoice document."""


def state(f: F, thr: float) -> str:
    if f.confidence < thr:
        return "uncertain"
    return "known" if f.value is not None else "absent"


def _mk(cid: str, status: CheckStatus, sev: Severity, detail: str,
        refs: list[str], **facts: Any) -> Check:
    return Check(check_id=cid, name=CHECK_NAMES[cid], status=status, severity=sev,
                 detail=detail, evidence_refs=refs, facts=facts)


def _combine(parts: list[CheckStatus]) -> CheckStatus:
    if FAIL in parts:
        return FAIL
    if UNCERTAIN in parts:
        return UNCERTAIN
    return PASS


def _fmt(x: float) -> str:
    return inr(x, paise=True)


class _Ctx:
    def __init__(self, pkg: ExtractedPackage, cfg: dict[str, Any]):
        self.cfg = cfg
        self.thr = float(cfg["extraction"]["uncertain_below"])
        self.tol = cfg["tolerances"]
        inv = pkg.first(DocType.invoice)
        if inv is None:
            raise NoInvoiceError("No invoice found in the package.")
        self.inv: InvoiceDoc = inv
        self.po: Optional[PODoc] = pkg.first(DocType.po)
        self.challan: Optional[ChallanDoc] = pkg.first(DocType.challan)
        self.eway: Optional[EwayDoc] = pkg.first(DocType.eway)
        self.grn: Optional[GRNDoc] = pkg.first(DocType.grn)
        self.contract: Optional[ContractDoc] = pkg.first(DocType.contract)
        self.docs: list[BaseDoc] = list(pkg.documents)

    def st(self, f: F) -> str:
        return state(f, self.thr)

    def num(self, f: F) -> Optional[float]:
        return float(f.value) if self.st(f) == "known" else None


# ---------------------------------------------------------------- C01
def c01(x: _Ctx) -> Check:
    ref = x.inv.po_reference
    s = x.st(ref)
    if s == "uncertain":
        return _mk("C01", UNCERTAIN, BLOCKER, "Could not read the PO reference on the invoice.", ["inv"])
    if s == "absent":
        return _mk("C01", FAIL, BLOCKER, "Invoice does not cite a PO number.", ["inv", "po"])
    if x.po is None:
        return _mk("C01", MISSING, BLOCKER,
                   f"Invoice cites {ref.value} but no PO is in the package.", ["inv", "po"],
                   invoice_po_ref=ref.value)
    po_no = x.po.po_no if x.po.po_no.known else x.po.doc_no
    if x.st(po_no) != "known":
        return _mk("C01", UNCERTAIN, BLOCKER, "Could not read the PO number on the PO.", ["inv", "po"])
    if refs_match(ref.value, po_no.value):
        return _mk("C01", PASS, BLOCKER, f"Invoice PO reference {ref.value} matches the PO.",
                   ["inv", "po"], po_no=po_no.value)
    return _mk("C01", FAIL, BLOCKER,
               f"Invoice cites PO {ref.value} but the PO in the package is {po_no.value}.",
               ["inv", "po"], invoice_po_ref=ref.value, po_no=po_no.value)


# ---------------------------------------------------------------- C02
def c02(x: _Ctx) -> Check:
    inv, parts, notes = x.inv, [], []
    taxable, total = x.num(inv.taxable_value), x.num(inv.total)
    gst_fields = [inv.cgst, inv.sgst, inv.igst]
    gst_unreadable = any(x.st(g) == "uncertain" for g in gst_fields)
    facts: dict[str, Any] = {}

    if taxable is None or total is None or gst_unreadable:
        parts.append(UNCERTAIN)
        notes.append("could not read taxable value, GST or total")
    else:
        gst = sum(x.num(g) or 0.0 for g in gst_fields)
        diff = round(taxable + gst - total, 2)
        facts.update(taxable=taxable, gst=gst, total=total, gst_diff=diff)
        if abs(diff) > float(x.tol["gst_math_inr"]):
            parts.append(FAIL)
            notes.append(f"taxable {_fmt(taxable)} + GST {_fmt(gst)} ≠ total {_fmt(total)} "
                         f"(off by {_fmt(abs(diff))})")
        else:
            parts.append(PASS)

    if x.po is not None:
        po_total = x.num(x.po.po_total)
        if po_total is None or taxable is None:
            parts.append(UNCERTAIN)
            notes.append("could not compare against the PO value")
        else:
            limit = po_total * (1 + float(x.tol["po_value_pct"]) / 100)
            facts.update(po_total=po_total)
            if taxable > limit:
                parts.append(FAIL)
                notes.append(f"invoice taxable {_fmt(taxable)} exceeds PO value {_fmt(po_total)} "
                             f"by {(taxable / po_total - 1) * 100:.1f}%")
            else:
                parts.append(PASS)

    status = _combine(parts)
    if status == PASS:
        detail = "Totals reconcile" + (" and are within the PO value." if x.po else ".")
    else:
        joined = "; ".join(notes)
        detail = joined[:1].upper() + joined[1:] + "."
    return _mk("C02", status, BLOCKER, detail, ["inv", "po"] if x.po else ["inv"], **facts)


# ---------------------------------------------------------------- line matching
def _match_items(src: list, dst: list, min_sim: float = 0.80) -> list[tuple[Any, Any]]:
    """Greedy best match of src items to dst items by description."""
    pairs, used = [], set()
    for a in src:
        best, best_j = 0.0, None
        for j, b in enumerate(dst):
            if j in used:
                continue
            sim = desc_similarity(a.desc, b.desc)
            if sim > best:
                best, best_j = sim, j
        if best_j is not None and best >= min_sim:
            used.add(best_j)
            pairs.append((a, dst[best_j]))
        else:
            pairs.append((a, None))
    return pairs


# ---------------------------------------------------------------- C03
def c03(x: _Ctx) -> Check:
    if x.po is None:
        return _mk("C03", MISSING, INFO, "Skipped: no PO in the package (see C01).", ["inv", "po"])
    if x.st(x.inv.line_items) != "known" or x.st(x.po.line_items) != "known":
        return _mk("C03", UNCERTAIN, WARNING, "Could not read line items on the invoice or PO.",
                   ["inv", "po"])
    qty_tol, rate_tol = float(x.tol["line_qty_pct"]), float(x.tol["line_rate_pct"])
    issues, worst = [], 0.0
    for it, po_it in _match_items(x.inv.line_items.value, x.po.line_items.value):
        if po_it is None:
            issues.append(f"'{it.desc}' is not on the PO")
            worst = max(worst, 100.0)
            continue
        if it.qty is not None and po_it.qty:
            dev = (it.qty / po_it.qty - 1) * 100
            if dev > qty_tol:
                issues.append(f"'{it.desc}' qty {it.qty:g} vs PO {po_it.qty:g}")
                worst = max(worst, dev)
        if it.rate is not None and po_it.rate:
            dev = (it.rate / po_it.rate - 1) * 100
            if dev > rate_tol:
                issues.append(f"'{it.desc}' rate {_fmt(it.rate)} vs PO {_fmt(po_it.rate)} (+{dev:.1f}%)")
                worst = max(worst, dev)
    if not issues:
        return _mk("C03", PASS, WARNING, "Invoice line items match the PO.", ["inv", "po"])
    sev = BLOCKER if worst > float(x.tol["line_blocker_pct"]) else WARNING
    return _mk("C03", FAIL, sev, "Line items differ from the PO: " + "; ".join(issues) + ".",
               ["inv", "po"], max_deviation_pct=round(worst, 2), issues=issues)


# ---------------------------------------------------------------- C04
def c04(x: _Ctx) -> Check:
    inv = x.inv
    name_s, gst_s = x.st(inv.buyer_name), x.st(inv.buyer_gstin)
    if name_s == "uncertain" and gst_s == "uncertain":
        return _mk("C04", UNCERTAIN, BLOCKER, "Could not read the buyer on the invoice.", ["inv"])
    ratio_min = float(x.tol["party_fuzzy_ratio"])
    issues, mismatched, uncertain_docs, compared = [], [], [], 0

    if gst_s == "known" and not gstin_valid(inv.buyer_gstin.value):
        issues.append(f"invoice buyer GSTIN {inv.buyer_gstin.value} fails format/checksum")
        mismatched.append("inv")

    for d in x.docs:
        if d is inv or d.doc_type in (DocType.other, DocType.contract):
            continue
        node = NODE[d.doc_type]
        d_gst_s, d_name_s = x.st(d.buyer_gstin), x.st(d.buyer_name)
        if gst_s == "known" and d_gst_s == "known":
            compared += 1
            if normalize_gstin(d.buyer_gstin.value) != normalize_gstin(inv.buyer_gstin.value):
                issues.append(f"buyer GSTIN on {d.doc_type.value} ({d.buyer_gstin.value}) ≠ "
                              f"invoice ({inv.buyer_gstin.value})")
                mismatched.append(node)
                continue
        if name_s == "known" and d_name_s == "known":
            compared += 1
            sim = party_similarity(inv.buyer_name.value, d.buyer_name.value)
            if sim < ratio_min:
                issues.append(f"buyer name on {d.doc_type.value} '{d.buyer_name.value}' ≠ "
                              f"invoice '{inv.buyer_name.value}' (similarity {sim:.2f})")
                mismatched.append(node)
        elif "uncertain" in (d_gst_s, d_name_s):
            uncertain_docs.append(node)

    refs = ["inv"] + sorted({NODE[d.doc_type] for d in x.docs if d.doc_type in NODE} - {"inv"})
    if issues:
        return _mk("C04", FAIL, BLOCKER, "Buyer details differ: " + "; ".join(issues) + ".", refs,
                   mismatched_nodes=sorted(set(mismatched)))
    if compared == 0 and uncertain_docs:
        return _mk("C04", UNCERTAIN, BLOCKER, "Could not compare buyer details across documents.", refs)
    return _mk("C04", PASS, BLOCKER, "Buyer name and GSTIN are consistent across documents.", refs,
               uncertain_nodes=uncertain_docs)


# ---------------------------------------------------------------- C05
def c05(x: _Ctx) -> Check:
    if x.challan is None:
        return _mk("C05", MISSING, BLOCKER, "No delivery challan / LR in the package.", ["challan"])
    return _mk("C05", PASS, BLOCKER, "Delivery challan present.", ["challan"])


# ---------------------------------------------------------------- C06
def c06(x: _Ctx) -> Check:
    if x.challan is None:
        return _mk("C06", MISSING, INFO, "Skipped: no delivery challan (see C05).", ["inv", "challan"])
    if x.st(x.inv.line_items) != "known" or x.st(x.challan.line_items) != "known":
        return _mk("C06", UNCERTAIN, BLOCKER, "Could not read line items on the invoice or challan.",
                   ["inv", "challan"])
    short = []
    for it, ch in _match_items(x.inv.line_items.value, x.challan.line_items.value):
        if ch is None:
            short.append(f"'{it.desc}' not on the challan")
        elif it.qty is not None and ch.qty is not None and ch.qty < it.qty:
            short.append(f"'{it.desc}' delivered {ch.qty:g} < invoiced {it.qty:g}")
    if short:
        return _mk("C06", FAIL, BLOCKER, "Delivered quantity short: " + "; ".join(short) + ".",
                   ["inv", "challan"], short=short)
    return _mk("C06", PASS, BLOCKER, "Delivered quantities cover the invoice.", ["inv", "challan"])


# ---------------------------------------------------------------- C07
def c07(x: _Ctx) -> Check:
    ch = x.challan
    if ch is None:
        return _mk("C07", MISSING, INFO, "Skipped: no delivery challan (see C05).", ["challan"])
    stamp, sign = ch.received_stamp_present, ch.received_signature_present
    if x.st(stamp) == "known" and stamp.value or x.st(sign) == "known" and sign.value:
        who = f" by {ch.received_by_name.value}" if ch.received_by_name.known else ""
        return _mk("C07", PASS, WARNING, f"Challan carries receiver stamp/signature{who}.", ["challan"])
    if "uncertain" in (x.st(stamp), x.st(sign)):
        return _mk("C07", UNCERTAIN, WARNING, "Could not confirm a receiver stamp or signature.", ["challan"])
    return _mk("C07", FAIL, WARNING, "Challan has no receiver stamp or signature.", ["challan"])


# ---------------------------------------------------------------- C08
def c08(x: _Ctx) -> Check:
    if x.st(x.inv.invoice_date) != "known":
        return _mk("C08", UNCERTAIN, WARNING, "Could not read the invoice date.", ["inv"])
    inv_d = x.inv.invoice_date.value
    issues, parts, refs = [], [], ["inv"]
    if x.challan is not None:
        refs.append("challan")
        if x.st(x.challan.challan_date) == "known":
            lag = (x.challan.challan_date.value - inv_d).days
            if lag > int(x.tol["challan_after_invoice_days"]):
                issues.append(f"challan dated {lag} days after the invoice")
                parts.append(FAIL)
        else:
            parts.append(UNCERTAIN)
    if x.po is not None:
        refs.append("po")
        if x.st(x.po.po_date) == "known":
            if x.po.po_date.value > inv_d:
                issues.append("PO is dated after the invoice")
                parts.append(FAIL)
        else:
            parts.append(UNCERTAIN)
    status = _combine(parts)
    detail = {PASS: "Document dates are in a plausible order.",
              UNCERTAIN: "Could not read every date to verify the order."}.get(
        status, "Date order issue: " + "; ".join(issues) + ".")
    return _mk("C08", status, WARNING, detail, refs)


# ---------------------------------------------------------------- C09
def c09(x: _Ctx) -> Check:
    taxable = x.num(x.inv.taxable_value)
    gst_s = [x.st(g) for g in (x.inv.cgst, x.inv.sgst, x.inv.igst)]
    if taxable is None or "uncertain" in gst_s:
        value = x.num(x.inv.total)
    else:
        value = taxable + sum(x.num(g) or 0.0 for g in (x.inv.cgst, x.inv.sgst, x.inv.igst))
    threshold = float(x.cfg["eway"]["threshold_inr"])
    if value is None:
        return _mk("C09", UNCERTAIN, WARNING, "Could not read the invoice value.", ["inv", "eway"])
    if value <= threshold:
        return _mk("C09", PASS, WARNING, f"Goods value {_fmt(value)} is below the e-way threshold.",
                   ["inv"], value=value, required=False)
    if x.eway is None:
        return _mk("C09", FAIL, WARNING,
                   f"Goods value {_fmt(value)} exceeds {_fmt(threshold)} but no e-way bill is in the package.",
                   ["inv", "eway"], value=value, required=True)
    ref = x.eway.invoice_reference
    if x.st(ref) == "uncertain" or x.st(x.inv.invoice_no) != "known":
        return _mk("C09", UNCERTAIN, WARNING, "Could not read the invoice reference on the e-way bill.",
                   ["inv", "eway"], required=True)
    if ref.known and not refs_match(ref.value, x.inv.invoice_no.value):
        return _mk("C09", FAIL, WARNING,
                   f"E-way bill cites invoice {ref.value}, not {x.inv.invoice_no.value}.",
                   ["inv", "eway"], required=True)
    return _mk("C09", PASS, WARNING, "E-way bill present and references this invoice.",
               ["inv", "eway"], value=value, required=True)


# ---------------------------------------------------------------- C10
def c10(x: _Ctx) -> Check:
    if x.grn is None:
        return _mk("C10", MISSING, BLOCKER,
                   "No GRN or written acceptance from the buyer. Acceptance can only be deemed, "
                   "which weakens the payment claim.", ["grn"])
    when = f" dated {x.grn.grn_date.value.isoformat()}" if x.st(x.grn.grn_date) == "known" else ""
    return _mk("C10", PASS, BLOCKER, f"Buyer GRN / acceptance present{when}.", ["grn"])


# ---------------------------------------------------------------- terms helpers
def governing_terms(x: _Ctx) -> tuple[Optional[int], str, bool, Optional[str]]:
    """(days, source, any_uncertain, text_source). Contract > PO > invoice.

    Terms text without a readable number of days counts as uncertain days.
    """
    any_unc, text_src = False, None
    for doc, src in ((x.contract, "contract"), (x.po, "po"), (x.inv, "invoice")):
        if doc is None:
            continue
        s = x.st(doc.payment_terms_days)
        if s == "known":
            return int(doc.payment_terms_days.value), src, any_unc, text_src
        if x.st(doc.payment_terms_text) == "known":
            text_src = text_src or src
            any_unc = True
        any_unc = any_unc or s == "uncertain"
    return None, "", any_unc, text_src


# ---------------------------------------------------------------- C11
_SRC_LABEL = {"po": "PO", "invoice": "invoice", "contract": "contract"}


def c11(x: _Ctx) -> Check:
    days, src, unc, text_src = governing_terms(x)
    if days is not None:
        return _mk("C11", PASS, WARNING, f"Written payment terms found on the {_SRC_LABEL.get(src, src)}: {days} days.",
                   [NODE[DocType(src)]], terms_days=days, source=src)
    if text_src:
        return _mk("C11", PASS, WARNING,
                   f"Written payment terms found on the {_SRC_LABEL.get(text_src, text_src)}, but the number of days is unclear.",
                   [NODE[DocType(text_src)]], source=text_src)
    if unc:
        return _mk("C11", UNCERTAIN, WARNING, "Could not read the payment terms.", ["inv"])
    n = x.cfg["msmed"]["no_agreement_days"]
    return _mk("C11", FAIL, WARNING,
               f"No written payment terms found; the MSMED {n}-day default would apply.", ["inv"])


# ---------------------------------------------------------------- C12
def c12(x: _Ctx) -> Check:
    days, src, unc, _ = governing_terms(x)
    limit = int(x.cfg["msmed"]["max_terms_days"])
    cls = str(x.cfg["supplier"]["enterprise_class"]).lower()
    if cls not in MSMED_CLASSES:
        return _mk("C12", PASS, WARNING, f"Not applicable to a {cls} enterprise.", [])
    if days is None:
        status = UNCERTAIN if unc else PASS
        return _mk("C12", status, WARNING, "No readable written terms (see C11).", ["inv"])
    if days > limit:
        return _mk("C12", FAIL, WARNING,
                   f"Terms of {days} days on the {src} exceed {limit} days; potentially "
                   f"non-compliant with MSMED s.15 (payment is still due within {limit} days of acceptance).",
                   [NODE[DocType(src)]], terms_days=days)
    return _mk("C12", PASS, WARNING, f"Terms of {days} days are within {limit} days.",
               [NODE[DocType(src)]], terms_days=days)


# ---------------------------------------------------------------- C13
def c13(x: _Ctx) -> Check:
    states = [x.st(d.supplier_udyam) for d in x.docs
              if d.doc_type in (DocType.invoice, DocType.challan, DocType.eway)]
    if "known" in states:
        u = next(d.supplier_udyam.value for d in x.docs if x.st(d.supplier_udyam) == "known")
        return _mk("C13", PASS, INFO, f"Supplier Udyam number {u} present.", ["inv"], udyam=u)
    if x.st(x.inv.supplier_udyam) == "uncertain":
        return _mk("C13", UNCERTAIN, INFO, "Could not read a Udyam number on the invoice.", ["inv"])
    return _mk("C13", FAIL, INFO,
               "No Udyam registration number on supplier documents; MSMED protections depend on registration.",
               ["inv"])


# ---------------------------------------------------------------- C14
def c14(x: _Ctx, lookup: Optional[DuplicateLookup]) -> Check:
    no = x.inv.invoice_no if x.inv.invoice_no.known else x.inv.doc_no
    if x.st(no) != "known":
        return _mk("C14", UNCERTAIN, BLOCKER, "Could not read the invoice number.", ["inv"])
    if lookup is None:
        return _mk("C14", PASS, BLOCKER, "Not checked against history (no lookup available).", ["inv"])
    # Only confidently read buyer details narrow the match (rule 3).
    gstin = x.inv.buyer_gstin.value if x.st(x.inv.buyer_gstin) == "known" else None
    name = x.inv.buyer_name.value if x.st(x.inv.buyer_name) == "known" else None
    dup = lookup(no.value, gstin, name)
    if dup:
        return _mk("C14", FAIL, BLOCKER,
                   f"Invoice {no.value} already exists for this buyer.", ["inv"], invoice_no=no.value)
    return _mk("C14", PASS, BLOCKER, f"Invoice {no.value} is not a duplicate.", ["inv"])


# ---------------------------------------------------------------- entry point
def run_checks(pkg: ExtractedPackage, *, duplicate_lookup: Optional[DuplicateLookup] = None,
               cfg: Optional[dict[str, Any]] = None) -> list[Check]:
    x = _Ctx(pkg, get_config() if cfg is None else cfg)
    return [c01(x), c02(x), c03(x), c04(x), c05(x), c06(x), c07(x), c08(x), c09(x),
            c10(x), c11(x), c12(x), c13(x), c14(x, duplicate_lookup)]
