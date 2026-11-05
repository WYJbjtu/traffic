"""Reproduce labeled inferred-v2 review copies of PR #20 official geometry maps."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
prior = ROOT / "reports/spatial96_nov05"
report = ROOT / "reports/spatial96_inferred_v2"
if not report.is_dir():
    raise FileNotFoundError("Run inferred-v2 experiment first")
for source, dest in (("ranked-directed-pair-1.png", "review-official-intersection.png"),
                     ("pair-1.png", "review-short-path-large-offset.png")):
    data = (prior / source).read_bytes()
    if len(data) < 10000 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Missing authentic source figure: {source}")
    (report / dest).write_bytes(data)
    print(source, dest, hashlib.sha256(data).hexdigest())
sources = json.loads((report / "source_sha256.json").read_text(encoding="utf-8"))
for name in ("uv.lock", "src/traffic_recovery/network/inferred_v2.py",
             "scripts/spatial96_inferred_v2.py", "scripts/spatial96_inferred_controls.py",
             "scripts/spatial96_inferred_figures.py"):
    sources[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
(report / "source_sha256.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
outputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
           for folder in (ROOT / "data/local/spatial96/inferred-v2", report)
           for p in folder.iterdir() if p.is_file() and p.name != "output_sha256.json"}
(report / "output_sha256.json").write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")
