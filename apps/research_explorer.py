"""Hong Kong Traffic Recovery — read-only research explorer.

Launch from repository root with the command in docs/research_explorer.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from traffic_recovery.research_viz import (
    METRICS, MODELS, confusion_counts, event_history, join_event_metadata,
    load_artifacts, select_predictions, temporal_summary,
)

ROOT = Path(__file__).resolve().parents[1]
INK, GREEN, RED, MUTED = "#344A5E", "#6C877B", "#A66B59", "#81878B"
PALETTE = [INK, GREEN, RED, "#8B8574", "#687F92"]
NAMES = {"logistic_regression": "Logistic Regression", "decision_tree": "Decision Tree",
         "random_forest": "Random Forest", "hist_gradient_boosting": "HistGradientBoosting",
         "xgboost": "XGBoost", "logistic_l1": "L1 Logistic Regression", "svm_rbf": "RBF SVM"}
STEPS = ["local", "local+history", "local+history+flow"]
st.set_page_config(page_title="HK Traffic Recovery | Research Explorer", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
.stApp {background:#F7F7F4;color:#30363A} .block-container{max-width:1320px;padding-top:1.4rem;padding-bottom:3rem}
h1,h2,h3{font-family:Arial,Helvetica,sans-serif;letter-spacing:-.025em;color:#30363A}
h1{font-size:2rem!important;font-weight:550!important} h2{font-size:1.38rem!important;margin-top:1.4rem!important}
[data-testid="stMetric"]{border-top:1px solid #E7E8E7;padding-top:.65rem}
[data-testid="stMetricValue"]{font-family:ui-monospace,monospace;font-size:1.45rem!important;color:#344A5E}
.kicker{font:600 .72rem ui-monospace,monospace;letter-spacing:.14em;color:#6C877B;text-transform:uppercase}
.rule{border-top:1px solid #D5D9D8;margin:.7rem 0 1.4rem}
.band{border-top:1px solid #D5D9D8;border-bottom:1px solid #D5D9D8;padding:.65rem 0;font: .8rem ui-monospace,monospace;color:#344A5E}
.note{color:#687174;font-size:.86rem;line-height:1.5}
</style>""", unsafe_allow_html=True)


def theme(fig: go.Figure, *, height: int = 340) -> go.Figure:
    """Consistent print-friendly axes and plot background."""
    fig.update_layout(template="simple_white", height=height, paper_bgcolor="#F7F7F4", plot_bgcolor="#F7F7F4",
                      font=dict(family="Arial, sans-serif", color="#30363A", size=12),
                      colorway=PALETTE, margin=dict(l=12, r=16, t=42, b=36),
                      legend=dict(orientation="h", y=-.27, title=None),
                      hoverlabel=dict(bgcolor="#F7F7F4", font_color="#30363A"))
    fig.update_xaxes(showgrid=False, linecolor="#D5D9D8")
    fig.update_yaxes(gridcolor="#E7E8E7", zeroline=False, linecolor="#D5D9D8")
    return fig


@st.cache_data(show_spinner=False)
def artifacts(name: str):
    return load_artifacts(ROOT, name)


