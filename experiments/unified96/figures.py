"""Build real-evidence poster figures; refuses to replace existing figure directory.

uv run --locked python -m experiments.unified96.figures --out reports/final_research/figures
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from traffic_recovery import research96
from traffic_recovery.data.http import sha256_file
from experiments.unified96.run import ROOT, load

RUN = ROOT / "experiments/unified96/runs/p1-f0-f4-v1"


def save(fig: plt.Figure, folder: Path, name: str) -> None:
    for suffix in ("svg", "png"):
        path = folder / f"{name}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        if suffix == "svg":
            # Matplotlib emits trailing spaces in path data; normalize for git diff --check.
            path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
    plt.close(fig)


def build(out: Path) -> None:
    if out.exists():
        raise FileExistsError(f"Refusing overwrite: {out}")
    frame, _ = load()
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["outputs_sha256"].items():
        if sha256_file(RUN / name) != digest:
            raise ValueError(f"New run artifact changed: {name}")
    metrics = pd.read_csv(RUN / "metrics.csv")
    bootstrap = json.loads((RUN / "paired_bootstrap.json").read_text(encoding="utf-8"))
    control = research96.metrics(ROOT, controls=True)
    # Out directory created only after verifying inputs; never replace published reports.
    out.mkdir(parents=True)
    fig, ax = plt.subplots(figsize=(11, 2.9))
    stages = ["Official source\n& hashes", "5-min lane bins\n& censored events", "Inferred directed\nroad candidates", "As-of local, history\n& neighbour features", "Train / validation\nmodel selection", "Paired test &\ncluster bootstrap"]
    for i, name in enumerate(stages):
        ax.text(i, .5, name, ha="center", va="center", fontsize=9,
                bbox={"boxstyle": "round", "facecolor": "#eaf2f3", "edgecolor": "#4f7e83"})
        if i:
            ax.annotate("", xy=(i-.37,.5), xytext=(i-.62,.5), arrowprops={"arrowstyle": "->"})
    ax.set(xlim=(-.45,5.45), ylim=(0,1), title="Figure 1. Authenticated retrospective research workflow")
    ax.axis("off")
    save(fig,out,"01_workflow")
    original = ROOT / "reports/spatial96_inferred_v2/review-official-intersection.png"
    expected = json.loads((ROOT / "reports/spatial96_inferred_v2/output_sha256.json").read_text(encoding="utf-8"))[str(original.relative_to(ROOT))]
    if sha256_file(original) != expected:
        raise ValueError("Official-geometry review image changed")
    shutil.copyfile(original, out / "02_official_geometry_review.png")
    # Deterministic real event: lexicographically first eligible P1 test event.
    event = frame.loc[frame.split.eq("test")].sort_values("event_id").iloc[0]
    start = event.prediction_time - pd.Timedelta(minutes=65)
    end = event.prediction_time + pd.Timedelta(minutes=65)
    local = research96.observed_bins(ROOT, event.detector_id, event.direction, event.lane_id, start, end)
    lineage = research96.event_lineage(ROOT, event, "INFERRED_EXPLORATORY")
    fig, ax = plt.subplots(figsize=(10,4.1))
    valid = local.loc[local.usable & local.speed_kmh.notna()].copy()
    before = (valid.timestamp.le(event.prediction_time) & valid.available_at.le(event.prediction_time)
              & valid.last_source_available_at.le(event.prediction_time))
    for mask, label, color, style in ((before, "Local (as-of)", "#276782", "o-"),
                                      (~before, "Local (retrospective only)", "#a77948", "o--")):
        segment = valid.loc[mask]
        if segment.empty:
            continue
        grid = pd.date_range(segment.timestamp.min(), segment.timestamp.max(), freq="5min", tz="Asia/Hong_Kong")
        speeds = segment.set_index("timestamp").speed_kmh.reindex(grid)  # absent bins stay gaps
        ax.plot(grid, speeds, style, label=label, color=color)
    for side,color in (("upstream","#228a79"),("downstream","#8b5684")):
        rows=lineage.loc[lineage.side.eq(side)]
        ax.scatter(rows.observed_at,rows.speed_kmh,label=f"{side.title()} true neighbour (as-of)",marker="x",s=60,color=color)
    ax.axvline(event.prediction_time,color="#a14444",label="Prediction time")
    ax.axvspan(event.prediction_time,event.prediction_time+pd.Timedelta(minutes=30),alpha=.1,color="#a14444",label="30-min outcome window")
    ax.set(title=f"Figure 3. Actual P1 test event {event.event_id[:12]}… · confirmation target · label={int(event.label)}",
           ylabel="Observed speed (km/h)",xlabel="Observation end (Asia/Hong_Kong)")
    ax.tick_params(axis="x",rotation=20);ax.legend(fontsize=7,ncol=2);save(fig,out,"03_real_event")
    selected = metrics.loc[metrics.split.eq("test")].pivot(index="model",columns="arm",values="roc_auc")
    fig,ax=plt.subplots(figsize=(8,4.2)); selected[["F0","F4"]].plot.bar(ax=ax,color=["#426b85","#238775"])
    ax.set(title="Figure 4. P1 test · recovery confirmation within 30 min · n=3,933",
           xlabel="Model",ylabel="ROC-AUC",ylim=(0,1))
    ax.legend(title="F0=L+H+Q; F4=F0+S");ax.tick_params(axis="x",rotation=16);save(fig,out,"04_ablation")
    fig,ax=plt.subplots(figsize=(8,4.2))
    names=[x["model"] for x in bootstrap]
    gains=[x["roc_auc"]["observed_delta"] for x in bootstrap]
    lows=[x["roc_auc"]["ci_95_percentile"][0] for x in bootstrap]
    highs=[x["roc_auc"]["ci_95_percentile"][1] for x in bootstrap]
    ax.errorbar(gains,range(len(names)),xerr=[np.subtract(gains,lows),np.subtract(highs,gains)],fmt="o",capsize=4)
    ax.axvline(0,color="gray",ls="--");ax.set_yticks(range(len(names)),names)
    ax.set(title="Figure 5. P1 test F4 − F0 · n=3,933; 44 detector clusters",
           xlabel="Paired ROC-AUC difference (95% detector-bootstrap percentile CI)")
    save(fig,out,"05_spatial_gain")
    controls = control.loc[control.split.eq("test") & control.arm.eq("M1") & control.population.isin(
        ["C1_geographic","C2_undirected","C3_directed","C4_time_region_shuffle"])]
    if controls.empty:
        raise ValueError("Frozen negative controls missing")
    table=controls.pivot(index="population",columns="model",values="roc_auc")
    fig,ax=plt.subplots(figsize=(8,4.2));table.plot.bar(ax=ax,color=["#426b85","#238775"])
    ax.set(title="Figure 6. Frozen PR #21 controls · P1 test · n=3,933; partial shuffle",
        xlabel="Neighbour representation (not a causal test)",ylabel="ROC-AUC",ylim=(0,1))
    ax.tick_params(axis="x",rotation=13);save(fig,out,"06_network_controls")
    provenance = {str(p.name):sha256_file(p) for p in sorted(out.iterdir()) if p.is_file()}
    (out / "figure_manifest.json").write_text(json.dumps({"sources": {"run_manifest":sha256_file(RUN/"manifest.json"),
       "spatial_controls":sha256_file(ROOT/"reports/spatial96_inferred_v2/spatial_negative_controls.csv"),
       "source_geometry_figure":expected},"event_id":event.event_id,
       "caveats": "Figure 2 is source review geometry, not legal/historical verified routing. Figure 3 neighbour points are as-of; later local speed is retrospective outcome context. Figure 6 partial shuffle is weak.",
       "figures_sha256":provenance},indent=2)+"\n",encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    build(parser.parse_args().out)


if __name__=="__main__":
    main()
