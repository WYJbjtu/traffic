"""SYNTHETIC checks only; these data and scores are not research results."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from traffic_recovery.models.contract import ExperimentContract
from traffic_recovery.models.extended_classifiers import (
    ExtendedRules, attach_outcome_maturity, base_pipeline, temporal_calibration_masks, train_extended,
)
from traffic_recovery.models.evaluation import evaluate_predictions

ROOT = Path(__file__).resolve().parents[1]
REAL = ExperimentContract.from_path(ROOT/'configs/tianhao_long_window_30m_contract.json')
CONTRACT = replace(REAL,feature_groups={'local':REAL.feature_groups['local']},
    availability_columns=('feature_max_available_at',),
    availability_requirements={'feature_max_available_at':REAL.feature_groups['local']})
RULES = ExtendedRules.from_path(ROOT/'configs/tianhao_extended_models.json')
SMALL = replace(RULES,l1={**RULES.l1,'C':[1.],'class_weight':[None]},
    svm={**RULES.svm,'C':[1.],'gamma':['scale'],'class_weight':[None]})


def synthetic_frame():
    times=pd.DatetimeIndex([*pd.date_range('2024-06-01',periods=8,freq='2h',tz='Asia/Hong_Kong'),
        *pd.date_range('2024-07-02',periods=8,freq='2h',tz='Asia/Hong_Kong'),
        *pd.date_range('2025-01-02',periods=6,freq='2h',tz='Asia/Hong_Kong'),
        *pd.date_range('2026-01-02',periods=6,freq='2h',tz='Asia/Hong_Kong')])
    n=len(times)
    return pd.DataFrame(dict(event_id=[f'SYNTHETIC-EXT-{i}' for i in range(n)],prediction_time=times,
        split=['train']*16+['validation']*6+['test']*6,label_30m=pd.Series([0,1]*(n//2),dtype='Int8'),
        detector_id=['SYNTHETIC-D']*n,direction=['North']*n,lane_id=['SYNTHETIC-L']*n,
        speed_kmh=[10.,50.]*4+[100.,200.]*4+[10.,50.]*6,speed_ratio=[.2,.7]*(n//2),baseline_kmh=[71.]*n,
        valid_slots=[4.]*n,onset_observed_minutes=[10.]*n,speed_change_15m_ratio=[-.2,.1]*(n//2),
        feature_max_available_at=times-pd.Timedelta(minutes=1),outcome_maturity_at=times+pd.Timedelta(minutes=70)))


def train(frame,kind):
    return train_extended(frame,CONTRACT,SMALL,kind=kind,feature_groups=('local',))


def test_l1_shared_probability_interpretation_and_metric_schema():
    r=train(synthetic_frame(),'logistic_l1')
    assert r.predictions.y_score.between(0,1).all() and r.predictions.model.eq('logistic_l1').all()
    assert r.interpretation.importance_type.eq('coefficient').all()
    assert r.interpretation.feature.tolist()==list(CONTRACT.feature_groups['local'])
    assert r.tuning.selected.sum()==1
    assert 'macro_f1' in set(evaluate_predictions(r.predictions,version_column='model_version').metric_name)


def test_svm_preprocessor_fits_early_train_only_and_stays_frozen():
    r=train(synthetic_frame(),'svm_rbf');base=base_pipeline(r.fitted[30])
    assert base.named_steps['classifier'].shape_fit_[0]==8
    numeric=base.named_steps['preprocess'].named_transformers_['numeric']
    assert numeric.named_steps['impute'].statistics_[0]==30.
    assert numeric.named_steps['scale'].mean_[0]==30.
    assert len(r.fitted[30].calibrated_classifiers_)==1 and r.interpretation.empty
    assert r.calibration_audit.svm_role.value_counts().to_dict()=={'base_fit':8,'sigmoid_calibration':8}


def test_validation_test_labels_do_not_fit_or_calibrate_svm():
    a=train(synthetic_frame(),'svm_rbf');frame=synthetic_frame();m=frame.split.ne('train')
    frame.loc[m,'label_30m']=1-frame.loc[m,'label_30m'];b=train(frame,'svm_rbf')
    ca=a.fitted[30].calibrated_classifiers_[0].calibrators[0]
    cb=b.fitted[30].calibrated_classifiers_[0].calibrators[0]
    assert (ca.a_,ca.b_)==(cb.a_,cb.b_)
    np.testing.assert_array_equal(a.predictions.y_score,b.predictions.y_score)


@pytest.mark.parametrize('kind',['logistic_l1','svm_rbf'])
def test_test_label_perturbation_does_not_select_candidates(kind):
    rules=replace(SMALL,l1={**SMALL.l1,'C':[.1,1.]},svm={**SMALL.svm,'C':[.1,1.]})
    f=synthetic_frame();a=train_extended(f,CONTRACT,rules,kind=kind,feature_groups=('local',))
    f.loc[f.split.eq('test'),'label_30m']=1-f.loc[f.split.eq('test'),'label_30m']
    b=train_extended(f,CONTRACT,rules,kind=kind,feature_groups=('local',))
    pd.testing.assert_frame_equal(a.tuning,b.tuning)
    np.testing.assert_array_equal(a.predictions.y_score,b.predictions.y_score)


def test_cross_boundary_outcomes_are_purged():
    f=synthetic_frame();f.loc[0,'outcome_maturity_at']=RULES.calibration_start+pd.Timedelta(minutes=1)
    fit,cal,audit=temporal_calibration_masks(f,CONTRACT,RULES)
    assert not fit.iloc[0] and not cal.iloc[0] and fit.sum()==7 and cal.sum()==8
    assert audit.loc[audit.event_id.eq('SYNTHETIC-EXT-0'),'svm_role'].item()=='purged'


@pytest.mark.parametrize('failure',['missing','naive','null','short','late_calibration','one_class'])
def test_unsafe_calibration_is_rejected(failure):
    f=synthetic_frame();rules=SMALL
    if failure=='missing':f=f.drop(columns='outcome_maturity_at')
    elif failure=='naive':f['outcome_maturity_at']=f.outcome_maturity_at.dt.tz_localize(None)
    elif failure=='null':f.loc[0,'outcome_maturity_at']=pd.NaT
    elif failure=='short':f.loc[0,'outcome_maturity_at']=f.prediction_time.iloc[0]
    elif failure=='late_calibration':rules=replace(rules,calibration_start=CONTRACT.validation_start)
    else:f.loc[f.prediction_time.lt(rules.calibration_start),'label_30m']=0
    with pytest.raises(ValueError):train_extended(f,CONTRACT,rules,kind='svm_rbf',feature_groups=('local',))


@pytest.mark.parametrize('field',['prediction_time','label_30m','split','event_id'])
def test_audit_cannot_be_attached_to_different_cohort(field):
    f=synthetic_frame();e=f.copy()
    if field=='prediction_time':e.loc[0,field]+=pd.Timedelta(minutes=1)
    elif field=='label_30m':e.loc[0,field]=1
    elif field=='split':e.loc[0,field]='test'
    else:e.loc[0,field]='WRONG-EVENT'
    with pytest.raises(ValueError):attach_outcome_maturity(f.drop(columns='outcome_maturity_at'),e)


@pytest.mark.parametrize('field,value',[('C',[0]),('C',[float('nan')]),('class_weight',['wrong'])])
def test_invalid_rules_fail_before_fitting(field,value):
    with pytest.raises(ValueError):replace(SMALL,l1={**SMALL.l1,field:value}).validate()


def test_only_30m_scope_is_supported():
    with pytest.raises(ValueError,match='30-minute'):
        train_extended(synthetic_frame(),replace(CONTRACT,horizons=(15,30,60)),SMALL,
                       kind='logistic_l1',feature_groups=('local',))


def test_unknown_label_is_not_a_negative_example():
    f=synthetic_frame();f.loc[f.split.eq('test').idxmax(),'label_30m']=pd.NA;r=train(f,'logistic_l1')
    test=r.predictions.loc[r.predictions.split.eq('test')]
    assert len(test)==5 and test.n_censored_in_split.eq(1).all()


def test_cli_outputs_and_no_overwrite(tmp_path,monkeypatch):
    scripts=ROOT/'experiments/tianhao';monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('synthetic_extended_runner',scripts/'run_extended_models.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    monkeypatch.setattr(runner,'repository_state',lambda:dict(commit='SYNTHETIC-COMMIT',dirty=True))
    f=synthetic_frame();data=tmp_path/'dataset.parquet';events=tmp_path/'events.parquet'
    f.drop(columns='outcome_maturity_at').to_parquet(data);f.to_parquet(events)
    payload=json.loads((ROOT/'configs/tianhao_long_window_30m_contract.json').read_text())
    payload.update(feature_groups={'local':list(CONTRACT.feature_groups['local'])},
        availability_columns=['feature_max_available_at'],availability_requirements={'feature_max_available_at':list(CONTRACT.feature_groups['local'])})
    cp=tmp_path/'contract.json';cp.write_text(json.dumps(payload))
    rules=json.loads((ROOT/'configs/tianhao_extended_models.json').read_text())
    rules['logistic_l1'].update(C=[1],class_weight=[None]);rules['svm_rbf'].update(C=[1],gamma=['scale'],class_weight=[None])
    rp=tmp_path/'rules.json';rp.write_text(json.dumps(rules));output=tmp_path/'new-results'
    kwargs=dict(dataset_path=data,events_path=events,contract_path=cp,rules_path=rp,
        supervised_rules_path=ROOT/'configs/supervised_models.json',benchmark_rules_path=ROOT/'configs/benchmarks.json',output=output)
    m=runner.run(**kwargs)
    assert m['completed'] and m['supervised_arms']==4 and m['prediction_rows']==len(f)*8
    assert m['run']['run_id'] and m['run']['started_at'] and m['run']['lock']['sha256']
    assert m['run']['git']==dict(commit='SYNTHETIC-COMMIT',dirty=True)
    assert m['run']['split_boundaries']['test_start']==CONTRACT.test_start.isoformat()
    assert (output/'fitted_pipelines.joblib').is_file() and (output/'calibration_audit.csv').is_file()
    assert pd.read_csv(output/'validation_selected.csv').model.nunique()==4
    from verify_workflow import verify_run
    assert verify_run(output,data,events)['arms']==8
    read_csv=pd.read_csv
    for filename in ['tuning.csv','confusion_matrices.csv','metrics.csv','validation_selected.csv']:
        def altered_csv(path,*args,**kwargs):
            table=read_csv(path,*args,**kwargs)
            if Path(path).name==filename:
                table=table.copy()
                if filename in ['tuning.csv','confusion_matrices.csv']:table=table.iloc[1:]
                elif filename=='metrics.csv':table.loc[0,'n_rows']+=1
                else:table.loc[0,'feature_set']='SYNTHETIC-WRONG-GROUP'
            return table
        with monkeypatch.context() as local:
            local.setattr(pd,'read_csv',altered_csv)
            with pytest.raises(ValueError):verify_run(output,data,events)
    read_parquet=pd.read_parquet
    changed_predictions=read_parquet(output/'predictions.parquet')
    mask=changed_predictions.model.eq('logistic_l1')
    changed_predictions.loc[mask,'y_pred']=1-changed_predictions.loc[mask,'y_pred']
    changed_metrics,_,changed_confusion,_=runner.summarise_predictions(changed_predictions)
    def changed_parquet(path,*args,**kwargs):
        return changed_predictions.copy() if Path(path).name=='predictions.parquet' else read_parquet(path,*args,**kwargs)
    def changed_csv(path,*args,**kwargs):
        if Path(path).name=='metrics.csv':return changed_metrics.copy()
        if Path(path).name=='confusion_matrices.csv':return changed_confusion.copy()
        return read_csv(path,*args,**kwargs)
    with monkeypatch.context() as local:
        local.setattr(pd,'read_parquet',changed_parquet);local.setattr(pd,'read_csv',changed_csv)
        with pytest.raises(ValueError,match='frozen threshold'):verify_run(output,data,events)
    changed=f.drop(columns='outcome_maturity_at').copy();changed.loc[0,'speed_kmh']+=1
    changed.to_parquet(data)
    with pytest.raises(ValueError,match='input dataset/events hashes'):verify_run(output,data,events)
    f.drop(columns='outcome_maturity_at').to_parquet(data)
    import joblib
    pipelines=joblib.load(output/'fitted_pipelines.joblib');pipelines.pop(next(iter(pipelines)))
    joblib.dump(pipelines,output/'fitted_pipelines.joblib')
    manifest=json.loads((output/'manifest.json').read_text());manifest['outputs_sha256']['fitted_pipelines.joblib']=runner.sha(output/'fitted_pipelines.joblib')
    (output/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='fitted pipelines'):verify_run(output,data,events)
    with pytest.raises(FileExistsError):runner.run(**kwargs)


@pytest.mark.parametrize('split,boundary',[('train','2025-01-01'),('validation','2026-01-01')])
def test_outer_split_outcome_windows_cannot_overlap(split,boundary):
    f=synthetic_frame();i=f.split.eq(split).idxmax()
    f.loc[i,'outcome_maturity_at']=pd.Timestamp(boundary,tz='Asia/Hong_Kong')
    with pytest.raises(ValueError,match='next split boundary'):
        train(f,'logistic_l1')