@st.cache_data(show_spinner=False)
def local_events(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def section(number: str, title: str, source: str) -> None:
    st.markdown(f'<div class="kicker">{number} / {source}</div>', unsafe_allow_html=True)
    st.subheader(title)


def controls(metrics: pd.DataFrame, *, key: str):
    a, b, c = st.columns([1, 1.5, 1.5])
    horizons = sorted(metrics.horizon_min.unique().tolist())
    horizon = a.selectbox("Horizon · minutes", horizons, index=horizons.index(30) if 30 in horizons else 0, key=key+"h")
    available = metrics.loc[metrics.horizon_min.eq(horizon)]
    models = [m for m in MODELS if m in available.model.unique()]
    model = b.selectbox("Model", models, format_func=lambda x: NAMES[x], key=key+"m")
    sets = available.loc[available.model.eq(model), "feature_set"].drop_duplicates().tolist()
    feature_set = c.selectbox("Feature configuration", sets, index=sets.index("local+history+flow") if "local+history+flow" in sets else 0, key=key+"f")
    return horizon, model, feature_set


def overview(metrics, pred, meta):
    section("01", "The study at a glance", "saved experiments / provisional cohort")
    all_times = pd.to_datetime(pred.prediction_time, utc=True).dt.tz_convert("Asia/Hong_Kong")
    period = f"{all_times.min():%Y.%m} — {all_times.max():%Y.%m}"  # test period, not complete study period
    manifest = json.loads((ROOT / "experiments/member4/model-dataset-manifest-hf.json").read_text(encoding="utf-8"))
    validation = manifest["validation"]
    st.markdown(f'<div class="band">2023.01—2026.09 · 24 SELECTED LANE UNITS · {validation["events"]:,} PROVISIONAL EVENTS &nbsp; / &nbsp; 30-MINUTE PRIMARY TASK &nbsp; / &nbsp; SCIENTIFIC REVIEW PENDING</div>', unsafe_allow_html=True)
    st.caption(f"长窗口、车道单元数量：docs/long_window_data_access.md；事件数量：Member4 数据集 manifest。保存的测试预测时间范围：{period}；不代表全体事件分布。")
    left, right = st.columns([1.8, 1])
    with left:
        section("01.1", "Three windows, three observation denominators", "member4 / all splits")
        rows = pd.DataFrame({"horizon": [15, 30, 60], "known": [validation[f"known_label_{h}m"] for h in (15,30,60)]})
        rows["unknown"] = validation["events"] - rows.known
        fig = go.Figure()
        for col, color in [("known", INK), ("unknown", RED)]:
            fig.add_bar(x=rows.horizon.astype(str)+" min", y=rows[col], name=col, marker_color=color)
        fig.update_layout(barmode="stack", title="Known vs censored / unknown labels · all events", yaxis_title="Events")
        st.plotly_chart(theme(fig, height=340), use_container_width=True)
    with right:
        st.markdown("**Research questions**")
        st.write("01  How does recovery-within-horizon change across 15 / 30 / 60 minutes?\n\n02  Do neighboring-road observations add signal beyond local history?")
        st.markdown("**Interpretation boundary**")
        st.write("The target is *observed sustained recovery confirmation*, not the onset of recovery. Candidate events and fitted thresholds remain provisional. Directed neighbor features are not verified; the spatial comparison is NO-GO.")
    section("01.2", "Positive labels among observed test outcomes", "member4 / test / single baseline arm")
    baseline = pred.loc[pred.model.eq("majority_class") & pred.feature_set.eq("none")]
    denom = baseline.groupby("horizon_min").agg(known=("y_true", "count"), positive=("y_true", "sum")).reset_index()
    denom["rate"] = denom.positive / denom.known
    fig = px.scatter(denom, x="horizon_min", y="rate", size="known", text="known", color_discrete_sequence=[INK],
                     labels={"horizon_min":"Horizon (min)", "rate":"Observed positive share", "known":"Known outcomes"})
    fig.update_traces(textposition="top center", marker_line_width=1, marker_line_color=INK)
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    st.plotly_chart(theme(fig, height=290), use_container_width=True)
    st.caption("This is label prevalence among known test outcomes, not a model prediction or a recovery frequency per road.")


def laboratory(metrics, pred, name):
    section("02", "Model laboratory", f"{name} / test only")
    h, model, fs = controls(metrics, key="lab")
    chosen = metrics.loc[metrics.horizon_min.eq(h) & metrics.model.eq(model) & metrics.feature_set.eq(fs)]
    arm = select_predictions(pred, model=model, feature_set=fs, horizon=h)
    scores = chosen.set_index("metric_name").metric_value.to_dict()
    cells = st.columns(5)
    for cell, metric in zip(cells, METRICS):
        cell.metric(metric.replace("_", " ").upper(), "—" if metric not in scores or pd.isna(scores[metric]) else f"{scores[metric]:.3f}")
    if name == "member4":
        st.caption("Macro-F1 未在 Member4 原始指标表中保存；不与 Tianhao 的 Macro-F1 混用。ROC/PR 使用逐事件保存的 test score 重算曲线；面积以原指标表为准。")
    st.caption(f"{name} · TEST · {h} min · {NAMES[model]} · {fs} · {len(arm):,} known event predictions")
    a, b = st.columns([1.65, 1])
    with a:
        from sklearn.metrics import precision_recall_curve, roc_curve
        if arm.y_true.nunique() == 2 and arm.y_score.notna().all():
            fpr, tpr, _ = roc_curve(arm.y_true, arm.y_score)
            recall, precision, _ = precision_recall_curve(arm.y_true, arm.y_score)
            fig = go.Figure()
            fig.add_scatter(x=fpr, y=tpr, name="ROC · saved scores", line=dict(color=INK, width=2.5))
            fig.add_scatter(x=recall, y=precision, name="PR · saved scores", line=dict(color=RED, width=2.5))
            fig.add_scatter(x=[0,1], y=[0,1], name="chance (ROC)", line=dict(color=MUTED, dash="dot"))
            fig.update_layout(title="Discrimination · ROC and Precision–Recall", xaxis_title="FPR (ROC) / Recall (PR)", yaxis_title="TPR (ROC) / Precision (PR)")
            fig.update_xaxes(range=[0,1]); fig.update_yaxes(range=[0,1])
            st.plotly_chart(theme(fig, height=380), use_container_width=True)
        else:
            st.info("ROC/PR unavailable: score or class missing in this arm.")
    with b:
        matrix = confusion_counts(arm)
        fig = px.imshow(matrix, x=["Pred 0", "Pred 1"], y=["Actual 0", "Actual 1"],
                        text_auto=True, color_continuous_scale=[[0,"#F1F2EF"],[1,INK]], aspect="auto")
        fig.update_layout(title="Confusion matrix · TEST", coloraxis_showscale=False)
        st.plotly_chart(theme(fig, height=380), use_container_width=True)
    st.caption("ROC and PR share axes for compact inspection; they represent different horizontal definitions. Scores are archived out-of-sample predictions; no fitting takes place in this app.")
    with st.expander("Model interpretation · training-fit coefficients / importance"):
        path = ROOT / ("experiments/member4/comparison-hf-v1/interpretation.csv" if name == "member4" else "experiments/tianhao/rerun_20261101/interpretation.csv")
        interpretation = pd.read_csv(path)
        subset = interpretation.loc[interpretation.model.eq(model) & interpretation.feature_set.eq(fs) & interpretation.horizon_min.eq(h)].copy()
        if subset.empty:
            st.info("This run has no saved feature interpretation for this model arm.")
        else:
            subset = subset.assign(magnitude=subset.value.abs()).nlargest(12, "magnitude").sort_values("magnitude")
            fig = px.bar(subset, x="value", y="feature", orientation="h", color_discrete_sequence=[GREEN],
                         title=f"Saved {subset.importance_type.iloc[0]} · not causal importance")
            st.plotly_chart(theme(fig, height=390), use_container_width=True)


def ablation(metrics, other):
    section("03", "Feature ablation", "separate experiment panels / never pooled")
    metric = st.selectbox("Measure", ["roc_auc", "pr_auc", "balanced_accuracy", "f1", "macro_f1"], key="ablmetric")
    a, b = st.columns(2)
    for panel, table, title, horizon, steps in [(a, metrics, "MEMBER4 · 30m · test", 30, STEPS),
                                                 (b, other, "TIANHAO · 30m · test · different run", 30,
                                                  STEPS+["local+history+flow+calendar", "local+history+flow+calendar+weather"])]:
        with panel:
            st.markdown(f"**{title}**")
            sub = table.loc[table.horizon_min.eq(horizon) & table.metric_name.eq(metric) & table.feature_set.isin(steps)].copy()
            sub["model_label"] = sub.model.map(NAMES)
            if sub.empty:
                st.info("Metric not available in this run.")
                continue
            fig = px.line(sub, x="feature_set", y="metric_value", color="model_label", markers=True,
                          category_orders={"feature_set":steps}, color_discrete_map={NAMES[m]: PALETTE[i] for i, m in enumerate(MODELS)},
                          labels={"feature_set":"Feature group", "metric_value":metric, "model_label":"Model"})
            fig.update_traces(line_width=2, marker_size=8)
            fig.update_xaxes(tickangle=-28)
            st.plotly_chart(theme(fig, height=430), use_container_width=True)
    st.caption("History and Flow are local-lane temporal/volume features, NOT verified neighboring-road features. Tianhao Calendar combines time-of-day, weekday and holiday signals; the group delta cannot identify a holiday-only effect. Weather is a station-level proxy. Deltas are descriptive, not causal or statistically tested. Tianhao is a previously viewed test-cohort rerun, not a new blind test.")


def explorer(metrics, pred, name, events_path, bins_path):
    section("04", "Traffic event explorer", f"{name} / authentic saved test predictions")
    h, model, fs = controls(metrics, key="evt")
    arm = select_predictions(pred, model=model, feature_set=fs, horizon=h)
    events = None
    if events_path:
        try:
            events = local_events(events_path)
            arm = join_event_metadata(arm, events)
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"Event data unavailable: {exc}"); events = None
    if events is not None and "detector_id" in arm:
        dets = sorted(arm.detector_id.dropna().astype(str).unique())
        detector = st.selectbox("Detector · test cohort", ["All", *dets])
        if detector != "All": arm = arm.loc[arm.detector_id.astype(str).eq(detector)]
    date = st.text_input("Filter date · YYYY-MM-DD (optional)", key="eventdate")
    if date:
        try:
            day = pd.Timestamp(date)
            arm = arm.loc[pd.to_datetime(arm.prediction_time, utc=True).dt.tz_convert("Asia/Hong_Kong").dt.date.eq(day.date())]
        except ValueError:
            st.warning("Enter a valid ISO date.")
    if arm.empty:
        st.info("No test events for this filter. Clear date or change detector/model."); return
    arm = arm.sort_values("prediction_time")
    ids = arm.event_id.astype(str).tolist()
    event_id = st.selectbox("Observed event · first test event selected by default", ids,
                            format_func=lambda x: f"{x}  /  {arm.loc[arm.event_id.astype(str).eq(x), 'prediction_time'].iloc[0]}")
    row = arm.loc[arm.event_id.astype(str).eq(event_id)].iloc[0]
    l, r = st.columns([1.7, 1])
    with l:
        if events is not None and pd.notna(row.get("detector_id")) and bins_path:
            try:
                history = event_history(Path(bins_path), row)
                if history.empty: st.info("No authentic same-lane pre-prediction bins for this event.")
                else:
                    fig = px.line(history, x="timestamp", y="speed_kmh", markers=True, title="Observed speed · available by prediction",
                                  color_discrete_sequence=[INK], labels={"timestamp":"Observation end (HKT)", "speed_kmh":"Speed (km/h)"})
                    if pd.notna(row.get("baseline_kmh")):
                        baseline = float(row.baseline_kmh)
                        fig.add_hline(y=baseline, line_color=GREEN, annotation_text="Historical reference")
                        for ratio, label in [(0.5,"Onset rule"),(0.8,"Recovery rule")]:
                            fig.add_hline(y=baseline*ratio, line_dash="dot", line_color=RED if ratio == .5 else GREEN, annotation_text=label)
                    st.plotly_chart(theme(fig, height=400), use_container_width=True)
            except (OSError, ValueError, KeyError) as exc: st.error(f"Bins unavailable: {exc}")
        else:
            st.info("Historical speed curve requires local official events.parquet AND cohort_bins.parquet. Saved predictions contain neither detector identity nor lane speed history. No synthetic curve is shown.")
    with r:
        st.markdown(f"**Event** `{row.event_id}`")
        st.write(f"Prediction time (HKT): **{row.prediction_time}**")
        if events is not None and pd.notna(row.get("detector_id")):
            st.write(f"Detector / direction / lane: **{row.detector_id} / {row.direction} / {row.lane_id}**")
        st.markdown(f"**Prediction · {h} minutes · {name} / {NAMES[model]} / {fs}**")
        st.metric("Saved out-of-sample score", f"{row.y_score:.3f}" if pd.notna(row.y_score) else "unavailable")
        st.write(f"Score type: {row.get('score_kind', 'unknown')} · class decision: {row.y_pred}")
        st.markdown("**Observed outcome · retrospective, never a model input**")
        st.write(f"Confirmed within {h} min: **{int(row.y_true) if pd.notna(row.y_true) else 'unknown'}**")
        if events is not None:
            st.write(f"Recovery confirmation time: {row.get('recovery_time', 'not available')}")
    st.caption("Test cohort includes only known labels for this horizon; absence of a row does not imply non-recovery. Full local event table is required for censored events and post-prediction observations.")


