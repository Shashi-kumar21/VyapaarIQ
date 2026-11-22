import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GT = REPO / "samples" / "ground_truth.json"
OUT = REPO / "samples" / "out"


@pytest.fixture(scope="session")
def ground_truth() -> dict:
    """Generate samples if needed (PDFs are gitignored, ground truth is not)."""
    if not OUT.exists() or not any(OUT.glob("PKG*/*.pdf")):
        subprocess.run([sys.executable, str(REPO / "samples" / "generate.py")], check=True)
    return json.loads(GT.read_text(encoding="utf-8"))
