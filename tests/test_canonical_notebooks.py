"""Active Notebook inventory; historical manifests are intentionally not migrated."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "Tianhao_新版96车道_完整重跑_20261104.ipynb"


def test_canonical_notebook_render_inventory():
    files = {p.name for p in (ROOT / "notebooks").glob("*.ipynb")}
    assert files == {NOTEBOOK, "long_window_review.ipynb"}
    cells = json.loads((ROOT / "notebooks" / NOTEBOOK).read_text(encoding="utf-8"))["cells"]
    code = [cell for cell in cells if cell["cell_type"] == "code"]
    assert [cell["execution_count"] for cell in code] == list(range(1, 11))
    assert not any(out.get("output_type") == "error" for cell in code for out in cell.get("outputs", []))
    assert sum("image/png" in out.get("data", {}) for cell in code for out in cell.get("outputs", [])) == 7