def temporal(events_path):
    section("05", "Temporal patterns", "full provisional event table required")
    if not events_path:
        st.info("No full official event table configured. Saved test predictions omit censored events and cannot support unbiased temporal counts, missing-label rates, or holiday inference. Supply a local events.parquet below.")
        return
    try:
        frame = local_events(events_path)
        summary = temporal_summary(frame)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Temporal analysis unavailable: {exc}"); return
    grouped = summary.groupby(["week", "period"], observed=True)[["events", "known", "recovered"]].sum().reset_index()
    grouped["missing_rate"] = 1-grouped.known/grouped.events
    grouped["known_recovery_rate"] = grouped.recovered/grouped.known.replace(0,float("nan"))
    fig = px.bar(grouped, x="period", y="events", color="week", barmode="group", color_discrete_sequence=[INK, RED], title="Event occurrence · HKT clock")
    st.plotly_chart(theme(fig), use_container_width=True)
    fig = px.scatter(grouped, x="period", y="known_recovery_rate", size="known", color="week", color_discrete_sequence=[INK, RED],
                     hover_data=["events", "known", "missing_rate"], title="Recovery share among known outcomes · marker size = known labels")
    fig.update_yaxes(tickformat=".0%", range=[0,1]); st.plotly_chart(theme(fig), use_container_width=True)
    monthly = summary.groupby("month")[["events", "known", "recovered"]].sum().reset_index()
    monthly["missing_rate"] = 1-monthly.known/monthly.events
    fig = px.line(monthly, x="month", y=["events", "known"], title="Monthly event and known-label counts", color_discrete_sequence=[INK, GREEN])
    st.plotly_chart(theme(fig), use_container_width=True)
    st.dataframe(monthly, hide_index=True, use_container_width=True)
    st.caption("Public-holiday and adjacent-day analysis requires versioned official calendar features aligned to this cohort; no date-based holiday guesses are made. Intraday bins are descriptive, not a causal effect. Month comparisons need exposure/coverage denominators before a seasonal claim.")


