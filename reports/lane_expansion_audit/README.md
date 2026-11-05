# January 2023 full-inventory lane-expansion audit

[Chinese decision report](report_zh.md) · [machine summary](summary.json) ·
[official input hashes](source_manifest.json) · [100m proximity-only supplement](processed_proximity_summary.json).

**Measured scope:** one authentic official January 2023 raw monthly ZIP, 1,136,915,260
bytes, SHA-256 `e9dede47f76807f674d26ca78a6832361e01073f51a09ddb2e1fd489d1794dc0`,
41,330 archive members (January 1–8 used to reconstruct January 1–7 profiles).
Source URL: `https://resource.data.one.gov.hk/td/traffic-detectors/rawSpeedVol-all.xml`;
DATA.GOV.HK request URL, pinned HTTP ETag, validated 206 ranges, per-range
checksums, requested/retrieved times and original byte hash are retained under
`data/local/lane-expansion/source/raw/202301/`. The verified downloaded monthly
ZIP is **ignored**, never committed. Its 1,136,915,260-byte acquisition is
bounded to one month, not the 47-GB archive collection.

Run from the repository root with Python 3.12, **without touching the existing
24-unit study**:

```text
uv sync --locked
uv run --locked python -m scripts.prepare_january_inventory --root data/local/lane-expansion/source --inventory data/local/smoke-audit/coverage_raw.json --workers 2
uv run --locked python -m traffic_recovery.data.lane_expansion --selection-root data/local/lane-expansion/source --output reports/lane_expansion_audit_NEW_VERSION
uv run --locked pytest
```

For a teammate holding the original full `raw/202301/raw_202301.zip` and its
`.meta.json`, `archive_check.json`, reuse them under their own `--root` and supply
a checksum-verified official raw archive inventory plus `.meta.json` via
`--inventory`. The preparation CLI requires the ZIP to exist by default. To
**explicitly acquire only the missing January month** (not 45 months), append
`--acquire-one-month`. For already existing full-inventory `selection/derived/
coverage_lane_day.parquet` and per-day bins, the audit CLI can be run directly,
without rerunning preparation. If checkpoint/code identities differ, stop and
investigate; use a separate new root rather than overwriting originals. Full
2023–September 2026 expanded continuity/event counts require the team's
original 45-month ZIPs (about 47 GB) or equivalent complete all-detector
histories. The published 1.67-GB prepared Release is limited to the earlier
selected detectors; it cannot answer continuity for the 402 additional choices.

**Original selector retained:** `data.pilot.select_cohort`, historical selection
end 2023-01-08 HKT; 5m valid mean ≥0.95, 5m valid minimum daily ≥0.90, positive
flow usable 5m mean ≥0.80, no conflicts. Rank by flow, valid coverage and lane
name; one lane per detector/direction; sort by detector ID/direction; apply the
24 cap last. `selection_funnel.csv` includes all four booleans and a first-week
reference-bin diagnostic for all 1,855 observed lanes.

The published 24 exact identities and filter-comparison rows were checked before
expansion. 1,081 lanes pass all four selection predicates, but only **426**
detector/direction groups supply a chosen lane under the original policy; **402**
selected groups are omitted solely by the artificial cap. All 426 already have
≥300 qualifying January 1–7 reference bins (minimum 1,645): this proves the
January 2023 **reference count threshold**, but **does not calculate the fitted
January 1–31 85th-percentile baseline**. No new recovery-event totals or
four-year coverage are claimed. Future periods may be reviewed for censoring
but cannot be used to choose the initial historical cohort.

`monthly_coverage.csv` is *only* the published coverage of the 24 existing
selected detectors and is labelled as such, **not** new-cohort continuity.
`geographic_coverage.csv` uses **current** official detector metadata Easting/
Northing (HK1980 Grid EPSG:2326) and district, not a verified 2023 location or
directed road match. `processed_proximity_review_leads.csv` stores **review
leads**, not neighbor features: exact-ID-overlapping official processed speeds
from two dates were compared to current geometry within 100 m of selected
stations. No same-time raw/processed agreement, independence, source IRN version
compatibility, turn verification or lane-specific inference is claimed. No
interpolation, label generation, model fitting or old-artifact modification.

The `report_zh.md` proximity supplement was appended after the initial selection
audit; `summary.json` reports selection/coverage only and
`processed_proximity_summary.json` reports the separate proximity diagnostic.
In `summary.json` and `expansion_scenarios.csv`, the 7,597 events for
`Original 24` are **published existing events**, not newly computed events;
expanded scenarios have null counts. The field name is
`recovery_events_published_existing_or_measured`.
