"""Synthetic byte fixtures: distinguish result tampering from live docs drift."""
import hashlib
from pathlib import Path

import pytest

from traffic_recovery.models.artifact_integrity import verify_manifest_files


def fixture(root: Path) -> dict[str, str]:
    (root / 'results').mkdir()
    files = {'README.md': b'SYNTHETIC original docs', 'results/predictions.parquet': b'SYNTHETIC result bytes'}
    for name, payload in files.items():
        (root / name).write_bytes(payload)
    return {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()}


def test_readme_update_is_reported_and_result_still_verified(tmp_path):
    hashes = fixture(tmp_path)
    (tmp_path / 'README.md').write_text('SYNTHETIC later team documentation')
    report = verify_manifest_files(tmp_path, hashes, immutable_prefixes=('results',))
    assert report['verified_artifacts'] == 1
    assert report['workspace_changes'][0]['path'] == 'README.md'
    assert not report['snapshot_matches_manifest']
    with pytest.raises(ValueError, match='Snapshot SHA256 changed: README.md'):
        verify_manifest_files(tmp_path, hashes, immutable_prefixes=('results',), strict_snapshot=True)


@pytest.mark.parametrize('missing', [False, True])
def test_altered_or_missing_predictions_fail_even_when_readme_changed(tmp_path, missing):
    hashes = fixture(tmp_path)
    (tmp_path / 'README.md').write_text('SYNTHETIC changed docs')
    path = tmp_path / 'results/predictions.parquet'
    if missing:
        path.unlink()
    else:
        path.write_bytes(b'SYNTHETIC tampered result')
    with pytest.raises(ValueError, match='Artifact SHA256'):
        verify_manifest_files(tmp_path, hashes, immutable_prefixes=('results',))


def test_frozen_snapshot_still_checks_all_files(tmp_path):
    report = verify_manifest_files(tmp_path, fixture(tmp_path), immutable_prefixes=('results',), strict_snapshot=True)
    assert report['snapshot_matches_manifest'] and not report['workspace_changes']


def test_manifest_cannot_read_outside_checkout(tmp_path):
    with pytest.raises(ValueError, match='escapes checkout'):
        verify_manifest_files(tmp_path, {'../secret': '0' * 64}, immutable_prefixes=('results',))