def network():
    section("06", "Network evidence · NO-GO", "official candidate road subset / historical matching unverified")
    folder = ROOT / "reports/spatial_feasibility"
    quality = json.loads((folder / "quality.json").read_text(encoding="utf-8"))
    st.warning("0 human-verified detector-to-road mappings / 0 approved directed neighbor relationships. Candidate geometry and proximity must NOT enter published spatial ablations.")
    a, b = st.columns([1.8, 1])
    with a:
        st.image(str(folder / "detector_map.png"), caption="Source EPSG:2326 road geometry + current detector locations · candidate selection, NOT a validated historical match", use_container_width=True)
    with b:
        st.markdown("**Evidence ledger · 39 detector-direction units**")
        st.write(f"{quality['source_routes_in_subset']:,} official corridor road segments · {quality['directed_arcs']:,} directed arcs · {quality['endpoint_graph']['weak_components']} weak components")
        st.write(f"{quality['human_verified_connections']} verified connections · {quality['source_supported_candidate_detector_pairs']} candidate detector pairs (review leads only)")
        st.write("23/39 candidate matches ambiguous; 8/39 observed vs metadata direction mismatch. Network snapshot/revision does not certify 2023–2026 historical validity.")
        st.markdown("**Gate to proceed**")
        st.write("Human carriageway/direction match with effective dates; historical road version and TURN/INTERSECTION review; then as-of neighbor-bin availability and paired eligible-row coverage.")
    with st.expander("Candidate matching review table · never scientific features"):
        table = pd.read_csv(folder / "detector_mapping.csv")
        st.dataframe(table[["detector_id", "direction", "route_id", "distance_m", "ambiguous", "review_status"]], hide_index=True, use_container_width=True)
    st.caption("See docs/spatial_feasibility.md for source hashes, map limitations, grade separations and the 40-row all-null spatial diagnostic. No proximity-derived links are drawn here.")


