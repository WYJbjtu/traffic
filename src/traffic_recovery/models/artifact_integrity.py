"""Separate immutable result integrity from changes in a live source checkout."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
from collections.abc import Mapping, Sequence


def verify_manifest_files(
    root: Path,
    hashes: Mapping[str, str],
    *,
    immutable_prefixes: Sequence[str],
    strict_snapshot: bool = False,
) -> dict[str, object]:
    """Verify frozen artifacts; report live-file drift without approving that code.

    Missing or changed immutable files always raise. ``strict_snapshot=True`` also
    rejects source/document drift, and is intended for a checkout of the original
    release commit. No expected hash is updated. Paths must stay inside ``root``.
    """
    root = root.resolve()
    verified = 0
    changes: list[dict[str, str | None]] = []
    for name, expected in hashes.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Manifest path escapes checkout: {name}")
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Manifest path escapes checkout: {name}")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"Invalid SHA256 in manifest: {name}")
        frozen = any(name.startswith(prefix.rstrip("/") + "/") for prefix in immutable_prefixes)
        actual = None
        if path.is_file():
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual == expected.lower():
            verified += int(frozen)
            continue
        status = "missing" if actual is None else "changed"
        if frozen or strict_snapshot:
            raise ValueError(f"{'Artifact' if frozen else 'Snapshot'} SHA256 {status}: {name}")
        changes.append({"path": name, "status": status, "expected_sha256": expected,
                        "actual_sha256": actual})
    return {
        "mode": "strict_snapshot" if strict_snapshot else "immutable_results",
        "verified_artifacts": verified,
        "workspace_changes": changes,
        "snapshot_matches_manifest": not changes,
        "note": "Result integrity does not certify the scientific validity or identity of current code.",
    }
