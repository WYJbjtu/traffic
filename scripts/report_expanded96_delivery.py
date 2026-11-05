"""Generate measured lightweight expanded96 delivery evidence; no inferred spatial approvals.

Requires the official Release ZIP and the independently created model run. Never
modifies source archives, model predictions or historical output manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

import pandas as pd
import pyarrow.parquet as pq

from traffic_recovery.data.http import sha256_file

ZIP_SHA = 'f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8'


def report(archive: Path, prepared: Path, run: Path, network: Path, out: Path) -> None:
    if out.exists():
        raise FileExistsError(f'Refusing overwrite: {out}')
    if sha256_file(archive) != ZIP_SHA:
        raise ValueError('Expanded96 ZIP SHA-256 mismatch')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('SHARED_DATA_MANIFEST.json'))
        for name, entry in manifest['files'].items():
            digest = hashlib.sha256()
            size = 0
            with z.open(name) as f:
                while chunk := f.read(4 * 1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            if size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
                raise ValueError(f'Internal Release member mismatch: {name}')
    for name in ('events', 'cohort_bins'):
        if sha256_file(prepared / 'processed' / f'{name}.parquet') != manifest['files'][f'processed/{name}.parquet']['sha256']:
            raise ValueError(f'Extracted {name} mismatch')
    bins_count = pq.ParquetFile(prepared / 'processed/cohort_bins.parquet').metadata.num_rows
    if bins_count != 35782769:
        raise ValueError('Expanded96 bin count mismatch')
    events = pd.read_parquet(prepared / 'processed/events.parquet')
    if len(events) != manifest['events'] or events.event_id.duplicated().any():
        raise ValueError('Event count or identity mismatch')
    model = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in model['outputs_sha256'].items():
        if sha256_file(run / name) != digest:
            raise ValueError(f'Model result mismatch: {name}')
    if model['source_sha256']['events'] != manifest['files']['processed/events.parquet']['sha256']:
        raise ValueError('Model source identity mismatch')
    net = json.loads((network / 'manifest.json').read_text(encoding='utf-8'))
    sources = {name: {'path': evidence['path'], 'sha256': evidence['sha256'],
        'locally_verified': sha256_file(Path(evidence['path'])) == evidence['sha256']}
        for name, evidence in net['sources'].items()}
    if not all(x['locally_verified'] for x in sources.values()):
        raise ValueError('Official road source mismatch')
    with sqlite3.connect(network / 'topology_index.sqlite') as db:
        road_count = db.execute('select count(*) from roads').fetchone()[0]
        arc_count = db.execute('select count(*) from arcs').fetchone()[0]
    if road_count != net['source_segments'] or arc_count != net['directed_arcs']:
        raise ValueError('Road index does not match source manifest')
    meta = pd.read_csv(prepared / 'metadata/detectors.csv', dtype=str, encoding='utf-8-sig')
    meta = meta.rename(columns={'AID_ID_Number': 'detector_id'})
    if meta.detector_id.duplicated().any():
        raise ValueError('Duplicate metadata detector ID')
    indexed = events.merge(meta[['detector_id', 'Easting', 'Northing']], on='detector_id',
                           how='left', validate='many_to_one')
    location = indexed.Easting.notna() & indexed.Northing.notna()
    if (indexed.split_proposal.value_counts().to_dict() != model['splits']
            or len(indexed[['detector_id', 'direction', 'lane_id']].drop_duplicates()) != model['event_lane_units']):
        raise ValueError('Split or event unit mismatch')
    out.mkdir(parents=True)
    summary = {'release_zip_sha256': ZIP_SHA, 'release_files_verified': len(manifest['files']),
        'frozen_lane_units': manifest['units'], 'event_lane_units': model['event_lane_units'],
        'events': len(events), 'bins': bins_count,
        'split_counts': {k: int(v) for k, v in indexed.split_proposal.value_counts().items()},
        'known_label_counts': {f'{h}m': int(indexed[f'label_{h}m'].notna().sum()) for h in (15, 30, 60)},
        'unknown_label_counts': {f'{h}m': int(indexed[f'label_{h}m'].isna().sum()) for h in (15, 30, 60)},
        'events_with_current_metadata_coordinates': int(location.sum()),
        'event_units_with_current_metadata_coordinates': int(indexed.loc[location, ['detector_id', 'direction', 'lane_id']].drop_duplicates().shape[0]),
        'model_manifest_sha256': sha256_file(run / 'manifest.json')}
    (out / 'dataset_verification.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (out / 'network_construction_validation.json').write_text(json.dumps({
        'status': 'SOURCE HASH AND SQLITE COUNTS VERIFIED; HISTORICAL TOPOLOGY NOT VERIFIED',
        'source_hashes': sources, 'roads_sqlite': road_count, 'arcs_sqlite': arc_count,
        'candidate_transition_counts': net['transition_status_counts'],
        'source_manifest_sha256': sha256_file(network / 'manifest.json'),
        'verified_detector_mappings': 0, 'verified_directed_relations': 0,
        'verification_basis': 'No signed mapping/transition approval artifact was supplied to this run; zero *admitted*, not a claim that no valid roads exist.'}, indent=2) + '\n', encoding='utf-8')
    eligibility = pd.DataFrame({'event_id': indexed.event_id,
        'split': indexed.split_proposal, 'location_known_current_metadata': location,
        'lane_direction_identity_present': indexed[['detector_id','direction','lane_id']].notna().all(axis=1),
        'mapping_approved': False, 'topology_approved': False,
        'upstream_asof_observation_approved': False,
        'downstream_asof_observation_approved': False,
        'eligible_for_spatial_model': False,
        'reason': 'historical_mapping_and_directed_topology_not_approved'})
    for h in (15, 30, 60):
        eligibility[f'known_label_{h}m'] = indexed[f'label_{h}m'].notna()
    eligibility.to_csv(out / 'spatial_event_eligibility.csv', index=False)
    pd.read_csv(run / 'model_metrics.csv').to_csv(out / 'model_metrics.csv', index=False)
    pd.read_csv(run / 'tuning.csv').to_csv(out / 'model_tuning.csv', index=False)
    history = pd.read_parquet(run / 'history_features.parquet')
    coverage = pd.DataFrame([{'split': split, 'events': len(part),
        'lag_5m_nonmissing': int(part.lag_5m_ratio.notna().sum()),
        'lag_30m_nonmissing': int(part.lag_30m_ratio.notna().sum()),
        'mean_observed_history_bins': float(part.history_observed_bins.mean())}
        for split, part in indexed[['event_id', 'split_proposal']].merge(history, on='event_id', validate='one_to_one').groupby('split_proposal')])
    coverage.to_csv(out / 'feature_coverage_by_split.csv', index=False)
    print(json.dumps(summary, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'prepared', 'run', 'network', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    report(args.archive, args.prepared, args.run, args.network, args.out)


if __name__ == '__main__':
    main()