def verified96(page: str, events_path: str, bins_path: str) -> None:
    """Separate 96-lane saved evidence; never join to legacy 24-lane metrics."""
    folder = ROOT / "experiments/tianhao/expanded96_20261104"
    st.warning("96 frozen lane units · recovery_confirmation_v1 (NOT recovery start) · exploratory; historical test exposure. No verified spatial features or source-level volume in this Release.")
    if page == "Network evidence":
        st.info("Official geometry: 36,525 segments / 48,080 candidate arcs. Historical detector mapping approvals: 0; verified directed neighbors: 0; spatial-eligible events: 0. Spatial ablation: NO-GO. Candidate proximity is not approval.")
        st.markdown("See [spatial gate](reports/nov04_integrated_delivery/spatial_gate_decision.md). The old 39-detector map is a different pilot, not a 96-lane map.")
        return
    if page == "Methodology":
        st.write("30-minute confirmed recovery, not Proposal recovery start. Training-only preprocessing; validation-only candidate selection. Weather is a regional station proxy. Flow and spatial experiments are not part of the published 96-lane bundle.")
        return
    table = pd.read_csv(folder / "metrics.csv")
    summary = pd.read_csv(folder / "metrics_summary.csv")
    if page in ("Overview", "Feature ablation"):
        st.subheader("Verified published 96-lane experiment · test split")
        st.caption("30,452 events / 27,858 known labels across splits; 7,008 known test labels; 20 published arms and 557,160 saved predictions. No 24-lane results pooled.")
        metric = st.selectbox("Metric", ["roc_auc", "pr_auc", "macro_f1", "log_loss"], key="verifiedmetric")
        selected = summary.loc[summary.split.eq("test") & summary.model.isin(["logistic_regression", "logistic_l1", "svm_rbf", "decision_tree"])].copy()
        selected["model"] = selected.model.map(NAMES)
        st.dataframe(selected[["model", "feature_set", "n", metric]], hide_index=True, use_container_width=True)
        st.markdown("**Member4 96-lane ensemble · separately prepared Local/History matrix**")
        ensemble = pd.read_csv(ROOT / "reports/nov04_integrated_delivery/model_metrics.csv")
        metric_col = {"pr_auc": "average_precision"}.get(metric, metric)
        ours = ensemble.loc[ensemble.split.eq("test") & ensemble.horizon_min.eq(30) & ensemble.model.isin(["random_forest", "xgboost", "hist_gradient_boosting"])]
        st.dataframe(ours[["model", "feature_set", "n_known", metric_col]], hide_index=True, use_container_width=True)
        st.caption("Ensemble Calendar/Weather outcomes are NOT RUN until the full authentic feature matrix is rebuilt. Published Calendar combines time and holiday effects; these two preparation pipelines are not interchangeable without event/provenance alignment.")
        return
    if page == "Temporal patterns":
        temporal(events_path)
        return
    from sklearn.metrics import precision_recall_curve, roc_curve
    models = ["logistic_regression", "logistic_l1", "svm_rbf", "decision_tree"]
    model = st.selectbox("Published 96-lane model", models, format_func=lambda m: NAMES[m], key="v96model")
    sets = summary.loc[summary.model.eq(model), "feature_set"].drop_duplicates().tolist()
    feature_set = st.selectbox("Published feature configuration", sets, key="v96set")
    # Filter at the Parquet level; avoid loading 557,160 rows for a single view.
    import pyarrow.parquet as pq
    p = pq.read_table(folder / "predictions.parquet", filters=[("split", "=", "test"),
        ("model", "=", model), ("feature_set", "=", feature_set)],
        columns=["event_id", "prediction_time", "y_true", "y_score", "y_pred"]).to_pandas()
    st.caption(f"Official Release · 96 lanes · test · n={len(p):,} · {NAMES[model]} · {feature_set}")
    if page == "Event explorer":
        if not events_path or not bins_path:
            st.info("Configure the authenticated expanded96 events.parquet and cohort_bins.parquet to see observed as-of speed history; saved predictions alone contain no speeds.")
        else:
            event_id = st.selectbox("Test event", p.event_id.astype(str).tolist(), key="v96event")
            row = p.loc[p.event_id.eq(event_id)].iloc[0]
            try:
                event = local_events(events_path).loc[lambda f: f.event_id.eq(event_id)]
                if len(event) != 1:
                    raise ValueError("Event absent or duplicate in configured Release")
                source = event.iloc[0]
                if source.prediction_time != row.prediction_time or int(source.label_30m) != row.y_true:
                    raise ValueError("Configured Release truth differs from published prediction")
                history = event_history(Path(bins_path), source)
                st.line_chart(history.set_index("timestamp").speed_kmh)
                st.write(f"Observed confirmation outcome: {row.y_true}; saved score: {row.y_score:.3f}")
            except (OSError, ValueError, KeyError) as exc:
                st.error(f"Authenticated event history unavailable: {exc}")
        return
    st.subheader("Saved test predictions · ROC / PR and confusion")
    if p.y_true.nunique() == 2:
        fpr, tpr, _ = roc_curve(p.y_true, p.y_score)
        precision, recall, _ = precision_recall_curve(p.y_true, p.y_score)
        fig = go.Figure()
        fig.add_scatter(x=fpr, y=tpr, name="ROC")
        fig.add_scatter(x=recall, y=precision, name="PR")
        st.plotly_chart(theme(fig), use_container_width=True)
    matrix = confusion_counts(p)
    st.plotly_chart(theme(px.imshow(matrix, x=["Pred 0", "Pred 1"], y=["Actual 0", "Actual 1"], text_auto=True)), use_container_width=True)
    st.dataframe(table.loc[table.model.eq(model) & table.feature_set.eq(feature_set) & table.split.eq("test"), ["metric_name", "metric_value"]], hide_index=True)


