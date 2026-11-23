"""Evidence graph: nodes = documents, edges = match status (BUILD_SPEC §12)."""

from __future__ import annotations

from typing import Any, Optional

from app.fmt import inr
from app.rules.config import get_config
from app.schemas import (
    BaseDoc,
    Check,
    CheckStatus,
    DocType,
    ExtractedPackage,
    Graph,
    GraphEdge,
    GraphNode,
)

# which checks describe the relation between the invoice and each document
EDGE_CHECKS: dict[str, list[str]] = {
    "po": ["C01", "C02", "C03"],
    "challan": ["C05", "C06", "C07", "C08"],
    "eway": ["C09"],
    "grn": ["C10"],
    "contract": ["C11", "C12"],
}
LABELS = {"po": "Purchase order", "challan": "Delivery challan", "eway": "E-way bill",
          "grn": "GRN / acceptance", "contract": "Contract"}


UNSURE = "? (verify)"
DOC_NO_KEYS = ("invoice_no", "po_no", "challan_no", "eway_no", "grn_no", "doc_no")


def doc_confidence(d: BaseDoc) -> float:
    vals = [getattr(d, k).confidence for k, v in d.__class__.model_fields.items()
            if hasattr(getattr(d, k), "confidence") and getattr(d, k).value is not None]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _doc_no(d: Optional[BaseDoc], thr: float) -> Optional[str]:
    """First document number read at or above the threshold (rule 3), else None."""
    if d is None:
        return None
    for key in DOC_NO_KEYS:
        f = getattr(d, key, None)
        if f is not None and f.value and f.confidence >= thr:
            return str(f.value)
    return None


def _doc_no_text(d: Optional[BaseDoc], thr: float) -> str:
    """Label text: a confident number, '? (verify)' if one was read below threshold, else ''."""
    no = _doc_no(d, thr)
    if no:
        return no
    if d is not None and any((f := getattr(d, k, None)) is not None and f.value for k in DOC_NO_KEYS):
        return f"No. {UNSURE}"
    return ""


def build_graph(pkg: ExtractedPackage, checks: list[Check], cfg: Optional[dict[str, Any]] = None) -> Graph:
    if cfg is None:
        cfg = get_config()
    thr = float(cfg["extraction"]["uncertain_below"])
    by_id = {c.check_id: c for c in checks}
    c04 = by_id.get("C04")
    party_bad = set(c04.facts.get("mismatched_nodes", [])) if c04 and c04.status == CheckStatus.fail else set()

    inv = pkg.first(DocType.invoice)
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    inv_bad = any(by_id[c].status == CheckStatus.fail for c in ("C02", "C14") if c in by_id) or "inv" in party_bad
    amount, amount_unsure = "", False
    if inv is not None and inv.total.value is not None:
        amount_unsure = inv.total.confidence < thr
        amount = f"₹{UNSURE}" if amount_unsure else inr(inv.total.value)
    no_text = _doc_no_text(inv, thr)
    inv_label = f"{no_text or 'Invoice'} {amount}".strip()
    inv_status = "mismatch" if inv_bad else "uncertain" if amount_unsure or UNSURE in no_text else "ok"
    nodes.append(GraphNode(id="inv", type="invoice", label=inv_label, status=inv_status,
                           doc_no=_doc_no(inv, thr)))

    eway_required = bool(by_id.get("C09") and by_id["C09"].facts.get("required"))
    for node_id, check_ids in EDGE_CHECKS.items():
        doc = pkg.first(DocType(node_id))
        if doc is None and node_id == "contract":
            continue
        if doc is None and node_id == "eway" and not eway_required:
            continue
        rel = [by_id[c] for c in check_ids if c in by_id]
        statuses = {c.status for c in rel}
        if doc is None:
            n_status, e_status = "missing", "missing"
        elif CheckStatus.fail in statuses or node_id in party_bad:
            n_status, e_status = "mismatch", "mismatch"
        elif CheckStatus.uncertain in statuses:
            n_status, e_status = "uncertain", "uncertain"
        else:
            n_status, e_status = "ok", "matched"
        conf = doc_confidence(doc) if doc else 0.0
        if doc is not None and conf and conf < thr and n_status == "ok":
            n_status, e_status = "uncertain", "uncertain"

        no_text = _doc_no_text(doc, thr)
        label = LABELS[node_id] + (f" {no_text}" if no_text else "")
        nodes.append(GraphNode(id=node_id, type=node_id, label=label, status=n_status,
                               doc_no=_doc_no(doc, thr)))
        bad = [c for c in rel if c.status != CheckStatus.passed and c.severity.value != "info"]
        if node_id in party_bad and c04:
            bad.append(c04)
        note = (bad[0].detail if bad else (rel[0].detail if rel else ""))
        edges.append(GraphEdge(**{"from": "inv"}, to=node_id, status=e_status, confidence=conf,
                               note=note, check_ids=[c.check_id for c in rel]))
    return Graph(nodes=nodes, edges=edges)
