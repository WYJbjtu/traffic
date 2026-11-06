"""Six evidence-backed views embedded by apps/research_explorer.py."""
from __future__ import annotations

import json
import os
from math import atan2, degrees
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pyarrow.dataset as ds
import pydeck as pdk
import streamlit as st

from traffic_recovery import research96 as data
from traffic_recovery.network.map_layers import available_tiles, load_tile

ROOT = Path(os.environ.get("RESEARCH96_DATA_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()
NETWORK = ROOT / "data/local/network-full/v1"
BLUE, TEAL, AMBER, RED = "#344A5E", "#21867A", "#C68B44", "#A65A50"
MODEL_NAMES = {"random_forest": "Random Forest", "xgboost": "XGBoost"}
POP_NAMES = {"INFERRED_EXPLORATORY": "P1 · Broad inferred network",
             "HIGH_CONFIDENCE_INFERRED": "P2 · High-confidence inferred network",
             "INDEPENDENTLY_VERIFIED": "P3 · Independently verified (NO-GO)"}
METRIC_NAMES = {"roc_auc": "ROC-AUC", "average_precision": "PR-AUC", "macro_f1": "Macro-F1",
                "balanced_accuracy": "Balanced accuracy", "precision": "Precision", "recall": "Recall",
                "brier": "Brier score", "log_loss": "Log loss"}


@st.cache_data(show_spinner=False)
def get_mappings() -> pd.DataFrame:
    return data.mappings(ROOT)


@st.cache_data(show_spinner=False)
def get_neighbors(population: str) -> pd.DataFrame:
    return data.neighbors(ROOT, population)


@st.cache_data(show_spinner=False)
def get_events() -> pd.DataFrame:
    return data.release_events(ROOT)


@st.cache_data(show_spinner=False)
def get_metrics(controls: bool = False) -> pd.DataFrame:
    return data.metrics(ROOT, controls=controls)


@st.cache_data(show_spinner=False)
def get_tile(tile: str) -> pd.DataFrame:
    return load_tile(NETWORK, tile)


@st.cache_data(show_spinner=False)
def get_routes(ids: tuple[str, ...]) -> dict[str, list[list[float]]]:
    return data.route_paths(ROOT, set(ids))


@st.cache_data(show_spinner=False)
def get_bins(detector: str, direction: str, lane: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return data.observed_bins(ROOT, detector, direction, lane, start, end)


@st.cache_data(show_spinner=False)
def get_lineage(event_id: str, population: str) -> pd.DataFrame:
    event = get_events().set_index("event_id").loc[event_id]
    event["event_id"] = event_id
    return data.event_lineage(ROOT, event, population)


@st.cache_data(show_spinner=False)
def get_features(event_id: str, population: str) -> pd.Series:
    event = get_events().set_index("event_id").loc[event_id]
    event["event_id"] = event_id
    return data.event_features(ROOT, event, population)


@st.cache_data(show_spinner=False)
def observed_event_ids(population: str) -> set[str]:
    path = data.verified_file(ROOT, "data/local/spatial96/inferred-v2/event_neighbor_lineage.parquet")
    rows = pd.read_parquet(path, columns=["event_id", "population"])
    return set(rows.loc[rows.population.eq(population), "event_id"].astype(str))


def _note(message: str) -> None:
    st.caption(message)


def _event_choice(detector: str | None = None, *, key: str = "event96") -> pd.Series | None:
    try:
        events = get_events()
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"真实事件表不可用：{exc}")
        return None
    if detector:
        events = events.loc[events.detector_id.eq(detector)]
    if events.empty:
        st.info("该探测器没有已记录拥堵事件。")
        return None
    events = events.sort_values("prediction_time")
    ids = events.event_id.astype(str).tolist()
    labels = dict(zip(ids, events.prediction_time.dt.strftime("%Y-%m-%d %H:%M")))
    observed = observed_event_ids("INFERRED_EXPLORATORY")
    first_observed = next((i for i, eid in enumerate(ids) if eid in observed), 0)
    chosen = st.selectbox("真实拥堵事件 · 预测时点（香港时间）", ids, key=key,
                          index=first_observed,
                          format_func=lambda eid: f"{labels[eid]} · {eid}")
    return events.loc[events.event_id.eq(chosen)].iloc[0]


def overview() -> None:
    st.subheader("研究概览 / Research overview")
    st.markdown("**问题：** 预测香港道路拥堵在 15、30、60 分钟内是否得到*持续恢复确认*；比较本地历史与推断路网邻路信息。")
    st.info("96 个冻结车道单位 · 94 个有事件 · 30,452 个真实恢复事件 · 35,782,769 条五分钟交通记录。当前空间实验为 30 分钟；其余时窗的空间结果不可用。")
    st.warning("推断路网探索性空间模型已经训练并评估。独立核验的历史路网实验仍不可用（P3：0 条获批连接）。")
    a, b = st.columns(2)
    with a:
        st.markdown("#### 已保存的研究证据")
        st.write("P1：广义推断邻路；P2：高置信推断邻路；M0–M5：本地历史到空间特征消融；C1–C5：地理、无向、有向、置换、高置信对照。")
        st.write("原始交通数据与官方路网按 SHA-256 清单认证。所有探索图形只读取已有文件。")
    with b:
        st.markdown("#### 阅读顺序")
        st.write("先在「道路网络」核查检测器与路线，再在「事件」查看预测前输入和事后结果，最后比较同事件模型指标与对照。")
        st.write("2026 官方路网快照回溯套用于 2023–2026 交通事件；历史映射和物理连接尚未独立核准。")
    st.markdown("#### 数据可用性")
    paths = {
        "Git：轻量空间指标": ROOT / "reports/spatial96_inferred_v2/paired_spatial_metrics.csv",
        "本地：96 车道事件": ROOT / "data/local/expanded96-release/prepared-v1/processed/events.parquet",
        "本地：五分钟交通": ROOT / "data/local/expanded96-release/prepared-v1/processed/cohort_bins.parquet",
        "本地：官方道路索引": NETWORK / "topology_index.sqlite",
        "本地：推断邻路与特征": ROOT / "data/local/spatial96/inferred-v2/event_spatial_features.parquet",
        "本地：空间逐事件预测": ROOT / "data/local/spatial96/inferred-v2/predictions.parquet",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        st.warning(f"{len(missing)} 项研究产物不可用：{'、'.join(missing)}。缺失保持缺失；不使用演示数据替代。")
    st.dataframe(pd.DataFrame([{"证据": k, "状态": "已发现" if p.is_file() else "不可用", "相对路径": str(p.relative_to(ROOT))}
                               for k, p in paths.items()]), hide_index=True, width="stretch")
    _note("空间逐事件概率未随 PR #21 发布：仅显示真实汇总指标，不从 AUC 反推 ROC/PR 曲线，也不借用其他模型概率。历史 24 车道研究与本页隔离。")


def _unit_label(row: pd.Series) -> str:
    return f"{row.detector_id} · {row.direction} · {row.lane_id}"


def road_network() -> None:
    st.subheader("香港官方路网 / 推断有向关系")
    _note("灰线：官方道路几何；蓝线：算法推断路径；绿色/琥珀色点：高置信/歧义候选；红色：选定车道单位。路径按真实路线几何绘制，长度取保存的网络路径结果。")
    try:
        mapping = get_mappings()
        paths = get_neighbors("INFERRED_EXPLORATORY")
    except (FileNotFoundError, ValueError) as exc:
        st.error(f"本地空间证据不可用：{exc}")
        return
    best = mapping.loc[mapping["rank"].eq(1)].copy()
    c1, c2, c3 = st.columns([1.15, 1.1, 1])
    detector = c1.selectbox("Detector ID", ["All", *sorted(best.detector_id.unique())])
    candidates = best if detector == "All" else best.loc[best.detector_id.eq(detector)]
    road_names = sorted(best.road_name.dropna().astype(str).unique())
    road = c2.selectbox("道路 / corridor", ["All", *road_names])
    if road != "All":
        candidates = candidates.loc[candidates.road_name.eq(road)]
    direction = c3.selectbox("方向", ["All", *sorted(best.direction.dropna().unique())])
    if direction != "All":
        candidates = candidates.loc[candidates.direction.eq(direction)]
    d1, d2, d3 = st.columns(3)
    lane = d1.selectbox("车道", ["All", *sorted(best.lane_id.dropna().unique())])
    tier = d2.selectbox("映射等级", ["All", *sorted(best.quality_tier.dropna().unique())])
    eligible = d3.selectbox("邻路资格", ["All", "Has inferred neighbor", "No inferred neighbor"])
    if lane != "All": candidates = candidates.loc[candidates.lane_id.eq(lane)]
    if tier != "All": candidates = candidates.loc[candidates.quality_tier.eq(tier)]
    if eligible != "All":
        connected = set(zip(paths.upstream_detector, paths.upstream_direction, paths.upstream_lane)) | set(
            zip(paths.downstream_detector, paths.downstream_direction, paths.downstream_lane))
        flag = candidates.apply(lambda r: (r.detector_id, r.direction, r.lane_id) in connected, axis=1)
        candidates = candidates.loc[flag if eligible.startswith("Has") else ~flag]
    if candidates.empty:
        st.info("当前筛选没有车道单位。")
        return
    connected = set(zip(paths.upstream_detector, paths.upstream_direction, paths.upstream_lane)) | set(
        zip(paths.downstream_detector, paths.downstream_direction, paths.downstream_lane))
    ordered = candidates.assign(has_path=candidates.apply(
        lambda r: (r.detector_id, r.direction, r.lane_id) in connected, axis=1)).sort_values(
            ["has_path", "detector_id"], ascending=[False, True])
    labels = {_unit_label(row): idx for idx, row in ordered.iterrows()}
    st.caption(f"当前：{len(candidates)} 个车道单位，{candidates.detector_id.nunique()} 个物理探测器位置；全体冻结队列为 96 个车道单位。")
    selected_label = st.selectbox("车道单位（同一物理探测器可有多个方向/车道）", list(labels))
    selected = candidates.loc[labels[selected_label]]
    unit = (selected.detector_id, selected.direction, selected.lane_id)
    st.session_state["selected_detector96"] = unit[0]
    relevant = paths.loc[((paths.upstream_detector == unit[0]) & (paths.upstream_direction == unit[1]) & (paths.upstream_lane == unit[2]))
                         | ((paths.downstream_detector == unit[0]) & (paths.downstream_direction == unit[1]) & (paths.downstream_lane == unit[2]))].copy()
    toggles = st.columns(7)
    show_roads = toggles[0].toggle("官方道路", value=True)
    show_paths = toggles[1].toggle("推断路径", value=True)
    show_up = toggles[2].toggle("上游", value=True)
    show_down = toggles[3].toggle("下游", value=True)
    high_only = toggles[4].toggle("仅高置信")
    show_candidates = toggles[5].toggle("匹配候选", value=True)
    toggles[6].toggle("独立核验 (0)", disabled=True)
    tile_names = available_tiles(NETWORK)
    center_tile = f"{int(selected.easting // 4000)}_{int(selected.northing // 4000)}"
    tile = st.selectbox("官方道路几何分块 · 每次只加载一个 4 km 源分块", tile_names,
                        index=tile_names.index(center_tile) if center_tile in tile_names else 0)
    st.caption("平移地图后可在此切换相邻分块；96 个车道标记同时可见，官方道路几何按所选分块限量读取并简化显示。")
    layers = []
    if show_roads:
        try:
            roads = get_tile(tile)
            layers.append(pdk.Layer("PathLayer", roads[["route_id", "path"]], get_path="path",
                                    get_color=[130, 142, 148, 125], get_width=2, width_min_pixels=1,
                                    pickable=True))
            st.caption(f"本视图道路分块：{tile} · {len(roads):,} 条真实官方路线；全网 36,525 条路段 / 48,080 候选有向弧。")
        except (FileNotFoundError, ValueError) as exc:
            st.warning(f"道路几何不可用：{exc}")
    if high_only:
        high_paths = get_neighbors("HIGH_CONFIDENCE_INFERRED")
        relevant = high_paths.loc[((high_paths.upstream_detector == unit[0]) & (high_paths.upstream_direction == unit[1]) & (high_paths.upstream_lane == unit[2]))
                                  | ((high_paths.downstream_detector == unit[0]) & (high_paths.downstream_direction == unit[1]) & (high_paths.downstream_lane == unit[2]))]
    filtered = relevant.copy()
    if not show_up:
        filtered = filtered.loc[~filtered.downstream_detector.eq(unit[0])]
    if not show_down:
        filtered = filtered.loc[~filtered.upstream_detector.eq(unit[0])]
    route_ids = {str(route) for seq in filtered.route_sequence.dropna() for route in str(seq).split("|")}
    route_ids.add(str(selected.route_id))
    all_candidates = mapping.loc[(mapping.detector_id == unit[0]) & (mapping.direction == unit[1])
                                 & (mapping.lane_id == unit[2])]
    if show_candidates:
        route_ids.update(all_candidates.route_id.dropna().astype(str))
    try:
        routes = get_routes(tuple(sorted(route_ids)))
    except (FileNotFoundError, ValueError) as exc:
        st.warning(f"选中路径的官方几何不可用：{exc}")
        routes = {}
    if show_paths and not filtered.empty:
        draw = []
        arrows = []
        for row in filtered.itertuples():
            side = "upstream" if row.downstream_detector == unit[0] else "downstream"
            for arc in str(row.arc_sequence).split("|"):
                route, orientation = arc.rsplit(":", 1)
                if route in routes:
                    path = routes[route][::(-1 if orientation == "R" else 1)]
                    draw.append({"path": path,
                                 "color": [33, 134, 122, 220] if side == "upstream" else [52, 74, 94, 225],
                                 "pair": f"{row.upstream_detector} → {row.downstream_detector}"})
                    if len(path) >= 2:
                        mid = max(0, (len(path)-2)//2)
                        a, b = path[mid:mid+2]
                        arrows.append({"position": [(a[0]+b[0])/2, (a[1]+b[1])/2],
                                       "text": "➤", "angle": -degrees(atan2(b[1]-a[1], b[0]-a[0])),
                                       "color": [33, 134, 122, 250] if side == "upstream" else [52, 74, 94, 250]})
        if draw:
            layers.append(pdk.Layer("PathLayer", draw, get_path="path", get_color="color", get_width=6,
                                    width_min_pixels=3, pickable=True))
            layers.append(pdk.Layer("TextLayer", arrows, get_position="position", get_text="text",
                                    get_angle="angle", get_color="color", get_size=18,
                                    size_min_pixels=12, size_max_pixels=22))
    if show_candidates:
        candidate_draw = [{"path": routes[str(row.route_id)], "arc_id": row.arc_id,
                           "color": [166, 90, 80, 225] if row["rank"] == 1 else [198, 139, 68, 110]}
                          for _, row in all_candidates.iterrows() if str(row.route_id) in routes]
        if candidate_draw:
            layers.append(pdk.Layer("PathLayer", candidate_draw, get_path="path", get_color="color",
                                    get_width=4, width_min_pixels=2, pickable=True))
    points = best.drop_duplicates(list(data.UNIT)).copy()
    points["color"] = points.quality_tier.map({"HIGH_CONFIDENCE_INFERRED": [33, 134, 122, 205],
                                                "AMBIGUOUS_INFERRED": [198, 139, 68, 200]}).apply(
                                                    lambda x: x if isinstance(x, list) else [130, 130, 130, 200])
    point_records = points[["detector_id", "direction", "lane_id", "longitude", "latitude", "color"]].to_dict("records")
    for point in point_records:
        if point["detector_id"] == unit[0] and point["direction"] == unit[1] and point["lane_id"] == unit[2]:
            point["color"] = [166, 90, 80, 245]
    layers.append(pdk.Layer("ScatterplotLayer", point_records, get_position="[longitude, latitude]",
                            get_fill_color="color", get_radius=55, radius_min_pixels=5, radius_max_pixels=13,
                            pickable=True))
    deck = pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(latitude=float(selected.latitude),
                     longitude=float(selected.longitude), zoom=12, pitch=0), map_style="light",
                    tooltip={"text": "{detector_id} {direction} {lane_id} {pair} {route_id} {arc_id}"})
    st.pydeck_chart(deck, width="stretch", height=540)
    st.markdown("#### 匹配质量与不确定性")
    st.dataframe(pd.DataFrame([{"探测器": selected.detector_id, "描述": selected.detector_description,
        "源东坐标 m": selected.easting, "源北坐标 m": selected.northing,
        "选中道路弧": selected.arc_id, "偏移 m": selected.distance_m,
        "方位差 °": selected.directional_error_deg, "路名证据": selected.name_evidence,
        "无量纲评分": selected.score, "评分差": selected.score_margin, "等级": selected.quality_tier,
        "核验状态": selected.review_status}]), hide_index=True, width="stretch")
    alternatives = mapping.loc[(mapping.detector_id == unit[0]) & (mapping.direction == unit[1]) &
                               (mapping.lane_id == unit[2])].sort_values("rank")
    with st.expander(f"全部候选道路弧 · {len(alternatives)} 条"):
        st.dataframe(alternatives[["rank", "arc_id", "road_name", "distance_m", "directional_error_deg",
                                   "name_evidence", "score", "score_margin", "quality_tier"]],
                     hide_index=True, width="stretch")
    if relevant.empty:
        st.info("这个车道单位没有已保存的推断邻路路径。")
    else:
        pair = relevant.iloc[0]
        st.caption(f"推断邻路 {len(relevant)} 条 · 例：{pair.upstream_detector} → {pair.downstream_detector} · "
                   f"保存的沿路长度 {pair.path_distance_m:.1f} m · {pair.population} · 尚未独立核验")
        st.dataframe(relevant[["upstream_detector", "downstream_detector", "arc_sequence", "route_sequence",
                               "path_distance_m", "alternative_paths", "upstream_tier", "downstream_tier",
                               "upstream_offset_m", "downstream_offset_m", "connection_status", "historical_status"]],
                     hide_index=True, width="stretch")
    st.warning("独立核验关系为 0。AID02205→AID02114 曾出现约 43 m 短路径、两端约 45 m 偏移的疑点；道路交点及近邻不等于合法或历史连接。")
    with st.expander("典型歧义与可疑短路径 · 原始官方几何审查图"):
        st.image(str(data.verified_file(ROOT, "reports/spatial96_inferred_v2/review-short-path-large-offset.png")),
                 caption="AID02205→AID02114：短网络路径与大探测器偏移并存，尚未获批。")
        st.image(str(data.verified_file(ROOT, "reports/spatial96_inferred_v2/review-official-intersection.png")),
                 caption="源交点几何与真实探测器位置；只代表审查线索。")


def _event_figure(event: pd.Series, paths: pd.DataFrame, horizon: int) -> tuple[go.Figure, pd.DataFrame]:
    prediction = pd.Timestamp(event.prediction_time)
    start, end = prediction - pd.Timedelta(minutes=75), prediction + pd.Timedelta(minutes=max(80, horizon + 20))
    fig = go.Figure()
    observations = []
    units = [(event.detector_id, event.direction, event.lane_id, "Local", BLUE)]
    for row in paths.itertuples():
        if row.downstream_detector == event.detector_id and row.downstream_direction == event.direction and row.downstream_lane == event.lane_id:
            units.append((row.upstream_detector, row.upstream_direction, row.upstream_lane, "Upstream", TEAL))
        elif row.upstream_detector == event.detector_id and row.upstream_direction == event.direction and row.upstream_lane == event.lane_id:
            units.append((row.downstream_detector, row.downstream_direction, row.downstream_lane, "Downstream", AMBER))
    for det, direction, lane, side, color in units:
        frame = get_bins(det, direction, lane, start, end)
        frame = frame.loc[frame.usable & frame.speed_kmh.notna()].copy()
        frame["as_of"] = (frame.timestamp.le(prediction) & pd.to_datetime(frame.available_at, utc=True).le(prediction)
                          & pd.to_datetime(frame.last_source_available_at, utc=True).le(prediction))
        asof = frame.loc[frame.as_of]
        observations.append({"detector": det, "direction": direction, "lane": lane, "side": side,
                             "usable_5m_bins_asof": len(asof), "valid_source_slots_asof": int(asof.valid_slots.sum()),
                             "latest_asof": asof.timestamp.max() if not asof.empty else pd.NaT,
                             "latest_speed_kmh": asof.speed_kmh.iloc[-1] if not asof.empty else None})
        # Reindex to the actual 5-minute grid, leaving unobserved points as NaN gaps.
        for retrospective, segment in ((False, frame.loc[frame.as_of]), (True, frame.loc[~frame.as_of])):
            if segment.empty:
                continue
            grid = pd.date_range(segment.timestamp.min(), segment.timestamp.max(), freq="5min", tz=data.HKT)
            series = segment.set_index("timestamp").speed_kmh.reindex(grid)
            fig.add_scatter(x=series.index, y=series.values, mode="lines+markers", connectgaps=False,
                            name=f"{side} · {det}{' · retrospective' if retrospective else ' · as-of'}",
                            line=dict(color=color, dash="dot" if retrospective else "solid", width=2))
    for ratio, name, color in ((1, "历史正常速度", BLUE), (.5, "拥堵阈值", RED), (.8, "恢复阈值", TEAL)):
        if pd.notna(event.baseline_kmh):
            fig.add_hline(y=float(event.baseline_kmh)*ratio, line_dash="dash", line_color=color,
                          annotation_text=name)
    fig.add_vline(x=prediction.to_pydatetime(), line_color=RED)
    fig.add_annotation(x=prediction.to_pydatetime(), y=1, yref="paper", text="预测时点",
                       showarrow=False, xanchor="left", font=dict(color=RED))
    fig.add_vrect(x0=prediction.to_pydatetime(), x1=(prediction+pd.Timedelta(minutes=horizon)).to_pydatetime(),
                  fillcolor="rgba(166,90,80,.09)", line_width=0)
    fig.update_layout(template="simple_white", height=440, xaxis_title="观测结束时间 · Asia/Hong_Kong",
                      yaxis_title="速度 km/h", legend=dict(orientation="h", y=-.3), margin=dict(l=20, r=10, t=20, b=40))
    return fig, pd.DataFrame(observations)


def event_explorer() -> None:
    st.subheader("真实拥堵事件 / 五分钟观测")
    try:
        events = get_events()
        mapping = get_mappings()
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"事件浏览需要已认证的本地 96 车道数据：{exc}")
        return
    dets = sorted(events.detector_id.astype(str).unique())
    observed = observed_event_ids("INFERRED_EXPLORATORY")
    observed_dets = events.loc[events.event_id.isin(observed), "detector_id"].astype(str)
    default_det = sorted(observed_dets.unique())[0] if not observed_dets.empty else dets[0]
    default_det = st.session_state.get("selected_detector96", default_det)
    if default_det not in dets:
        default_det = dets[0]
    detector = st.selectbox("Detector ID", dets, index=dets.index(default_det), key="event_detector")
    st.session_state["selected_detector96"] = detector
    event = _event_choice(detector, key="event_choice96")
    if event is None:
        return
    population = st.selectbox("推断邻路群体", list(data.POPULATIONS), format_func=lambda x: POP_NAMES[x])
    horizon = st.selectbox("恢复时窗 / 分钟", [15, 30, 60], index=1)
    st.session_state["feature_event_id"] = str(event.event_id)
    paths = get_neighbors(population)
    paths = paths.loc[((paths.upstream_detector == event.detector_id) & (paths.upstream_direction == event.direction)
                       & (paths.upstream_lane == event.lane_id)) | ((paths.downstream_detector == event.detector_id)
                       & (paths.downstream_direction == event.direction) & (paths.downstream_lane == event.lane_id))]
    st.markdown(f"**{event.detector_id} · {event.direction} · {event.lane_id}**　预测：`{event.prediction_time}`　目标：`{event.definition_version}`")
    label = event[f"label_{horizon}m"]
    st.write(f"真实结果：**{'未知/删失' if pd.isna(label) else ('时窗内确认恢复' if int(label) else '时窗内未确认恢复')}**；恢复确认：**{event.recovery_time if pd.notna(event.recovery_time) else '未观测到'}**。")
    if pd.notna(label):
        try:
            local_scores = data.published_local_scores(ROOT, event, horizon)
            if not local_scores.empty:
                st.markdown("**已保存的全队列 Local + History 逐事件概率**")
                st.dataframe(local_scores[["model", "split", "horizon_min", "label", "probability",
                                            "prediction", "target_version", "source_provenance"]],
                             hide_index=True, width="stretch")
                st.caption("来自独立 A0–A2 v2 全队列实验；PR #21 的 P1/P2 M0 在各自资格群体重新拟合，不能把此分数当作配对空间模型预测。")
        except (FileNotFoundError, ValueError) as exc:
            st.info(f"全队列本地模型逐事件概率不可用：{exc}")
    st.caption("实线表示预测时可用的观测，虚线和阴影表示事后解释窗口。未来观测从未进入已保存模型的预测特征矩阵。")
    try:
        fig, quality = _event_figure(event, paths, horizon)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(quality, hide_index=True, width="stretch")
    except (FileNotFoundError, ValueError, KeyError) as exc:
        st.info(f"真实五分钟速度曲线不可用：{exc}")
    try:
        lineage = get_lineage(str(event.event_id), population)
        if lineage.empty:
            st.info("此事件没有符合预测时可用性门槛的真实邻路速度；缺失保持缺失。")
        else:
            st.markdown("#### 预测时的真实邻路观测")
            st.dataframe(lineage[["neighbor_detector", "neighbor_direction", "neighbor_lane", "side",
                                  "network_distance_m", "mapping_tier", "observed_at", "available_at",
                                  "speed_kmh", "age_minutes", "valid_slot_fraction", "source_sha256"]],
                         hide_index=True, width="stretch")
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"邻路来源明细不可用：{exc}")
    matched = mapping.loc[(mapping.detector_id == event.detector_id) & (mapping.direction == event.direction)
                          & (mapping.lane_id == event.lane_id) & mapping["rank"].eq(1)]
    if not matched.empty:
        st.caption(f"道路映射：{matched.iloc[0].arc_id} · {matched.iloc[0].quality_tier}；属于算法推断，不是独立核准。")


def spatial_features() -> None:
    st.subheader("空间特征工程 / 真实事件示例")
    try:
        detector_ids = sorted(get_events().detector_id.unique())
        preferred = st.session_state.get("selected_detector96", detector_ids[0])
        detector = st.selectbox("Detector ID", detector_ids,
                                index=detector_ids.index(preferred) if preferred in detector_ids else 0,
                                key="feature_detector")
        st.session_state["selected_detector96"] = detector
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"真实事件表不可用：{exc}")
        return
    event = _event_choice(detector, key="feature_choice96")
    if event is None:
        return
    population = st.selectbox("群体", list(data.POPULATIONS), format_func=lambda x: POP_NAMES[x], key="feature_pop")
    try:
        values = get_features(str(event.event_id), population)
        lineage = get_lineage(str(event.event_id), population)
    except (FileNotFoundError, ValueError) as exc:
        st.info(f"本地空间特征不可用：{exc}")
        return
    st.write("道路端点与路口形成节点；源有向道路段形成弧；只保留有源路口支持的弧间转接；探测器匹配至候选道路弧；在有向路径上检索上/下游，再按预测时可得观测聚合为 ML 特征。")
    st.caption(f"事件 {event.event_id} · {event.prediction_time} · 邻路真实观测 {int(values.observed_neighbor_count)} 条；空值显示为空，不当作 0 km/h。")
    groups = {
        "S1 · 基本邻域": ["mean_speed_kmh", "mean_ratio", "observed_count", "mean_age_minutes", "coverage", "missing"],
        "S2 · 空间拥堵": ["congestion_fraction", "upstream_downstream_congestion_difference", "local_minus_neighbor_ratio", "neighbor_to_local_speed_gradient"],
        "S3 · 路网权重": ["mean_network_distance_m", "distance_weighted_speed", "confidence_weighted_speed", "multihop_congestion_fraction"],
        "S4 · 邻路时间变化": ["change_5m_kmh", "change_10m_kmh", "change_15m_kmh", "local_neighbor_trend_difference"],
    }
    for title, fields in groups.items():
        with st.expander(title, expanded=title.startswith("S1")):
            rows = []
            for field in fields:
                names = [field] if field in values.index else [f"{side}_{field}" for side in ("upstream", "downstream")]
                for name in names:
                    if name in values.index:
                        v = values[name]
                        rows.append({"特征": name, "真实保存值": None if pd.isna(v) else v})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if lineage.empty:
        st.info("该事件没有可用邻路观测；S1–S4 测量值按原产物保留缺失。")
    else:
        st.dataframe(lineage[["side", "neighbor_detector", "network_distance_m", "mapping_tier",
                              "observed_at", "available_at", "speed_kmh", "change_5m_kmh",
                              "change_10m_kmh", "change_15m_kmh"]], hide_index=True, width="stretch")
    st.caption("S3 使用保存的网络距离、距离衰减和路径置信权重；S4 各滞后观测同样受 as-of 可用时间限制。无插值、无虚构路段速度。")