def methodology():
    section("07", "Methods & limitations", "read the provenance before the score")
    st.markdown('<div class="band">OFFICIAL TD TRAFFIC → COVERAGE FILTER → EVENT CONFIRMATION → PREDICTION-TIME FEATURES → TEMPORAL SPLIT → TRAIN-FITTED MODELS → TEST EVALUATION</div>', unsafe_allow_html=True)
    st.write("**Prediction:** event onset confirmed after two low bins; local speed, history and flow observed by an archive-replay availability time. **Outcome:** three consecutive high 5-minute bins confirm recovery. Within-horizon ≠ at endpoint. Unknown follow-up is censored, not negative.")
    st.write("**Evaluation:** chronological splits and holdout test, exploratory scientific status pending review. Tianhao rerun reuses a previously viewed test cohort. Feature-group improvements are descriptive. No proof of holiday-only causality, network neighbor benefit, or generalization across all HK roads.")
    st.write("**Proposal mismatch:** recovery confirmation time is later than recovery start; provisional lane-level units, thresholds and limited detector coverage constrain the target. Official road candidates have no human-verified mapping/validity for historical event dates. Weather station is regional, not a local road sensor.")
    st.caption("Sources: experiments/member4/comparison-hf-v1/manifest.json; experiments/tianhao/rerun_20261101/README.md; docs/data_contract.md; docs/spatial_feasibility.md")


