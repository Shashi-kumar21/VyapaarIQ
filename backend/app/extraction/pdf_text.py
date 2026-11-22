"""PDF/image -> per-page text lines + page images; detects scanned documents.

Lines are rebuilt from word boxes so that table columns drawn separately end up
on one line, separated by two or more spaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

SCANNED_CHARS_PER_PAGE = 40
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


class UnreadableFileError(ValueError):
    """The file is not a readable PDF or image."""


@dataclass
class PdfContent:
    pages: list[str] = field(default_factory=list)  # one text block per page
    page_count: int = 0
    is_scanned: bool = False
    is_image: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.pages)


def _page_lines(page: "pymupdf.Page") -> str:
    words = page.get_text("words")  # x0, y0, x1, y1, word, block, line, wno
    if not words:
        return ""
    words.sort(key=lambda w: (round((w[1] + w[3]) / 2), w[0]))
    lines: list[list[tuple]] = []
    for w in words:
        mid = (w[1] + w[3]) / 2
        if lines and abs(((lines[-1][0][1] + lines[-1][0][3]) / 2) - mid) <= 3.0:
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for ln in lines:
        ln.sort(key=lambda w: w[0])
        parts, prev_x1 = [], None
        for w in ln:
            if prev_x1 is not None:
                parts.append("  " if w[0] - prev_x1 > 8 else " ")
            parts.append(w[4])
            prev_x1 = w[2]
        out.append("".join(parts))
    return "\n".join(out)


def read_document(data: bytes, filename: str = "") -> PdfContent:
    name = filename.lower()
    try:
        if name.endswith(IMAGE_EXT):
            doc = pymupdf.open(stream=data, filetype=name.rsplit(".", 1)[-1])
            return PdfContent(pages=[""] * max(1, doc.page_count), page_count=max(1, doc.page_count),
                              is_scanned=True, is_image=True)
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf raises several types for corrupt input
        raise UnreadableFileError(f"Cannot open {filename or 'file'}: not a readable PDF/image.") from exc
    if doc.page_count == 0:
        raise UnreadableFileError(f"{filename or 'file'} has no pages.")
    pages = [_page_lines(p) for p in doc]
    chars = sum(len(p.strip()) for p in pages)
    return PdfContent(pages=pages, page_count=doc.page_count,
                      is_scanned=chars / doc.page_count < SCANNED_CHARS_PER_PAGE)


def page_images_png(data: bytes, filename: str = "", dpi: int = 150, max_pages: int = 3) -> list[bytes]:
    """Render pages to PNG for a vision model."""
    name = filename.lower()
    if name.endswith(IMAGE_EXT):
        doc = pymupdf.open(stream=data, filetype=name.rsplit(".", 1)[-1])
    else:
        doc = pymupdf.open(stream=data, filetype="pdf")
    return [doc[i].get_pixmap(dpi=dpi).tobytes("png") for i in range(min(max_pages, doc.page_count))]