def model_comparison() -> None:
    st.subheader("本地历史与推断空间模型 / 同事件比较")
    table = get_metrics()
    c1, c2, c3 = st.columns(3)
    population = c1.selectbox("群体", [*data.POPULATIONS, "INDEPENDENTLY_VERIFIED"], format_func=lambda x: POP_NAMES[x])
    model = c2.selectbox("模型", list(MODEL_NAMES), format_func=lambda x: MODEL_NAMES[x])
    split = c3.selectbox("评估集", ["test", "validation"])
    if population == "INDEPENDENTLY_VERIFIED":
        st.warning("P3：独立获批的历史路网关系为 0；没有可用实验或性能指标。")
        return
    a, b, c = st.columns(3)
    arm = a.selectbox("特征臂", [f"M{i}" for i in range(6)], index=1)
    metric = b.selectbox("指标", list(METRIC_NAMES), format_func=lambda x: METRIC_NAMES[x])
    c.selectbox("预测时窗", [30], help="已发布推断空间实验只有 30 分钟；其他时窗不显示虚构结果。")
    base, selected = data.paired_rows(table, population, model, split, "M0", arm)
    st.caption(f"{POP_NAMES[population]} · {split} · 30 min · {selected.n_events:,} 相同事件 · 目标 recovery_confirmation_v1 · event IDs SHA-256: {selected.event_ids_sha256}")
    line = table.loc[table.population.eq(population) & table.model.eq(model) & table.split.eq(split)].sort_values("arm")
    for item in line.itertuples():
        data.paired_rows(table, population, model, split, "M0", item.arm)
    fig = go.Figure()
    fig.add_scatter(x=line.arm, y=line[metric], mode="lines+markers", line=dict(color=BLUE, width=3),
                    text=[f"n={n}" for n in line.n_events], name=METRIC_NAMES[metric])
    fig.update_layout(template="simple_white", height=330, xaxis_title="M0 Local + History → M1–M4 spatial → M5 network structure",
                      yaxis_title=METRIC_NAMES[metric], margin=dict(l=20, r=20, t=20, b=45))
    st.plotly_chart(fig, width="stretch")
    st.write(f"M0 **{base[metric]:.4f}** → {arm} **{selected[metric]:.4f}**；同一事件集点估计差 **{selected[metric]-base[metric]:+.4f}**。")
    st.dataframe(line[["arm", "n_events", "n_positive", "n_negative", "roc_auc", "average_precision",
                       "macro_f1", "balanced_accuracy", "precision", "recall", "brier", "log_loss"]],
                 hide_index=True, width="stretch")
    matrix = pd.DataFrame([[selected.tn, selected.fp], [selected.fn, selected.tp]],
                          index=["Actual 0", "Actual 1"], columns=["Pred 0", "Pred 1"])
    st.markdown("**保存的混淆矩阵计数 · 阈值 0.5**")
    st.dataframe(matrix, width="content")
    st.info("PR #21 只发布空间模型汇总指标，没有逐事件概率产物；空间 ROC/PR 曲线与逐事件空间分数不可用。不能从 AUC 重建曲线。")
    st.caption("P1 与 P2 的测试事件群不同，不能把两组指标当作配对差异。M0 在各自资格群体重新拟合。")
    with st.expander("已发布 Tianhao 96 车道逐事件预测 · 独立实验"):
        _published_predictions()
    st.markdown("#### 负对照 · C1–C5")
    controls = get_metrics(True)
    control = controls.loc[controls.model.eq(model) & controls.split.eq(split) & controls.arm.eq("M1")].copy()
    directed = selected if arm == "M1" else data.paired_rows(table, population, model, split, "M0", "M1")[1]
    control["same_events_as_selected"] = control.event_ids_sha256.eq(directed.event_ids_sha256)
    st.dataframe(control[["population", "n_events", "event_ids_sha256", "same_events_as_selected",
                          "roc_auc", "average_precision", "macro_f1", "brier", "shuffle_swapped_events"]],
                 hide_index=True, width="stretch")
    st.caption("C1 地理邻近；C2 无方向网络；C3 推断有向；C4 同时刻/同区置换；C5 P2 高置信网络。P1 内 C3 的回溯点估计高于 C1/C2；C4 仍保留较强预测信号，置换只部分有效。不能由此推断因果或显著性。")


