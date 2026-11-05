"""Locate and verify frozen January selection evidence across machines."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from traffic_recovery.data.http import sha256_file


def selection_directory(result: Mapping[str, str], override: Path | None = None) -> Path:
    """Return directory with the hashed selection profile; raise on missing/mismatch.

    ``override`` relocates the profile without changing its frozen digest. No
    machine-specific directory is assumed when a relocation is supplied.
    """
    directory = override if override is not None else Path(result['selection_frozen_from']).parent
    profile = directory / 'coverage_lane_day.parquet'
    if not profile.is_file():
        raise FileNotFoundError(f'Missing frozen selection profile: {profile}; set --selection-directory')
    if sha256_file(profile) != result['selection_profile_sha256']:
        raise ValueError('Frozen selection profile checksum mismatch')
    return directory
