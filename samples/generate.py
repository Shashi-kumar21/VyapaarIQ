"""Synthetic invoice-package generator (BUILD_SPEC §14).

Writes PDFs to ``samples/out/<PKG>/`` and ``samples/ground_truth.json`` with the
true field values, injected defects and the expected check outcome per package.

Ground truth is computed here, independently of the backend, so the eval can
catch backend bugs. All companies are fictional.

    python samples/generate.py            # default 28 packages, seed 42
    python samples/generate.py --seed 7
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
GT_PATH = ROOT / "ground_truth.json"

GST_RATE = 0.18
EWAY_THRESHOLD = 50000
DEEMED_OFFSET = 15
MAX_TERMS = 45
NO_TERMS_DAYS = 15
ALL_CHECKS = [f"C{i:02d}" for i in range(1, 15)]

# --------------------------------------------------------------------------
# GSTIN helpers (self-contained on purpose; do not import the backend)
# --------------------------------------------------------------------------
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        prod = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return _CHARS[(36 - total % 36) % 36]


def make_gstin(state: str, pan: str, entity: str = "1") -> str:
    base = f"{state}{pan}{entity}Z"
    return base + gstin_checksum(base)


# --------------------------------------------------------------------------
# Fictional parties and catalogue
# --------------------------------------------------------------------------
SUPPLIER = {
    "name": "Shakti Precision Components Pvt Ltd",
    "gstin": make_gstin("27", "AAECS4821K"),
    "udyam": "UDYAM-MH-26-0048213",
    "address": "Plot 14, MIDC Bhosari, Pune 411026, Maharashtra",
    "enterprise_class": "small",
}

BUYERS = [
    {"code": "KAA", "name": "Kaveri Auto Assemblies Pvt Ltd", "alt": "Kaveri Auto Assemblies Private Limited",
     "gstin": make_gstin("27", "AABCK7712M"), "city": "Chakan, Pune, Maharashtra"},
    {"code": "NEW", "name": "Narmada Engineering Works Ltd", "alt": "Narmada Engineering Works Limited",
     "gstin": make_gstin("24", "AACCN3390P"), "city": "Vadodara, Gujarat"},
    {"code": "DAM", "name": "Deccan Agro Machines Pvt Ltd", "alt": "Deccan Agro Machines Pvt. Ltd.",
     "gstin": make_gstin("36", "AAFCD5521Q"), "city": "Medchal, Hyderabad, Telangana"},
    {"code": "SPV", "name": "Sahyadri Pumps & Valves LLP", "alt": "Sahyadri Pumps and Valves LLP",
     "gstin": make_gstin("27", "ABEFS8834R"), "city": "Satara, Maharashtra"},
    {"code": "GEL", "name": "Ganga Electricals Pvt Ltd", "alt": "Ganga Electricals Private Limited",
     "gstin": make_gstin("09", "AAGCG1209L"), "city": "Noida, Uttar Pradesh"},
    {"code": "VIP", "name": "Vindhya Infra Projects Ltd", "alt": "Vindhya Infra Projects Limited",
     "gstin": make_gstin("23", "AAHCV6650N"), "city": "Indore, Madhya Pradesh"},
]

CATALOGUE = [
    ("MS Flange 4 inch", "7307", "Nos", 420.0),
    ("SS Hex Bolt M12x50", "7318", "Nos", 18.5),
    ("Bearing Housing BH-208", "8483", "Nos", 1250.0),
    ("Gear Blank 60T", "8483", "Nos", 2100.0),
    ("Pump Impeller 150mm", "8413", "Nos", 3400.0),
    ("CNC Machined Shaft 40mm", "8483", "Nos", 1850.0),
    ("Gasket Set GS-12", "4016", "Set", 260.0),
    ("Coupling Sleeve CS-50", "8483", "Nos", 780.0),
]

# defect plan: each defect >= 2 times, >= 5 clean, two combined packages
PLAN: list[list[str]] = (
    [["clean"]] * 6
    + [["missing_grn"]] * 2
    + [["missing_challan"]] * 2
    + [["qty_short"]] * 2
    + [["invoice_gt_po"]] * 2
    + [["party_mismatch"]] * 2
    + [["missing_po_ref"]] * 2
    + [["terms_gt_45"]] * 2
    + [["no_stamp"]] * 2
    + [["duplicate_invoice"]] * 2
    + [["wrong_gst_math"]] * 2
    + [["missing_grn", "no_stamp"], ["terms_gt_45", "missing_po_ref"]]
)

# expected non-pass statuses per defect (everything else expected "pass")
DEFECT_EXPECT: dict[str, dict[str, str]] = {
    "clean": {},
    "missing_grn": {"C10": "missing"},
    "missing_challan": {"C05": "missing", "C06": "missing", "C07": "missing"},
    "qty_short": {"C06": "fail"},
    "invoice_gt_po": {"C02": "fail", "C03": "fail"},
    "party_mismatch": {"C04": "fail"},
    "missing_po_ref": {"C01": "fail"},
    "terms_gt_45": {"C12": "fail"},
    "no_stamp": {"C07": "fail"},
    "duplicate_invoice": {"C14": "fail"},
    "wrong_gst_math": {"C02": "fail"},
}
BLOCKER_CHECKS = {"C01", "C02", "C04", "C05", "C06", "C10", "C14"}


# --------------------------------------------------------------------------
# Package model
# --------------------------------------------------------------------------
@dataclass
class Pkg:
    pid: str
    defects: list[str]
    buyer: dict
    style: int
    scan_docs: list[str] = field(default_factory=list)
    docs: dict[str, dict] = field(default_factory=dict)  # doc_type -> true fields


def fmt_date(d: date, style: int) -> str:
    return [d.strftime("%d-%m-%Y"), d.strftime("%d/%m/%Y"), d.strftime("%d %b %Y")][style % 3]


def inr(x: float) -> str:
    """Indian digit grouping, 2 decimals, no symbol (Rs 2,40,000.00)."""
    neg = x < 0
    whole, frac = f"{abs(x):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if neg else "") + whole + "." + frac


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def build_package(i: int, defects: list[str], rng: random.Random, base: date,
                  issued: list[dict]) -> Pkg:
    pid = f"PKG{i + 1:02d}"
    buyer = BUYERS[i % len(BUYERS)]
    p = Pkg(pid=pid, defects=defects, buyer=buyer, style=i % 3)
    intra = buyer["gstin"][:2] == SUPPLIER["gstin"][:2]

    # ---- line items (PO = truth of what was ordered)
    n_items = rng.randint(2, 4)
    items = []
    for desc, hsn, unit, rate in rng.sample(CATALOGUE, n_items):
        qty = float(rng.choice([10, 20, 25, 40, 50, 60, 80, 100, 120, 150, 200, 250]))
        items.append({"desc": desc, "hsn": hsn, "unit": unit, "qty": qty, "rate": rate,
                      "amount": r2(qty * rate)})
    po_total = r2(sum(x["amount"] for x in items))

    terms = rng.choice([30, 30, 45, 21])
    if "terms_gt_45" in defects:
        terms = rng.choice([60, 90])
    terms_text = f"Net {terms} days from date of acceptance of goods"

    po_date = base + timedelta(days=i * 2 + rng.randint(0, 3))
    inv_date = po_date + timedelta(days=rng.randint(5, 12))
    challan_date = inv_date + timedelta(days=rng.randint(0, 1))
    received_date = challan_date + timedelta(days=rng.randint(1, 3))
    grn_date = received_date + timedelta(days=rng.randint(1, 4))

    po_no = f"{buyer['code']}/PO/2627/{1100 + i * 7}"

    # ---- invoice lines (copy of PO unless a defect changes them)
    inv_items = [dict(x) for x in items]
    if "invoice_gt_po" in defects:
        j = max(range(len(inv_items)), key=lambda k: inv_items[k]["amount"])
        inv_items[j]["rate"] = r2(inv_items[j]["rate"] * 1.08)
        inv_items[j]["amount"] = r2(inv_items[j]["qty"] * inv_items[j]["rate"])
    taxable = r2(sum(x["amount"] for x in inv_items))
    if intra:
        cgst = sgst = r2(taxable * GST_RATE / 2)
        igst = 0.0
    else:
        cgst = sgst = 0.0
        igst = r2(taxable * GST_RATE)
    true_total = total = r2(taxable + cgst + sgst + igst)
    if "wrong_gst_math" in defects:
        total = r2(total + rng.choice([1800.0, 2500.0, -1200.0]))

    if "duplicate_invoice" in defects:
        prev = next((x for x in reversed(issued) if x["buyer"] == buyer["code"]), None)
        invoice_no = prev["invoice_no"] if prev else f"SPC/26-27/{101 + i:04d}"
    else:
        invoice_no = f"SPC/26-27/{101 + i:04d}"
    issued.append({"buyer": buyer["code"], "invoice_no": invoice_no})

    inv_buyer_name, inv_buyer_gstin = buyer["name"], buyer["gstin"]
    if "party_mismatch" in defects:
        if i % 2 == 0:  # GSTIN typo: one digit changed, checksum recomputed
            g = buyer["gstin"]
            d = str((int(g[7]) + 3) % 10)  # g[7] is the first PAN digit
            inv_buyer_gstin = make_gstin(g[:2], g[2:7] + d + g[8:12], g[12])
        else:  # a different legal entity name
            inv_buyer_name = buyer["name"].split()[0] + " Motors & Traders Pvt Ltd"

    common = {
        "supplier_name": SUPPLIER["name"], "supplier_gstin": SUPPLIER["gstin"],
        "supplier_udyam": SUPPLIER["udyam"],
    }
    p.docs["po"] = {
        **common, "supplier_udyam": None,
        "doc_no": po_no, "doc_date": po_date.isoformat(),
        "buyer_name": buyer["alt"], "buyer_gstin": buyer["gstin"],
        "po_reference": po_no, "po_no": po_no, "po_date": po_date.isoformat(),
        "line_items": items, "po_total": po_total,
        "delivery_date": (po_date + timedelta(days=14)).isoformat(),
        "payment_terms_text": terms_text, "payment_terms_days": terms,
    }
    p.docs["invoice"] = {
        **common,
        "doc_no": invoice_no, "doc_date": inv_date.isoformat(),
        "buyer_name": inv_buyer_name, "buyer_gstin": inv_buyer_gstin,
        "po_reference": None if "missing_po_ref" in defects else po_no,
        "invoice_no": invoice_no, "invoice_date": inv_date.isoformat(),
        "line_items": inv_items, "taxable_value": taxable,
        "cgst": cgst, "sgst": sgst, "igst": igst, "total": total,
        "payment_terms_text": terms_text, "payment_terms_days": terms,
        "due_date_text": None, "irn": hashlib.sha256(invoice_no.encode()).hexdigest()[:64],
        "bank_details_present": True,
    }

    if "missing_challan" not in defects:
        ch_items = [{"desc": x["desc"], "qty": x["qty"]} for x in inv_items]
        if "qty_short" in defects:
            ch_items[0]["qty"] = float(max(1, int(ch_items[0]["qty"] * 0.8)))
        stamped = "no_stamp" not in defects
        p.docs["challan"] = {
            **common, "supplier_udyam": None,
            "doc_no": f"DC/26-27/{301 + i:04d}", "doc_date": challan_date.isoformat(),
            "buyer_name": buyer["name"], "buyer_gstin": buyer["gstin"], "po_reference": po_no,
            "challan_no": f"DC/26-27/{301 + i:04d}", "challan_date": challan_date.isoformat(),
            "invoice_reference": invoice_no, "line_items": ch_items,
            "vehicle_no": f"MH12{chr(65 + i % 26)}{chr(66 + i % 24)}{4000 + i * 37}",
            "received_by_name": rng.choice(["R. Patil", "S. Kulkarni", "A. Shaikh", "M. Reddy"]) if stamped else None,
            "received_stamp_present": stamped, "received_signature_present": stamped,
            "received_date": received_date.isoformat() if stamped else None,
        }

    if true_total > EWAY_THRESHOLD:  # consignment value incl. GST
        p.docs["eway"] = {
            **common, "supplier_udyam": None,
            "doc_no": f"{rng.randint(10**11, 10**12 - 1)}", "doc_date": challan_date.isoformat(),
            "buyer_name": buyer["name"], "buyer_gstin": buyer["gstin"], "po_reference": None,
            "eway_no": None, "generated_date": challan_date.isoformat(),
            "invoice_reference": invoice_no, "value": true_total,
            "vehicle_no": p.docs.get("challan", {}).get("vehicle_no", f"MH14ZX{5000 + i}"),
            "valid_until": (challan_date + timedelta(days=3)).isoformat(),
        }
        p.docs["eway"]["eway_no"] = p.docs["eway"]["doc_no"]

    if "missing_grn" not in defects:
        grn_items = [{"desc": c["desc"], "qty_received": c["qty"], "qty_accepted": c["qty"]}
                     for c in (p.docs.get("challan", {}).get("line_items")
                               or [{"desc": x["desc"], "qty": x["qty"]} for x in inv_items])]
        p.docs["grn"] = {
            **common, "supplier_udyam": None,
            "doc_no": f"GRN-{buyer['code']}-{7700 + i * 3}", "doc_date": grn_date.isoformat(),
            "buyer_name": buyer["name"], "buyer_gstin": buyer["gstin"], "po_reference": po_no,
            "grn_no": f"GRN-{buyer['code']}-{7700 + i * 3}", "grn_date": grn_date.isoformat(),
            "invoice_reference": invoice_no, "line_items": grn_items,
            "accepted_by": rng.choice(["Stores In-charge", "QC Supervisor", "Receiving Officer"]),
            "remarks": "Accepted" if "qty_short" not in defects else "Accepted qty as received",
        }
    return p


def expected(p: Pkg) -> dict:
    exp = {c: "pass" for c in ALL_CHECKS}
    for d in p.defects:
        exp.update(DEFECT_EXPECT[d])
    # when the challan is missing and C07 was also defected, missing wins
    if "missing_challan" in p.defects:
        exp["C07"] = "missing"

    grn = p.docs.get("grn")
    ch = p.docs.get("challan")
    if grn:
        acc, basis = date.fromisoformat(grn["grn_date"]), "grn"
    elif ch and ch.get("received_date"):
        acc, basis = date.fromisoformat(ch["received_date"]), "challan_received"
    elif ch:
        acc, basis = date.fromisoformat(ch["challan_date"]) + timedelta(days=DEEMED_OFFSET), "deemed"
    else:
        acc, basis = None, "unknown"
    terms = p.docs["invoice"]["payment_terms_days"]
    due = acc + timedelta(days=min(terms, MAX_TERMS)) if acc else None
    return {
        "checks": exp,
        "has_blocker": any(exp[c] != "pass" for c in BLOCKER_CHECKS),
        "acceptance_basis": basis,
        "acceptance_date": acc.isoformat() if acc else None,
        "due_date": due.isoformat() if due else None,
    }


# --------------------------------------------------------------------------
# PDF rendering
# --------------------------------------------------------------------------
FONTS = [("Helvetica", "Helvetica-Bold"), ("Times-Roman", "Times-Bold"), ("Courier", "Courier-Bold")]
TITLES = {"invoice": "TAX INVOICE", "po": "PURCHASE ORDER", "challan": "DELIVERY CHALLAN",
          "eway": "E-WAY BILL", "grn": "GOODS RECEIPT NOTE"}


class Doc:
    def __init__(self, style: int):
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4, invariant=1)
        self.font, self.bold = FONTS[style % 3]
        self.size = 10 if style != 2 else 9
        self.y = A4[1] - 50
        self.x = 45 + style * 5

    def line(self, text: str, bold: bool = False, dx: float = 0, gap: float = 15, size: float | None = None):
        self.c.setFont(self.bold if bold else self.font, size or self.size)
        self.c.drawString(self.x + dx, self.y, text)
        self.y -= gap

    def row(self, cols: list[str], xs: list[float], bold: bool = False):
        self.c.setFont(self.bold if bold else self.font, self.size - 1)
        for text, x in zip(cols, xs):
            self.c.drawString(self.x + x, self.y, text)
        self.y -= 14

    def stamp(self, text: str):
        self.c.saveState()
        self.c.setStrokeColorRGB(0.1, 0.2, 0.7)
        self.c.setFillColorRGB(0.1, 0.2, 0.7)
        self.c.translate(380, self.y + 20)
        self.c.rotate(8)
        self.c.roundRect(0, 0, 150, 48, 6)
        self.c.setFont("Helvetica-Bold", 9)
        for k, t in enumerate(text.split("\n")):
            self.c.drawString(8, 34 - k * 12, t)
        self.c.restoreState()

    def bytes(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def render(p: Pkg, doc_type: str) -> bytes:
    d = p.docs[doc_type]
    s = p.style
    f = lambda k: fmt_date(date.fromisoformat(d[k]), s) if d.get(k) else ""  # noqa: E731
    doc = Doc(s)
    sup = SUPPLIER
    is_supplier_doc = doc_type in ("invoice", "challan", "eway")

    if is_supplier_doc:
        doc.line(sup["name"], bold=True, size=13, gap=14)
        doc.line(sup["address"], gap=13)
        doc.line(f"GSTIN: {sup['gstin']}", gap=13)
        if doc_type == "invoice":
            doc.line(f"Udyam Registration No: {sup['udyam']}", gap=13)
    else:
        doc.line(d["buyer_name"], bold=True, size=13, gap=14)
        doc.line(p.buyer["city"], gap=13)
        doc.line(f"GSTIN: {d['buyer_gstin']}", gap=13)
    doc.y -= 6
    doc.line(TITLES[doc_type], bold=True, size=14, gap=22, dx=170)

    if doc_type == "invoice":
        label_no = ["Invoice No", "Invoice Number", "Inv. No."][s]
        doc.line(f"{label_no}: {d['invoice_no']}")
        doc.line(f"Invoice Date: {f('invoice_date')}")
        if d["po_reference"]:
            doc.line(f"{['Buyer PO No', 'PO Ref', 'Order Reference'][s]}: {d['po_reference']}")
        doc.line(f"IRN: {d['irn'][:32]}...", size=7, gap=13)
        doc.y -= 4
        doc.line("Bill To:", bold=True)
        doc.line(d["buyer_name"])
        doc.line(f"Buyer GSTIN: {d['buyer_gstin']}")
    elif doc_type == "po":
        doc.line(f"PO No: {d['po_no']}")
        doc.line(f"PO Date: {f('po_date')}")
        doc.line(f"Delivery By: {f('delivery_date')}")
        doc.y -= 4
        doc.line("Vendor:", bold=True)
        doc.line(d["supplier_name"])
        doc.line(f"Vendor GSTIN: {d['supplier_gstin']}")
    elif doc_type == "challan":
        doc.line(f"Challan No: {d['challan_no']}")
        doc.line(f"Challan Date: {f('challan_date')}")
        doc.line(f"Against Invoice No: {d['invoice_reference']}")
        doc.line(f"PO Ref: {d['po_reference']}")
        doc.line(f"Vehicle No: {d['vehicle_no']}")
        doc.y -= 4
        doc.line("Consignee:", bold=True)
        doc.line(d["buyer_name"])
        doc.line(f"Consignee GSTIN: {d['buyer_gstin']}")
    elif doc_type == "eway":
        doc.line(f"E-Way Bill No: {d['eway_no']}")
        doc.line(f"Generated Date: {f('generated_date')}")
        doc.line(f"Valid Upto: {f('valid_until')}")
        doc.line(f"Document No (Invoice): {d['invoice_reference']}")
        doc.line(f"Value of Goods: {inr(d['value'])}")
        doc.line(f"Vehicle No: {d['vehicle_no']}")
        doc.line(f"Recipient: {d['buyer_name']}")
        doc.line(f"Recipient GSTIN: {d['buyer_gstin']}")
    elif doc_type == "grn":
        doc.line(f"GRN No: {d['grn_no']}")
        doc.line(f"GRN Date: {f('grn_date')}")
        doc.line(f"PO Ref: {d['po_reference']}")
        doc.line(f"Supplier Invoice No: {d['invoice_reference']}")
        doc.line(f"Supplier: {d['supplier_name']}")
        doc.line(f"Supplier GSTIN: {d['supplier_gstin']}")

    # ---- line items table
    doc.y -= 8
    items = d.get("line_items") or []
    if doc_type in ("invoice", "po"):
        xs = [0, 28, 210, 260, 310, 350, 420]
        doc.row(["#", "Description", "HSN", "Qty", "Unit", "Rate", "Amount"], xs, bold=True)
        for k, it in enumerate(items, 1):
            doc.row([str(k), it["desc"], it["hsn"], f"{it['qty']:g}", it["unit"],
                     inr(it["rate"]), inr(it["amount"])], xs)
    elif doc_type == "challan":
        xs = [0, 28, 260]
        doc.row(["#", "Description", "Qty Dispatched"], xs, bold=True)
        for k, it in enumerate(items, 1):
            doc.row([str(k), it["desc"], f"{it['qty']:g}"], xs)
    elif doc_type == "grn":
        xs = [0, 28, 250, 350]
        doc.row(["#", "Description", "Qty Received", "Qty Accepted"], xs, bold=True)
        for k, it in enumerate(items, 1):
            doc.row([str(k), it["desc"], f"{it['qty_received']:g}", f"{it['qty_accepted']:g}"], xs)

    doc.y -= 8
    if doc_type == "invoice":
        doc.line(f"Taxable Value: {inr(d['taxable_value'])}", dx=280)
        if d["igst"]:
            doc.line(f"IGST @18%: {inr(d['igst'])}", dx=280)
        else:
            doc.line(f"CGST @9%: {inr(d['cgst'])}", dx=280)
            doc.line(f"SGST @9%: {inr(d['sgst'])}", dx=280)
        doc.line(f"Grand Total: {inr(d['total'])}", bold=True, dx=280)
        doc.y -= 6
        doc.line(f"Payment Terms: {d['payment_terms_text']}")
        doc.line("Bank: Sahakari Udyog Bank, A/c No 004512009876, IFSC SUBK0000451")
        doc.line("MSME supplier: payment beyond 45 days attracts interest under MSMED Act s.16.", size=7)
    elif doc_type == "po":
        doc.line(f"PO Total (excl. GST): {inr(d['po_total'])}", bold=True, dx=250)
        doc.y -= 6
        doc.line(f"Payment Terms: {d['payment_terms_text']}")
    elif doc_type == "challan":
        doc.y -= 30
        if d["received_stamp_present"]:
            doc.line(f"Received By: {d['received_by_name']}")
            doc.line(f"Received Date: {f('received_date')}")
            doc.stamp(f"RECEIVED\n{d['buyer_name'][:22]}\n{f('received_date')}")
            doc.line("Receiver's signature: ________ (signed)")
        else:
            doc.line("Received By: ______________")
            doc.line("Receiver's signature: ______________")
    elif doc_type == "grn":
        doc.line(f"Accepted By: {d['accepted_by']}")
        doc.line(f"Remarks: {d['remarks']}")
    return doc.bytes()


def scanify(pdf_bytes: bytes, rng: random.Random) -> bytes:
    """Rasterise, rotate, blur and add noise -> image-only PDF (no text layer)."""
    import pymupdf
    from PIL import Image, ImageFilter

    page = pymupdf.open(stream=pdf_bytes, filetype="pdf")[0]
    pix = page.get_pixmap(dpi=110)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    img = img.rotate(rng.uniform(-2.5, 2.5), expand=True, fillcolor=245)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 60):
        x, y = rng.randrange(w), rng.randrange(h)
        px[x, y] = max(0, min(255, px[x, y] + rng.randint(-70, 70)))
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=110)
    return out.getvalue()


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--base-date", default="2026-08-20")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    base = date.fromisoformat(args.base_date)
    issued: list[dict] = []

    # scan-style variants on 5 non-defect-critical documents
    scan_targets = {1: "invoice", 5: "challan", 8: "grn", 13: "po", 20: "challan"}

    OUT.mkdir(parents=True, exist_ok=True)
    gt = {"version": 1, "seed": args.seed, "supplier": SUPPLIER,
          "buyers": [{k: b[k] for k in ("code", "name", "gstin")} for b in BUYERS],
          "packages": []}

    for i, defects in enumerate(PLAN):
        p = build_package(i, defects, rng, base, issued)
        pdir = OUT / p.pid
        pdir.mkdir(exist_ok=True)
        for old in pdir.glob("*.pdf"):
            old.unlink()
        files = []
        for doc_type in ("po", "invoice", "challan", "eway", "grn"):
            if doc_type not in p.docs:
                continue
            data = render(p, doc_type)
            scan = scan_targets.get(i) == doc_type
            if scan:
                data = scanify(data, rng)
            name = f"{p.pid}_{doc_type}{'_scan' if scan else ''}.pdf"
            (pdir / name).write_bytes(data)
            files.append({"filename": name, "doc_type": doc_type, "scan": scan,
                          "sha256": hashlib.sha256(data).hexdigest(),
                          "fields": p.docs[doc_type]})
        gt["packages"].append({
            "package_id": p.pid, "buyer_code": p.buyer["code"], "buyer_name": p.buyer["name"],
            "defects": [d for d in defects if d != "clean"], "files": files,
            "expected": expected(p),
        })

    GT_PATH.write_text(json.dumps(gt, indent=1), encoding="utf-8")
    n_files = sum(len(x["files"]) for x in gt["packages"])
    print(f"wrote {len(gt['packages'])} packages, {n_files} PDFs -> {OUT}")
    print(f"ground truth -> {GT_PATH}")


if __name__ == "__main__":
    main()
