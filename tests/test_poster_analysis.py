"""Synthetic statistical/metric tests plus optional authenticated local run checks."""
from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.unified96.run import ROOT, paired_bootstrap
from experiments.unified96.poster_analysis import recompute, error_transitions, verify_run
from experiments.unified96.poster_controls import pooled_s1
from experiments.unified96.poster_handoff import verify_package


def test_cluster_bootstrap_repeats_drawn_detectors_with_correct_weights():
    # Synthetic clusters of unequal size and class balance; deduplicating a draw
    # would produce different percentiles. Explicitly repeat the reference draw.
    left=pd.DataFrame({'event_id':list('abcdef'),'detector_id':['a','a','a','b','c','d'],
        'y_true':[0,1,1,0,0,1],'y_score':[.1,.2,.6,.8,.4,.3]})
    right=left.assign(y_score=[.3,.9,.7,.6,.1,.2])
    result=paired_bootstrap(left,right,replicates=80,seed=73)
    rng=np.random.default_rng(73); groups=[np.where(left.detector_id.eq(x))[0] for x in sorted(left.detector_id.unique())]
    deltas=[];invalid=0
    for _ in range(80):
        ix=np.concatenate([groups[i] for i in rng.integers(0,4,4)])
        y=left.y_true.to_numpy()[ix]
        if len(np.unique(y))<2:invalid+=1;continue
        deltas.append(roc_auc_score(y,right.y_score.to_numpy()[ix])-roc_auc_score(y,left.y_score.to_numpy()[ix]))
    assert result['invalid_single_class']==invalid
    assert result['roc_auc']['valid_resamples']==len(deltas)
    np.testing.assert_allclose(result['roc_auc']['ci_95_percentile'],np.quantile(deltas,[.025,.975]))
    identical=paired_bootstrap(left,left,replicates=20,seed=73)
    assert identical['roc_auc']['ci_95_percentile']==[0.,0.]


def test_recomputed_metrics_and_error_categories():
    t=pd.Timestamp('2026-01-01',tz='Asia/Hong_Kong')
    a=pd.DataFrame({'event_id':list('abcd'),'detector_id':list('abcd'),'prediction_time':[t]*4,
        'y_true':[0,1,1,0],'y_score':[.1,.2,.3,.4],'y_pred':[0,0,0,0]})
    b=a.assign(y_score=[.2,.4,.8,.8],y_pred=[0,0,1,1])
    errors=error_transitions(a,b)
    assert [errors[k] for k in ['both_correct','both_wrong','only_spatial_correct','only_base_correct']]==[1,1,1,1]
    values=recompute(b)
    assert [values[k] for k in ['tn','fp','fn','tp']]==[1,1,1,1]
    with pytest.raises(ValueError,match='probability'):
        recompute(b.assign(y_score=[np.nan,.4,.8,.8]))
    with pytest.raises(ValueError,match='same events'):
        error_transitions(a,b.assign(prediction_time=t+pd.Timedelta(minutes=1)))


def test_undirected_pool_missing_is_not_zero():
    frame=pd.DataFrame({'upstream_observed_count':[1,0], 'downstream_observed_count':[2,0]})
    for side,values in [('upstream',[10.,np.nan]),('downstream',[40.,np.nan])]:
        for field in ['mean_speed_kmh','mean_ratio','mean_age_minutes','coverage']:
            frame[side+'_'+field]=values
    result=pooled_s1(frame)
    assert result.upstream_mean_speed_kmh.iloc[0]==30.
    assert result.downstream_mean_speed_kmh.iloc[0]==30.
    assert pd.isna(result.upstream_mean_speed_kmh.iloc[1])
    assert result.upstream_missing.tolist()==[0,1]
    assert result.upstream_observed_count.tolist()==[3,0]


def test_real_32_arm_local_predictions_when_available():
    run=ROOT/'data/local/unified96/p1-cw-matrix-v2-20261108'
    if not run.is_dir():pytest.skip('Authenticated large local predictions not distributed in Git')
    predictions,metrics,manifest=verify_run(run)
    assert len(predictions)==275616 and len(metrics)==64
    assert manifest['split_counts']=={'train':7611,'validation':4680,'test':3933}


def test_published_poster_package_when_available():
    folder=ROOT/'deliverables/poster_handoff/p1-cw-final-20261108-v1'
    if not folder.is_dir():pytest.skip('Poster package not generated yet')
    receipt=verify_package(folder)
    assert receipt['status']=='passed' and receipt['metric_rows_checked']==64
    speech=(folder/'05_presentation_4m30s_en.md').read_text(encoding='utf-8')
    import re
    body=speech.split('<!-- SCRIPT_START -->')[1].split('<!-- SCRIPT_END -->')[0]
    actual=len(re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b",body))
    assert f'**{actual}**' in speech
