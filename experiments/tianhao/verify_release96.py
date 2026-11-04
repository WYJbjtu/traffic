"""Offline verification of the published96 prediction/config/source bundle."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from traffic_recovery.models.evaluation import evaluate_predictions
from traffic_recovery.models.saved_comparison import normalise_predictions
from run_extended_models import sha,summarise_predictions
from run_release96 import ARTIFACTS,verify_release,verify_sources


def verify_bundle(artifacts: Path=ARTIFACTS, *, release_dir: Path|None=None, source_cache: Path|None=None) -> dict:
    """Recompute metrics/counts/selection and enforce current+historical hashes.

    Pipeline binaries remain local. Probability replay is recorded in the original
    local receipt, not falsely claimed as an offline check without those binaries.
    """
    manifest=json.loads((artifacts/'publication_manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files_sha256'].items():
        p=(artifacts/name).resolve()
        if not p.is_relative_to(artifacts.resolve()) or sha(p)!=digest:raise ValueError('Published artifact hash mismatch: '+name)
    if sha(ROOT/'uv.lock')!=manifest['lock_sha256']:raise ValueError('Publication lock changed')
    notebook=json.loads((ROOT/manifest['notebook_path']).read_text(encoding='utf-8'))
    code='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code')
    if hashlib.sha256(code.encode()).hexdigest()!=manifest['notebook_source_sha256']:raise ValueError('Notebook execution source changed')
    for name,digest in manifest['code_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Publication code changed: '+name)
    original=json.loads((artifacts/'original_training_manifest.json').read_text())
    if original['run']['lock']['sha256']!=sha(artifacts/'original_uv.lock'):raise ValueError('Historical lock differs')
    for name,digest in original['outputs_sha256'].items():
        if (artifacts/name).is_file() and sha(artifacts/name)!=digest:raise ValueError('Published bytes differ from original run: '+name)
    for name,digest in original['code_sha256'].items():
        if sha(artifacts/'training_code'/name)!=digest:raise ValueError('Historical training source changed: '+name)
    for source,target in [('contract','contract.json'),('extended_rules','extended_rules.json'),('supervised_rules','supervised_rules.json'),('benchmark_rules','benchmark_rules.json')]:
        if sha(artifacts/'configs'/target)!=original['inputs'][source]['sha256']:raise ValueError('Frozen config differs: '+source)
    live={'configs/tianhao_expanded96_30m_contract.json':'contract.json','configs/tianhao_extended_models.json':'extended_rules.json','configs/supervised_models.json':'supervised_rules.json','configs/benchmarks.json':'benchmark_rules.json'}
    for path,frozen in live.items():
        if sha(ROOT/path)!=sha(artifacts/'configs'/frozen):raise ValueError('Live/frozen config mismatch: '+path)
    pred=normalise_predictions(pd.read_parquet(artifacts/'predictions.parquet'))
    if len(pred)!=557160 or pred[['model','feature_set']].drop_duplicates().shape[0]!=20:raise ValueError('Incomplete96 predictions')
    counts={'train':13002,'validation':7848,'test':7008}
    references={}
    for (model,features,split),p in pred.groupby(['model','feature_set','split']):
        ordered=p.set_index('event_id').sort_index()
        if len(p)!=counts[split]:raise ValueError('Wrong split count')
        values=ordered[['prediction_time','y_true']]
        if split in references and not values.equals(references[split]):raise ValueError('Mismatched event cohort/labels/times')
        references[split]=values
        if model in ['logistic_regression','decision_tree','logistic_l1','svm_rbf'] and not np.array_equal(p.y_score.ge(.5).astype(int),p.y_pred):raise ValueError('Frozen threshold mismatch')
    metrics=evaluate_predictions(pred,version_column='experiment_version');saved=pd.read_csv(artifacts/'metrics.csv')
    keys=['model','feature_set','horizon_min','split','metric_name']
    paired=metrics.merge(saved,on=keys,how='outer',suffixes=('_new','_saved'),validate='one_to_one',indicator=True)
    if not paired._merge.eq('both').all() or not np.allclose(paired.metric_value_new,paired.metric_value_saved,atol=1e-12,rtol=1e-9,equal_nan=True):raise ValueError('Recomputed metrics differ')
    for name in ['n_rows','n_events','n_positive','n_censored','n_missing_feature']:
        if not np.array_equal(paired[name+'_new'],paired[name+'_saved']):raise ValueError('Metric count mismatch: '+name)
    _,summary,cm,selected=summarise_predictions(pred)
    actual=pd.read_csv(artifacts/'confusion_matrices.csv');k=['model','feature_set','horizon_min','split']
    paired=cm.merge(actual,on=k,how='outer',suffixes=('_new','_saved'),validate='one_to_one',indicator=True)
    if not paired._merge.eq('both').all() or not np.array_equal(paired[['n_new','tn_new','fp_new','fn_new','tp_new']],paired[['n_saved','tn_saved','fp_saved','fn_saved','tp_saved']]):raise ValueError('Confusion/count mismatch')
    actual=pd.read_csv(artifacts/'validation_selected.csv');k=['model','feature_set','is_overall_choice']
    if not selected[k].sort_values('model').reset_index(drop=True).equals(actual[k].sort_values('model').reset_index(drop=True)):raise ValueError('Validation-selected groups differ')
    tuning=pd.read_csv(artifacts/'tuning.csv');chosen=pd.read_csv(artifacts/'selected_parameters.csv')
    if len(tuning)!=224 or tuning.groupby(['model','feature_set']).ngroups!=16:raise ValueError('Incomplete tuning')
    for key,part in tuning.groupby(['model','feature_set']):
        best=part.sort_values(['validation_log_loss','candidate_id']).iloc[0]
        selected_rows=part.loc[part.selected]
        p=chosen.loc[chosen.model.eq(key[0])&chosen.feature_set.eq(key[1])]
        if len(selected_rows)!=1 or len(p)!=1 or best.candidate_id!=selected_rows.iloc[0].candidate_id or best.parameters!=p.iloc[0].parameters:raise ValueError('Candidate winner differs')
    preparation=json.loads((artifacts/'original_preparation_manifest.json').read_text())
    if sha(artifacts/'sources.csv')!=preparation['outputs_sha256']['source_checks.csv'] or sha(artifacts/'coverage.csv')!=preparation['outputs_sha256']['coverage.csv']:raise ValueError('Source/coverage inventory differs from original preparation')
    sources=pd.read_csv(artifacts/'sources.csv')
    if len(sources)!=94 or sources.file.duplicated().any() or not sources.sha256.str.fullmatch('[0-9a-f]{64}').all():raise ValueError('Incomplete source inventory')
    for value in sources.retrieved_at:
        if pd.Timestamp(value).tzinfo is None:raise ValueError('Naive source retrieval time')
    alignment='not_rechecked_without_release'
    if release_dir is not None:
        verify_release(release_dir);events=pd.read_parquet(release_dir/'processed/events.parquet').set_index('event_id')
        for split,reference in references.items():
            eligible=events.loc[events.split_proposal.eq(split)&events.label_30m.notna()].sort_index()
            if not eligible.index.equals(reference.index) or not eligible.prediction_time.equals(reference.prediction_time) or not np.array_equal(eligible.label_30m,reference.y_true):raise ValueError('Release truth mismatch')
        alignment='passed'
    if source_cache is not None:verify_sources(source_cache)
    return dict(status='passed',prediction_rows=len(pred),metric_rows=len(metrics),arms=20,arm_splits=60,candidates=224,
        sources=len(sources),release_alignment=alignment,source_bytes_rechecked=source_cache is not None,
        probability_replay='historical local receipt; requires local fitted_pipelines.joblib to rerun',
        historical_git=original['run']['git'],scientific_approval='pending_team_review')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--release-dir',type=Path);parser.add_argument('--source-cache',type=Path)
    args=parser.parse_args();print(json.dumps(verify_bundle(release_dir=args.release_dir,source_cache=args.source_cache),indent=2))
