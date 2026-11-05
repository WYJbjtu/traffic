"""Verify legacy and extended real runs using their frozen plans and cohorts."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from traffic_recovery.models.evaluation import evaluate_predictions
from traffic_recovery.models.extended_classifiers import attach_outcome_maturity, base_pipeline
from traffic_recovery.models.saved_comparison import normalise_predictions
from run_extended_models import sha, summarise_predictions
from run_experiment import add_trend
from traffic_recovery.models.contract import ExperimentContract
from traffic_recovery.models.benchmarks import BenchmarkRules, benchmark_predictions


def verify_run(output: Path, dataset_path: Path, events_path: Path, report_path: Path | None = None) -> dict[str, object]:
    """Recompute saved metrics and probabilities; fail on missing arms or artifacts.

    Supports the original 14-arm run and new 24-arm run without fixing row counts.
    The original historical verifier remains available for its strict snapshot.
    """
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    hashes=manifest.get('outputs_sha256',manifest.get('outputs'))
    if not isinstance(hashes,dict) or not hashes:
        raise ValueError('Run manifest has no output hashes')
    inputs=manifest.get('inputs',{})
    dataset_hash=inputs.get('dataset',{}).get('sha256',hashes.get('event_features.parquet'))
    events_hash=inputs.get('events',{}).get('sha256')
    if not dataset_hash or sha(dataset_path)!=dataset_hash or not events_hash or sha(events_path)!=events_hash:
        raise ValueError('Supplied input dataset/events hashes disagree with the run manifest')
    for name,digest in hashes.items():
        if sha(output/name)!=digest:
            raise ValueError(f'Output checksum mismatch: {name}')
    frame=attach_outcome_maturity(pd.read_parquet(dataset_path),pd.read_parquet(events_path))
    pred=normalise_predictions(pd.read_parquet(output/'predictions.parquet'))
    plan_path=output/('plan.json' if (output/'plan.json').exists() else 'predeclared_plan.json')
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    if 'model_kinds' in plan:
        for required in ['selected_parameters.csv','validation_selected.csv','trend_rule_tuning.csv']:
            if not (output/required).is_file():
                raise FileNotFoundError(f'Missing planned selection artifact: {required}')
    kinds=plan.get('model_kinds',['logistic_regression','decision_tree'])
    groups=['+'.join(x) for x in plan['feature_sets']]
    expected={(kind,fs) for kind in kinds for fs in groups}
    expected|={('majority_class','none'),('train_prevalence','none'),('speed_ratio_rule','local_speed_ratio'),('speed_trend_rule','history_rule')}
    actual=set(map(tuple,pred[['model','feature_set']].drop_duplicates().to_numpy()))
    if actual!=expected:
        raise ValueError(f'Experiment arms do not match frozen plan: missing={expected-actual}, extra={actual-expected}')
    checked=0
    for (kind,fs,split),part in pred.groupby(['model','feature_set','split']):
        truth=frame.loc[frame.split.eq(split)&frame.label_30m.notna()].set_index('event_id').sort_index()
        p=part.set_index('event_id').sort_index()
        if not p.index.equals(truth.index) or not np.array_equal(p.y_true,truth.label_30m) or not p.prediction_time.equals(truth.prediction_time):
            raise ValueError(f'Prediction cohort/labels/times differ: {kind}/{fs}/{split}')
        checked+=1
    for arm,part in pred.groupby(['model','feature_set']):
        if set(part.split)!=set(['train','validation','test']):
            raise ValueError(f'Missing split in arm {arm}')
    metrics=evaluate_predictions(pred,version_column='experiment_version')
    saved=pd.read_csv(output/'metrics.csv')
    keys=['model','feature_set','horizon_min','split','metric_name']
    joined=metrics.merge(saved,on=keys,suffixes=('_new','_saved'),how='outer',validate='one_to_one',indicator=True)
    if not joined._merge.eq('both').all() or not np.allclose(joined.metric_value_new,joined.metric_value_saved,atol=1e-12,rtol=1e-9,equal_nan=True):
        raise ValueError('Recomputed metrics differ')
    legacy_missing_counts=0
    for count in ['n_rows','n_events','n_positive','n_censored','n_missing_feature']:
        missing=joined[count+'_saved'].isna()
        legacy_allowed=missing & joined.metric_name.eq('macro_f1') & ('model_kinds' not in plan)
        legacy_missing_counts+=int(legacy_allowed.sum())
        if (missing & ~legacy_allowed).any() or not np.array_equal(joined.loc[~missing,count+'_new'],joined.loc[~missing,count+'_saved']):
            raise ValueError(f'Saved metric sample counts differ: {count}')
    tuning=pd.read_csv(output/'tuning.csv')
    expected_fitted={(kind,fs) for kind in kinds for fs in groups}
    if set(map(tuple,tuning[['model','feature_set']].drop_duplicates().to_numpy()))!=expected_fitted:
        raise ValueError('Missing or extra tuning arms')
    rules_path=output/('configs/supervised_rules.json' if (output/'configs/supervised_rules.json').exists() else 'supervised_models.json')
    rules=json.loads(rules_path.read_text(encoding='utf-8'))
    parameter_keys={'logistic_regression':['C','class_weight'],'decision_tree':['max_depth','min_samples_leaf','class_weight']}
    winners=[]
    for (kind,fs),part in tuning.groupby(['model','feature_set']):
        if kind in parameter_keys:
            names=parameter_keys[kind]
            candidates=[dict(zip(names,values)) for values in itertools.product(*(rules[kind][name] for name in names))]
        else:
            candidates=plan['extended_candidates'][kind]
        ordered=part.sort_values('candidate_id')
        if ordered.candidate_id.tolist()!=list(range(len(candidates))) or [json.loads(x) for x in ordered.parameters]!=candidates:
            raise ValueError(f'Tuning candidate grid differs from frozen rules: {kind}/{fs}')
        selected=part.loc[part.selected]
        if len(selected)!=1 or selected.iloc[0].candidate_id!=part.sort_values(['validation_log_loss','candidate_id']).iloc[0].candidate_id:
            raise ValueError('Candidate selection is not the validation minimum')
        winners.append(selected.iloc[0])
    winners=pd.DataFrame(winners)
    if (output/'selected_parameters.csv').exists():
        chosen=pd.read_csv(output/'selected_parameters.csv')
        fields=['model','feature_set','candidate_id','parameters']
        if not chosen[fields].sort_values(fields[:2]).reset_index(drop=True).equals(winners[fields].sort_values(fields[:2]).reset_index(drop=True)):
            raise ValueError('Saved selected parameters disagree with tuning winners')
    if (output/'validation_selected.csv').exists():
        expected_selection=summarise_predictions(pred)[3]
        chosen=pd.read_csv(output/'validation_selected.csv')
        fields=['model','feature_set','is_overall_choice']
        if not chosen[fields].sort_values('model').reset_index(drop=True).equals(expected_selection[fields].sort_values('model').reset_index(drop=True)):
            raise ValueError('Saved feature-group selection disagrees with validation loss')
    contract_path=output/('configs/contract.json' if (output/'configs/contract.json').exists() else 'experiment_contract.json')
    benchmark_path=output/('configs/benchmark_rules.json' if (output/'configs/benchmark_rules.json').exists() else 'benchmarks.json')
    contract=ExperimentContract.from_path(contract_path)
    rules_prediction=benchmark_predictions(frame,contract,BenchmarkRules.from_path(benchmark_path))
    trend,trend_tuning=add_trend(frame)
    if (output/'trend_rule_tuning.csv').exists():
        saved_trend=pd.read_csv(output/'trend_rule_tuning.csv')
        if len(saved_trend)!=len(trend_tuning) or not np.allclose(saved_trend.threshold,trend_tuning.threshold) or not np.array_equal(saved_trend.selected,trend_tuning.selected) or not np.allclose(saved_trend.validation_macro_f1,trend_tuning.validation_macro_f1):
            raise ValueError('Saved trend-rule selection differs')
    arm_keys=['model','feature_set','split','event_id']
    rules_check=pd.concat([rules_prediction,trend]).merge(pred,on=arm_keys,suffixes=('_new','_saved'),validate='one_to_one')
    if len(rules_check)!=len(rules_prediction)+len(trend) or not np.array_equal(rules_check.y_pred_new,rules_check.y_pred_saved) or not np.allclose(rules_check.y_score_new,rules_check.y_score_saved,atol=1e-12,rtol=0):
        raise ValueError('Saved benchmark predictions differ from frozen rules')
    fitted=joblib.load(output/'fitted_pipelines.joblib')
    fitted_keys={({'logistic':'logistic_regression','tree':'decision_tree'}.get(k,k),fs) for k,fs in fitted}
    if fitted_keys!=expected_fitted or len(fitted)!=len(expected_fitted):
        raise ValueError('Saved fitted pipelines do not match all planned supervised arms')
    max_diff=0.0
    for (kind,fs),model in fitted.items():
        kind={'logistic':'logistic_regression','tree':'decision_tree'}.get(kind,kind)
        winner=winners.loc[winners.model.eq(kind)&winners.feature_set.eq(fs)].iloc[0]
        actual_params=base_pipeline(model).named_steps['classifier'].get_params()
        if any(actual_params[key]!=value for key,value in json.loads(winner.parameters).items()):
            raise ValueError('Fitted parameters disagree with validation-selected parameters')
        val_metric=metrics.loc[metrics.model.eq(kind)&metrics.feature_set.eq(fs)&metrics.split.eq('validation')&metrics.metric_name.eq('log_loss')].iloc[0].metric_value
        if not np.isclose(val_metric,winner.validation_log_loss,atol=1e-12,rtol=1e-9):
            raise ValueError('Selected tuning loss disagrees with validation predictions')
        columns=list(base_pipeline(model).named_steps['preprocess'].feature_names_in_)
        part=pred.loc[pred.model.eq(kind)&pred.feature_set.eq(fs)]
        x=frame.set_index('event_id').loc[part.event_id,columns]
        probability=model.predict_proba(x)[:,1]
        threshold=float(plan.get('threshold',plan.get('classification_threshold',rules['decision_threshold'])))
        if not np.array_equal((probability>=threshold).astype(int),part.y_pred.to_numpy()):
            raise ValueError(f'Saved decisions disagree with frozen threshold: {kind}/{fs}')
        delta=float(np.abs(probability-part.y_score.to_numpy()).max())
        max_diff=max(max_diff,delta)
        if not np.allclose(probability,part.y_score,atol=1e-12,rtol=0):
            raise ValueError(f'Saved pipeline predictions differ: {kind}/{fs}')
    confusion=pd.read_csv(output/'confusion_matrices.csv')
    confusion_keys=['model','feature_set','split','horizon_min']
    expected_confusion=pred[confusion_keys].drop_duplicates()
    paired_confusion=expected_confusion.merge(confusion,on=confusion_keys,how='outer',validate='one_to_one',indicator=True)
    if not paired_confusion._merge.eq('both').all():
        raise ValueError('Missing or extra confusion matrices')
    for row in confusion.itertuples():
        part=pred.loc[pred.model.eq(row.model)&pred.feature_set.eq(row.feature_set)&pred.split.eq(row.split)]
        actual_cm=confusion_matrix(part.y_true,part.y_pred,labels=[0,1]).ravel()
        if not np.array_equal(actual_cm,[row.tn,row.fp,row.fn,row.tp]) or int(actual_cm.sum())!=len(part) or row.n!=len(part):
            raise ValueError('Confusion matrix disagrees with predictions')
    report=dict(status='passed',arms=len(actual),paired_arm_splits=checked,prediction_rows=len(pred),
        metric_rows=len(metrics),pipelines=len(fitted),max_pipeline_score_difference=max_diff,
        legacy_missing_count_cells=legacy_missing_counts,
        compatibility_note='Historical backfilled Macro-F1 metadata gaps were recomputed from authenticated predictions; original files retained' if legacy_missing_counts else 'All saved counts verified',
        cohort_counts=metrics.groupby(['model','feature_set','horizon_min','split'])[['n_rows','n_events','n_positive','n_censored','n_missing_feature']].first().reset_index().to_dict('records'),
        manifest_sha256=sha(output/'manifest.json'),scientific_approval='pending_team_review')
    target=report_path if report_path is not None else output/'workflow_verification.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--events',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify_run(args.run_dir,args.dataset,args.events,args.report),indent=2))