def _published_predictions() -> None:
    folder = ROOT / "experiments/tianhao/expanded96_20261104"
    summary = pd.read_csv(folder / "metrics_summary.csv")
    model = st.selectbox("已发布模型", ["logistic_regression", "logistic_l1", "svm_rbf", "decision_tree"], key="published_model")
    sets = sorted(summary.loc[summary.model.eq(model), "feature_set"].unique())
    feature_set = st.selectbox("已发布特征", sets, key="published_arm")
    p = ds.dataset(folder / "predictions.parquet").to_table(
        columns=["event_id", "prediction_time", "y_true", "y_score", "y_pred"],
        filter=(ds.field("split") == "test") & (ds.field("model") == model)
               & (ds.field("feature_set") == feature_set) & (ds.field("horizon_min") == 30)).to_pandas()
    if p.empty or p.event_id.duplicated().any():
        st.info("此已发布模型没有可用且唯一的逐事件预测。")
        return
    saved = summary.loc[summary.model.eq(model) & summary.feature_set.eq(feature_set) & summary.split.eq("test")].iloc[0]
    if len(p) != saved.n:
        raise ValueError("Published prediction count differs from frozen metrics")
    from sklearn.metrics import precision_recall_curve, roc_curve
    fpr, tpr, _ = roc_curve(p.y_true, p.y_score)
    precision, recall, _ = precision_recall_curve(p.y_true, p.y_score)
    fig = go.Figure()
    fig.add_scatter(x=fpr, y=tpr, name="ROC · saved scores", line=dict(color=BLUE))
    fig.add_scatter(x=recall, y=precision, name="PR · saved scores", line=dict(color=TEAL))
    fig.update_layout(template="simple_white", height=330, xaxis_title="FPR / Recall", yaxis_title="TPR / Precision")
    st.plotly_chart(fig, width="stretch")
    st.caption(f"此图仅属于 Tianhao 已发布 96 车道独立实验：n={len(p):,}, ROC-AUC={saved.roc_auc:.4f}, PR-AUC={saved.pr_auc:.4f}。未与 P1/P2 空间模型配对。")