st.markdown('<div class="kicker">SDSC6004 / Research explorer / 2026</div>', unsafe_allow_html=True)
st.title("HONG KONG TRAFFIC RECOVERY")
st.markdown("A Spatiotemporal Machine Learning Study")
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
page = st.radio("Research sections", ["Overview", "Event explorer", "Model laboratory", "Feature ablation", "Temporal patterns", "Network evidence", "Methodology"], horizontal=True, label_visibility="collapsed")
with st.expander("Data & run configuration · optional local official inputs"):
    experiment = st.selectbox("Dataset / experiment (never pooled)", ["verified96", "member4", "tianhao"], format_func=lambda x: {"verified96": "Verified published 96 lanes · 30m (L1/SVM/LR/DT)", "member4": "Historical 24 lanes · Member4", "tianhao": "Historical 24 lanes · Tianhao"}[x])
    events_path = st.text_input("Optional local official events.parquet (absolute or repo-relative path)")
    bins_path = st.text_input("Optional local official cohort_bins.parquet (file or directory)")
    def resolve(p: str) -> str:
        return str((ROOT / p).resolve()) if p else ""
    events_path, bins_path = resolve(events_path), resolve(bins_path)
try:
    if experiment == "verified96":
        verified96(page, events_path, bins_path)
        st.stop()
    m4, p4, meta = artifacts("member4")
    if page == "Overview": overview(m4, p4, meta)
    elif page == "Network evidence": network()
    elif page == "Methodology": methodology()
    elif page == "Temporal patterns": temporal(events_path)
    elif page == "Feature ablation":
        th, _, _ = artifacts("tianhao")
        ablation(m4, th)
    else:
        metrics, pred, _ = (m4, p4, meta) if experiment == "member4" else artifacts("tianhao")
        if page == "Event explorer": explorer(metrics, pred, experiment, events_path, bins_path)
        else: laboratory(metrics, pred, experiment)
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Saved artifact error (no synthetic fallback): {exc}")
st.markdown('<div class="rule"></div><div class="note">EXPLORATORY · pending scientific review &nbsp; / &nbsp; Saved real experimental artifacts only &nbsp; / &nbsp; No automatic downloads or model retraining</div>', unsafe_allow_html=True)
