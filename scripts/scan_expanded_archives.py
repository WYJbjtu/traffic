"""Check all 45 official raw ZIPs at explicit local/team roots; never download.

Use --source-root PATH repeatedly, where each PATH contains raw/YYYYMM/.
Original bytes and integrity checkpoints remain untouched. This command only
writes a NEW lightweight inventory CSV; existing output is never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from traffic_recovery.data.http import sha256_file


def scan(roots: list[Path], inventory: Path, output: Path) -> dict:
    """Record monthly presence and verify each present ZIP against source manifest.

    Returns available/missing/invalid counts. Invalid input is *not* treated as
    absent or acceptable. Only checked archives are eligible for later pipelines.
    """
    if not roots or output.exists():
        raise ValueError('At least one explicit source root and unused output path required')
    metadata = json.loads(inventory.with_name(inventory.name + '.meta.json').read_text(encoding='utf-8'))
    if metadata.get('sha256') != sha256_file(inventory) or metadata.get('status') != 200:
        raise ValueError('Official raw archive listing integrity mismatch')
    entries = [entry for entry in json.loads(inventory.read_text(encoding='utf-8'))['data-files']
               if '202301' <= entry['timestamp'][:6] <= '202609' and entry['period'] == 'M']
    months = [f'{y}{m:02d}' for y in range(2023, 2027) for m in range(1,13) if (y,m) <= (2026,9)]
    if sorted(entry['timestamp'][:6] for entry in entries) != months or len(entries) != 45:
        raise ValueError('Expected 45 distinct official monthly entries')
    rows = []
    for entry in entries:
        token = entry['timestamp'][:6]
        present = [root / f'raw/{token}/raw_{token}.zip' for root in roots
                   if (root / f'raw/{token}/raw_{token}.zip').exists()]
        if len(present) > 1:
            raise ValueError(f'Archive ambiguous in multiple roots: {token}; consolidate evidence first')
        record = {'month':token, 'official_expected_bytes':entry['size'],
                  'official_expected_snapshots':entry['resource_file_count'],
                  'path':str(present[0]) if present else None, 'sha256':None,
                  'status':'missing' if not present else 'unverified'}
        if present:
            path = present[0]
            check_path = path.parent / 'archive_check.json'
            meta_path = path.with_name(path.name + '.meta.json')
            if not check_path.exists() or not meta_path.exists():
                record['status'] = 'missing_integrity_checkpoint'
            else:
                check = json.loads(check_path.read_text(encoding='utf-8'))
                http = json.loads(meta_path.read_text(encoding='utf-8'))
                digest = sha256_file(path)
                record['sha256'] = digest
                if (path.stat().st_size == entry['size'] == check.get('bytes') == http.get('bytes')
                        and digest == check.get('sha256') == http.get('sha256')
                        and check.get('snapshots') == entry['resource_file_count']):
                    record['status'] = 'verified'
                else:
                    record['status'] = 'integrity_mismatch'
        rows.append(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return {'expected_months':45, 'verified_months':sum(row['status']=='verified' for row in rows),
            'missing_months':sum(row['status']=='missing' for row in rows),
            'invalid_months':[row['month'] for row in rows if row['status'] not in ('verified','missing')],
            'explicit_roots':[str(root) for root in roots], 'inventory_url':metadata['requested_url'],
            'inventory_sha256':metadata['sha256'], 'path':str(output)}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, action='append', required=True)
    p.add_argument('--inventory',type=Path,default=Path('data/local/smoke-audit/coverage_raw.json'))
    p.add_argument('--output',type=Path,default=Path('reports/lane_expansion_continuity/archive_inventory.csv'))
    a=p.parse_args()
    print(json.dumps(scan(a.source_root,a.inventory,a.output),indent=2))


if __name__=='__main__':main()