def methodology() -> None:
    st.subheader("方法、来源与科学边界")
    st.write("**目标：** 当前暂定 `recovery_confirmation_v1` 是采样后持续恢复的确认时点。Proposal 的 `recovery_start_sustained_v1` 是恢复开始，两者并不等价。15/30/60 分钟内恢复不等于时窗终点恰好恢复。")
    st.write("**路网：** 2026 官方 CENTERLINE、INTERSECTION、TURN 生成 36,525 路段、48,080 候选有向弧；探测器源 HK1980 坐标投影至路线；路径要求端点、路口、高程和记录的转向限制。缺少禁止转向记录不代表合法通行。")
    st.write("**特征：** 仅五分钟可用、有效且观测/可用时间不晚于预测时点的邻路速度用于 S1–S4；最大观测年龄 10 分钟。没有插值或未观测路段速度。")
    st.write("**评估：** P1/P2 分别在同事件群训练 M0–M5，验证集选择候选，测试集报告已保存的指标。P3 0 获批连接，保持 NO-GO。")
    st.warning("2026 路网快照回溯用于 2023–2026 事件；物理连接、历史映射、平行主辅路、立交和附条件转向均未独立核准。回溯性能增益不等于因果效应、显著性或可部署性。")
    st.info("Inferred-network exploratory spatial models have been trained and evaluated. Independently verified historical-network experiments remain unavailable.")
    st.caption("来源：reports/spatial96_inferred_v2/network_methodology.md、research_summary_zh.md、source_sha256.json；data/local 的冻结 Release 和路网索引只读。")


def render() -> None:
    st.markdown('<div class="kicker">SDSC6004 / 96-lane research evidence / 2026</div>', unsafe_allow_html=True)
    st.title("香港交通拥堵恢复 · 研究浏览器")
    st.caption("官方道路几何 · 实测五分钟车道速度 · 推断有向邻路 · 冻结模型证据")
    pages = ["概览", "道路网络", "事件浏览", "空间特征", "模型比较", "研究方法"]
    page = st.radio("研究视图", pages, horizontal=True, label_visibility="collapsed")
    try:
        {"概览": overview, "道路网络": road_network, "事件浏览": event_explorer,
         "空间特征": spatial_features, "模型比较": model_comparison, "研究方法": methodology}[page]()
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        st.error(f"研究产物不可用或验证失败：{exc}")
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.caption("96-LANE EXPANDED RELEASE · READ-ONLY · INFERRED NETWORK IS NOT INDEPENDENTLY APPROVED · HKT (UTC+08:00)")
