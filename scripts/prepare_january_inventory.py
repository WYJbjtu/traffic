"""Explicit one-month official archive acquisition and full-inventory selection.

By default NO HTTP download. --acquire-one-month fetches January 2023 ONLY
(1.14 GB); never downloads 2023–2026. The original selection pipeline and
source ZIP/Parquet checksums are reused; output is separate from 24-unit study.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import pandas as pd

from scripts.download_long_window import acquire
from scripts.prepare_long_window import ingest_job, profiles, VERSION
from traffic_recovery.data.events import UNIT
from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.pilot import select_cohort


def prepare(root: Path, inventory: Path, *, acquire_one_month: bool = False, workers: int = 2) -> dict:
    """Checkpointed Jan 1–8 capture + Jan 1–7 day profiles, verify published 24.

    Existing source is never overwritten; each per-day pipeline checkpoint
    validates source and code identity. Refuse an existing uncheckpointed final
    coverage table rather than silently replacing previous derivations.
    """
    if workers < 1 or workers > 4:
        raise ValueError('Choose 1–4 bounded workers')
    evidence = json.loads(inventory.with_name(inventory.name + '.meta.json').read_text(encoding='utf-8'))
    if evidence['sha256'] != sha256_file(inventory) or evidence['status'] != 200:
        raise ValueError('Official archive inventory provenance mismatch')
    entries = [entry for entry in json.loads(inventory.read_text(encoding='utf-8'))['data-files']
               if entry['timestamp'] == '20230101' and entry['period'] == 'M']
    if len(entries) != 1:
        raise ValueError('Expected exactly one January 2023 official monthly raw archive')
    archive = root / 'raw/202301/raw_202301.zip'
    if not archive.is_file() and not acquire_one_month:
        raise FileNotFoundError(f'{archive}: pass --acquire-one-month to explicitly download January ONLY')
    record = acquire(root, entries[0])
    if record['sha256'] != sha256_file(archive):
        raise ValueError('Archive checksum changed')
    implementation = {p.name: sha256_file(p) for p in
                      [Path('scripts/prepare_long_window.py'), Path('src/traffic_recovery/data/long_window.py')]}
    jobs = [(str(archive), f'202301{day:02d}', str(root / f'selection/lane_snapshots/202301{day:02d}.parquet'),
             None, record['sha256'], implementation) for day in range(1, 9)]
    with ProcessPoolExecutor(max_workers=min(workers, 2)) as pool:
        list(pool.map(ingest_job, jobs))
    config = json.loads(Path('configs/long_window.json').read_text(encoding='utf-8'))
    selection = root / 'selection/derived'
    final = selection / 'coverage_lane_day.parquet'
    checkpoint = selection / 'coverage_lane_day.audit.json'
    if final.exists():
        if not checkpoint.is_file() or json.loads(checkpoint.read_text(encoding='utf-8')) != {
                'sha256': sha256_file(final), 'archive_sha256': record['sha256'],
                'config_sha256': sha256_file(Path('configs/long_window.json'))}:
            raise ValueError(f'Existing uncheckpointed/stale selection profile: {final}')
        profile = pd.read_parquet(final)
    else:
        profile = profiles(root, root / 'selection/lane_snapshots', selection,
            pd.Timestamp(config['observation_start']), pd.Timestamp(config['selection_end']), None, workers)
        checkpoint.write_text(json.dumps({'sha256': sha256_file(final), 'archive_sha256': record['sha256'],
            'config_sha256': sha256_file(Path('configs/long_window.json'))}, indent=2) + '\n', encoding='utf-8')
    capped, comparison = select_cohort(profile, pd.Timestamp(config['selection_end']), config)
    published = pd.read_csv('reports/long_window/cohort.csv', dtype={name: str for name in UNIT})
    if capped[UNIT].to_dict('records') != published[UNIT].to_dict('records'):
        raise ValueError('24-unit reproduction differs; stop')
    pd.testing.assert_frame_equal(comparison, pd.read_csv('reports/long_window/selection_filter_comparison.csv'),
                                  check_dtype=False)
    print(json.dumps({'reproduced_original_24': True, 'full_inventory_lane_units':len(profile[UNIT].drop_duplicates()),
                      'archive_sha256': record['sha256']}, indent=2))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, default=Path('data/local/smoke-audit/coverage_raw.json'))
    parser.add_argument('--acquire-one-month', action='store_true')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    prepare(args.root, args.inventory, acquire_one_month=args.acquire_one_month, workers=args.workers)


if __name__ == '__main__':
    main()
