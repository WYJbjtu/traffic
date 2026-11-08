"""Current C/W-adjusted RF/XGB controls with matched 12-field S1 summaries.

Directed vs pooled uses exactly the same observed neighbor records. Geographic
uses the existing frozen 250m nearest-detector rule. Same P1 events, no dropna.
Full F7/S1–S4 is NOT used as the directed structure comparator here.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import logging

import numpy as np
import pandas as pd
from experiments.unified96.matrix import fit_arm, dump
from experiments.unified96.poster_analysis import recompute, verify_run
from experiments.unified96.run import ROOT, ARMS, event_hash
from scripts.spatial96_inferred_v2 import S1
from traffic_recovery import research96
from traffic_recovery.data.http import sha256_file


def pooled_s1(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove side identity, pooling values by observed counts; no zero speed fill.

    Coverage is the unweighted average of defined side coverages, matching the
    frozen geographic representation. Both slots repeat the same pooled set.
    """
    out = frame.copy()
    a, b = frame.upstream_observed_count, frame.downstream_observed_count
    n = a+b
    for field in ['mean_speed_kmh', 'mean_ratio', 'mean_age_minutes', 'coverage']:
        left, right = frame['upstream_'+field], frame['downstream_'+field]
        if field == 'coverage':
            combined = pd.concat([left, right], axis=1).mean(axis=1)
        else:
            combined = (left.fillna(0)*a + right.fillna(0)*b)/n.replace(0, np.nan)
        for side in ['upstream', 'downstream']:
            out[side+'_'+field] = combined
    for side in ['upstream', 'downstream']:
        out[side+'_observed_count'] = n
        out[side+'_missing'] = n.eq(0).astype(int)
    return out


def run_controls(run: Path, out: Path) -> None:
    """Run six independently refitted matched structural controls, refuse overwrite."""
    if out.exists():
        raise FileExistsError(out)
    verify_run(run)
    base = pd.read_parquet(run/'model_input.parquet')
    geo_path = research96.verified_file(ROOT, 'data/local/spatial96/inferred-v2/geographic_control_features.parquet')
    lineage_path = research96.verified_file(ROOT, 'data/local/spatial96/inferred-v2/geographic_control_lineage.parquet')
    geo = pd.read_parquet(geo_path)
    lines = pd.read_parquet(lineage_path)
    matched = lines.merge(base[['event_id','prediction_time','detector_id']], on='event_id', validate='many_to_one')
    for col in ['observed_at','available_at','last_source_available_at']:
        if not matched[col].le(matched.prediction_time).all():
            raise ValueError('Future geographic observation')
    if matched.neighbor_detector.eq(matched.detector_id).any():
        raise ValueError('Geographic control contains target itself')
    geographic = base.drop(columns=S1).merge(geo[['event_id','prediction_time']+S1],
        on=['event_id','prediction_time'], validate='one_to_one', how='left', indicator=True)
    if not geographic._merge.eq('both').all():
        raise ValueError('Geographic feature keys do not cover P1')
    out.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO)
    predictions, results, tuning, audits, coverage = [], [], [], [], []
    for arm, data in [('CW_S1_directed',base), ('CW_S1_undirected',pooled_s1(base)), ('CW_S1_geographic',geographic)]:
        p, m, t, a = fit_arm(data, ARMS['F3']+S1, arm, out.name, ('random_forest','xgboost'))
        for row in m.itertuples():
            block = p.loc[p.model.eq(row.model) & p.split.eq(row.split)]
            if event_hash(block.event_id) != event_hash(base.loc[base.split.eq(row.split),'event_id']):
                raise ValueError('Control cohort changed')
            for key, value in recompute(block).items():
                if not np.isclose(value,getattr(row,key),rtol=1e-10,atol=1e-7):
                    raise ValueError('Control metric differs from saved predictions')
        for fit in a:
            means = data.loc[data.split.eq('train'),fit['feature_columns']].mean().to_numpy(dtype=float)
            stats = np.array([np.nan if v is None else v for v in fit['imputer_statistics']])
            if not np.allclose(means,stats,equal_nan=True):
                raise ValueError('Control preprocessing not train-only')
        for split, block in data.groupby('split'):
            coverage.append({'control':arm,'split':split,'n_events':len(block),
                'any_neighbor_fraction':float(((block.upstream_observed_count+block.downstream_observed_count)>0).mean())})
        predictions.append(p); results.append(m); tuning.append(t); audits.extend(a)
    pd.concat(predictions,ignore_index=True).to_parquet(out/'predictions.parquet',index=False)
    pd.concat(results,ignore_index=True).to_csv(out/'metrics.csv',index=False)
    pd.concat(tuning,ignore_index=True).to_csv(out/'tuning.csv',index=False)
    pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
    dump(out/'fit_audit.json',audits)
    dump(out/'manifest.json',{'status':'COMPLETE_RETROSPECTIVE_MATCHED_S1_CONTROLS',
        'main_run_manifest_sha256':sha256_file(run/'manifest.json'),
        'source_sha256':{str(p.relative_to(ROOT)):sha256_file(p) for p in [geo_path,lineage_path]},
        'code_sha256':sha256_file(Path(__file__)), 'arms':6,'features':ARMS['F3']+S1,
        'verification':'all controls same P1 event hashes; independently recalculated metrics; train-only imputer statistics',
        'limits':'12 S1 fields only, not F7; pooled slots duplicate one set; geographic coverage differs; no new permutation experiment',
        'outputs_sha256':{p.name:sha256_file(p) for p in out.iterdir() if p.is_file()}})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); run_controls(args.run,args.out)
