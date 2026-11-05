"""Portable repository code and ignored local data locations."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("TIANHAO_WORK_DIR", str(ROOT / "data/local/tianhao_experiment"))).expanduser().resolve()
DATA = Path(os.environ.get("TIANHAO_DATA_DIR", str(BASE / "release_subset"))).expanduser().resolve()

def describe_path(path: Path) -> str:
    for label, base in [("repository", ROOT), ("work", BASE), ("release_subset", DATA)]:
        if path.is_relative_to(base):
            return label + "/" + path.relative_to(base).as_posix()
    return "external-input/" + path.name


def traffic_file(data_dir: Path, name: str) -> Path:
    """Resolve the old24/new96 release layouts; reject ambiguity or missing input."""
    candidates=[data_dir/'processed/derived'/name,data_dir/'processed'/name]
    existing=[p for p in candidates if p.is_file()]
    if len(existing)!=1:raise ValueError(f'Expected exactly one {name} in the release layouts')
    return existing[0]
