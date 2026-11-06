"""Independent Proposal target; never mutates lane-observed-confirmation-v1.

Detector/direction aggregation is performed by the companion source runner.
Observed five-minute persistence is not proof of continuous physical recovery.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd

KEY = ["detector_id", "direction"]
VERSION = "detector-direction-recovery-start-v2"


def contextual_reference(bins: pd.DataFrame, fit_start: pd.Timestamp,
                         fit_end: pd.Timestamp, min_bins: int = 12) -> pd.DataFrame:
    """Training-past p85 in exact HKT weekday/hour cells, no global fallback.

    Require at least three distinct observation dates per cell. The fit interval
    is reserved, so its observations never become evaluation events.
    """
    if fit_start.tzinfo is None or fit_end.tzinfo is None or fit_start >= fit_end:
        raise ValueError("Require ordered aware reference boundaries")
    if fit_end > pd.Timestamp("2025-01-01", tz="Asia/Hong_Kong"):
        raise ValueError("Reference must end inside training period")
    history = bins.loc[(bins.timestamp >= fit_start) & (bins.timestamp < fit_end)
                       & (bins.available_at < fit_end) & bins.usable
                       & bins.speed_kmh.gt(0) & np.isfinite(bins.speed_kmh)].copy()
    local = history.timestamp.dt.tz_convert("Asia/Hong_Kong")
    history["weekday"], history["hour"], history["date"] = local.dt.dayofweek, local.dt.hour, local.dt.date
    ref = history.groupby(KEY + ["weekday", "hour"], observed=True).agg(
        baseline_kmh=("speed_kmh", lambda s: s.quantile(.85)),
        reference_bins=("speed_kmh", "size"), reference_days=("date", "nunique")).reset_index()
    ref = ref.loc[(ref.reference_bins >= min_bins) & (ref.reference_days >= 3)].copy()
    ref["reference_fit_end"] = fit_end
    return ref


def proposal_events(bins: pd.DataFrame, reference: pd.DataFrame, *,
                    start: pd.Timestamp, end: pd.Timestamp,
                    congestion: float = .5, recovery: float = .8) -> pd.DataFrame:
    """One prediction per witnessed episode; start-in-horizon + 10m persistence.

    Low uses strict < as in Proposal; high uses >=. Three high bin endpoints
    witness ten elapsed minutes. Only starts strictly after prediction qualify;
    delayed already-started recovery is retained as unknown (prevalent outcome).
    Negatives require all observations through horizon + 10m; no backdating an
    old confirmation label. Missing bins end an episode and force recovered
    rearming. Split purges cover input, outcome and availability windows.
    """
    if not 0 < congestion < recovery <= 1:
        raise ValueError("Invalid thresholds")
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Require aware ordered event bounds")
    if bins.empty:
        return pd.DataFrame()
    if bins[KEY].drop_duplicates().shape[0] != 1 or bins.timestamp.duplicated().any():
        raise ValueError("Require unique single detector/direction series")
    for col in ("timestamp", "available_at"):
        if not isinstance(bins[col].dtype, pd.DatetimeTZDtype):
            raise ValueError("Require timezone-aware observations and availability")
    if (bins.available_at < bins.timestamp).any():
        raise ValueError("Availability precedes observation")
    identity = {k: str(bins.iloc[0][k]) for k in KEY}
    r = reference.copy()
    if r.duplicated(KEY + ["weekday", "hour"]).any():
        raise ValueError("Duplicate reference cells")
    if len(r) and (r.reference_fit_end > start).any():
        raise ValueError("Reference uses future observations")
    frame = bins.set_index("timestamp").reindex(pd.date_range(start, end, freq="5min", inclusive="left"))
    frame.index.name = "timestamp"
    frame = frame.reset_index()
    for k, v in identity.items(): frame[k] = v
    local = frame.timestamp.dt.tz_convert("Asia/Hong_Kong")
    frame["weekday"], frame["hour"] = local.dt.dayofweek, local.dt.hour
    frame = frame.merge(r, on=KEY + ["weekday", "hour"], how="left", validate="many_to_one")
    ratio = (frame.speed_kmh / frame.baseline_kmh).to_numpy(dtype=float, na_value=np.nan)
    good = frame.usable.fillna(False).to_numpy(bool) & np.isfinite(ratio) & frame.available_at.notna().to_numpy()
    stamps, arrivals = frame.timestamp.tolist(), frame.available_at.tolist()
    baselines = frame.baseline_kmh.to_numpy(dtype=float, na_value=np.nan)
    rows, active = [], None
    armed = False
    low = high = 0
    cooldown = start
    last = None

    def finish(reason, first_high=None, confirmation=None, maturity=None):
        nonlocal active, cooldown
        pred = active["prediction_time"]
        active.update(recovery_start=first_high, recovery_confirmed_at=confirmation,
                      recovery_available_at=maturity, followup_end=last, termination_reason=reason,
                      episode_separated_at=confirmation, episode_separation_available_at=maturity)
        for h in (15, 30, 60):
            deadline = pred + pd.Timedelta(minutes=h)
            prevalent = first_high is not None and first_high <= pred
            if prevalent:
                value, why = pd.NA, "recovery_started_before_prediction"
            elif first_high is not None and first_high <= deadline:
                value, why = 1, "start_within_horizon_sustained_10m"
            elif last >= deadline + pd.Timedelta(minutes=10):
                value, why = 0, "observed_through_horizon_plus_10m"
            else:
                value, why = pd.NA, reason
            active[f"label_{h}m"], active[f"reason_{h}m"] = value, why
        # At least the complete 60+10m outcome window and its 10m closure.
        active["outcome_maturity_at"] = max(pred + pd.Timedelta(minutes=80), maturity or pred)
        rows.append(active)
        cooldown = pred + pd.Timedelta(minutes=60)
        active = None

    for i in range(len(frame)):
        if not good[i]:
            if active is not None: finish("missing_or_invalid_or_reference")
            armed, low, high = False, 0, 0
            continue
        stamp, arrival = stamps[i], arrivals[i]
        last = stamp
        low = low + 1 if ratio[i] < congestion else 0
        high = high + 1 if ratio[i] >= recovery else 0
        if active is not None:
            if high >= 3:
                finish("recovered", stamps[i-2], stamp, arrival)
                armed, low = True, 0
            continue
        if high >= 3:
            armed = True
            if rows and rows[-1]["episode_separated_at"] is None:
                # Later witnessed recovery separates the episode without filling
                # its previously censored outcomes with retrospective positives.
                rows[-1]["episode_separated_at"] = stamp
                rows[-1]["episode_separation_available_at"] = arrival
        if armed and low == 2:
            armed = False
            if arrival <= cooldown or arrival >= end: continue
            token = f"{VERSION}|{identity}|{stamp.isoformat()}|{congestion}|{recovery}"
            active = identity | {"event_id": hashlib.sha256(token.encode()).hexdigest()[:24],
                "onset_time": stamp - pd.Timedelta(minutes=10), "onset_confirmed_at": stamp,
                "prediction_time": arrival, "feature_max_available_at": arrival,
                "baseline_kmh": baselines[i], "speed_ratio": ratio[i],
                "reference_fit_end": frame.reference_fit_end.iloc[i],
                "congestion_ratio": congestion, "recovery_ratio": recovery,
                "definition_version": VERSION}
    if active is not None: finish("period_end")
    out = pd.DataFrame(rows)
    if len(out):
        for h in (15, 30, 60): out[f"label_{h}m"] = out[f"label_{h}m"].astype("Int8")
        for c in ("recovery_start", "recovery_confirmed_at", "recovery_available_at", "followup_end",
                  "episode_separated_at", "episode_separation_available_at"):
            out[c] = pd.to_datetime(out[c], utc=True).dt.tz_convert(start.tz)
        out['outcome_maturity_at']=pd.concat([out.outcome_maturity_at,
            out.episode_separation_available_at],axis=1).max(axis=1)
        lower=pd.Timestamp('2025-01-01',tz=start.tz)
        upper=pd.Timestamp('2026-01-01',tz=start.tz)
        out['split']='purged'
        closed=out.episode_separated_at.notna()
        in_period=out.outcome_maturity_at.lt(end)
        out.loc[closed & in_period & out.outcome_maturity_at.lt(lower),'split']='train'
        out.loc[closed & in_period & out.onset_time.ge(lower) & out.outcome_maturity_at.lt(upper),'split']='validation'
        out.loc[in_period & out.onset_time.ge(upper),'split']='test'
    return out
