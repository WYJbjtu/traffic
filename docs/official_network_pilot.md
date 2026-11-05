# Official full-network and historical processed-speed pilot (2026-11-02)

**Exploratory engineering evidence, NOT spatial-ML approval.** Source geometry is
not navigable topology. An ID join is not historical network version validation.
No recovery labels were changed and no new model was trained.

## Reproduction (repository root, Python 3.12)

```text
uv sync --locked
uv run --locked python -m traffic_recovery.network.full_network --output data/local/network-full/v1
uv run --locked python -m traffic_recovery.data.processed_segments --roads data/local/network-full/v1 --output data/local/processed-pilot/v1 --dates 2023-05-15 2026-09-15
uv run --locked python -m traffic_recovery.network.coverage_report --output data/local/processed-pilot/coverage.json
uv run --locked pytest
```

The network builder refuses an existing output directory; choose a **new versioned
output** for reruns, do not delete old evidence. The processed pilot reuses only
checksum-verified exact-URL responses. No annual archive is downloaded. Override
paths in CLI for portable environments. Source inputs in this run: original
`data/local/audit-20261019-21/network_centerline.gml` (484,207,756 bytes),
`data/local/pilot/network_http/{INTERSECTION,TURN}.gml` and previously downloaded
`data/local/smoke-audit/coverage_segment.json`. All large artifacts stay ignored.

For the Streamlit Research Explorer, use the environment documented in
`docs/research_explorer.md`; its optional dependencies Streamlit, PyDeck and
Plotly are **not** in `uv.lock` and were unavailable in this execution environment.
Open the **Full road & speed pilot** tab after generating local artifacts. Its map
uploads one 4-km *centroid tile* at a time, simplified for browser display; it
must still be browser-rendered and tested in a configured environment. Tiled
source WKB in EPSG:2326 and transformed WGS84 WKB are not simplified. The
candidate arc overlay uses straight endpoint vectors (NOT true road geometry).

## Sources, checksums and dates

| Official source | Local evidence | SHA-256 |
|---|---|---|
| `https://static.data.gov.hk/td/road-network-v2/CENTERLINE.gml` (retrieved 2026-10-27 08:18 UTC, Last-Modified 2026-10-09 04:20:50 GMT) | `data/local/audit-20261019-21/network_centerline.gml` | `4fad0303e65c759ac7abe8eea3920b3ffcfcd5149c978fa9540bf032933a32c2` |
| `https://static.data.gov.hk/td/road-network-v2/INTERSECTION.gml` | `data/local/pilot/network_http/INTERSECTION.gml` | `79119240315ea989b18e715d54f7146ff8bcbc9c51aeb91ed46857c0bf72fa5f` |
| `https://static.data.gov.hk/td/road-network-v2/TURN.gml` | `data/local/pilot/network_http/TURN.gml` | `790ce25722354a796f59becc7c6adf82766ebb4289f96621ef118ed4179a38b0` |
| `https://resource.data.one.gov.hk/td/traffic-detectors/irnAvgSpeed-all.xml` via archive `get-file?url=...&time=20230515-1200` (retrieved 2026-11-02 08:15:35 UTC) | `data/local/processed-pilot/v1/http/segment_20230515-1200.xml` (358,980 bytes) | `fdeed8f75587c3c97072f55b144a027e8d1432f2f3dee3422f7c808dd34c24b5` |
| Same via archive `get-file?url=...&time=20260915-1200` (retrieved 2026-11-02 08:15:40 UTC) | `data/local/processed-pilot/v1/http/segment_20260915-1200.xml` (381,832 bytes) | `0007acb1eee0defd9eae89802c61cbeeacc3950de1c2eaf2dfd20c536c1785f0` |

The complete request URLs, response statuses, redirected URLs, response headers,
byte counts and retrieval timestamps are in each adjacent `.meta.json` and
`requests.jsonl`. Road source metadata (including revision) are also embedded
in `data/local/network-full/v1/manifest.json`. Road direction `1` yields F/R,
`3` F only; elevation codes remain exact. A crossing with no common 1-cm
endpoint does **not** generate a transition. An `INTERSECTION` membership with a
point within 1 m tags a shared endpoint pair as supported **candidate**. A
negative `NO_TURN` TURN consecutive route pair blocks all such transitions
conservatively; unknown/fractional/conditional movements are **not** certified.
No complete legal routing or geographical-area administrative coverage is proven.

## Actual network run

`data/local/network-full/v1/`: `geometry/tile=.../*.parquet` (original
attribute JSON, source and WGS84 WKB), `arcs/tile=.../*.parquet`,
`transitions/tile=.../*.parquet`, `topology_index.sqlite`,
`invalid_geometry.json`, `manifest.json`. Geometry and topology are separate.
All 36,525 source objects parsed as valid geometry; 0 invalid; 48,080 directed
arcs; 29,705 weak endpoint nodes, 1,287 weak endpoint components (largest 11,587
nodes); 27,368 source INTERSECTION records and 11,051 TURN records; 95 populated
4-km centroid tiles. Candidate transition records: 62,625
intersection-supported (not legally verified), 16,579 unverified U-turns and
12,818 conservatively restricted. Unverified legal transitions cannot be used
for navigational degree/distance statistics. Linux peak process RSS 300,544 KiB;
wall runtime 59.28 s. Exact counts and tile counts are in the manifest. This
October 2026 road snapshot has **not** been proven valid for 2023 events.

## Historical availability and actual snapshot coverage

DATA.GOV.HK archive API: `https://data.gov.hk/en/help/api-spec` (GMT+8).
The prior archived inventory (retrieved 2026-10-27 09:20 UTC; SHA-256
`7b12c2f291520dbe7e3936b07372e50caa642427668335cf699bc6648ec97dab`)
lists 45 monthly objects for January 2023–September 2026 (12/12/12/9).
**Inventory is NOT per-segment observation or publication coverage.**
Bounded one-day `list-file-versions` requests found 720 capture versions on
2023-05-15 and 528 on 2026-09-15. Listing hashes respectively:
`bb9779a91150e51ea97f6b222649e8444e62f144abd363cde5999bbe4b367a08`
and `f2ce4029db21eb5a46d4709b7ca15e50b2a01984f302dd645a8e8d4027a0a258`.
Both selected real noon archives returned HTTP 200; source `irn_version` was
`20221210`, not a verified match to the October 2026 CENTERLINE.

| HKT snapshot | XML observation time | Rows / Y-valid numeric | Exact current-geometry ID overlap (Y-valid) | ID-overlap % of 36,525 | Approved time-valid network features |
|---|---|---:|---:|---:|---:|
| 2023-05-15 12:00 | 11:54 | 4,255 / 4,198 | 4,181 | 11.447% | 0 |
| 2026-09-15 12:00 | 11:53 | 4,524 / 4,458 | 4,437 | 12.148% | 0 |

All rows retain raw speed/valid/ID/IRN and provenance; `N` values are masked
(not speed zero). No duplicate/conflicting keys appeared in these two samples;
the parser quarantines conflicting keys if encountered. `available_at` is the
archive capture timestamp as a **candidate upper-bound proxy**, not proof of when
TD first published each XML value. `ingestion_status` and
`usable_for_historical_features` stay unapproved/false. A later verified
publication policy and historical network snapshots with compatible versions are
mandatory for as-of model features. Processed speeds may depend on target raw
detectors: neither agreement nor statistical independence has been established.

`data/local/processed-pilot/coverage.json` records exact sample hourly coverage
(only source hour 11 was sampled). No full day/year per-segment time-series
coverage is measured. The 24-detector long-window cohort and 7,597-event label
results are known from the separate long-window handoff, **but its prepared
long-window event/bins files are not present here**. Event-, upstream/downstream-,
raw-supplement-, corridor- and fold-specific coverage are therefore **unknown**,
not zero. Two snapshots cannot establish that processed speeds compensate for
sparse raw-detector coverage. A paired spatial ablation remains **NO-GO**.

## Remaining gates

1. Obtain period-appropriate network snapshot and source documentation mapping
   `irn_version` to geometry snapshot, plus independently review detector/arc
   mappings, turns, direction and effective-date intervals.
2. Establish a conservative historic publication/availability rule with sampled
   archive evidence; study whether a processed neighbor reuses target-detector
   data. `network.observations.neighbor_speeds` requires explicitly reviewed
   same-version inputs and retains both sources, missingness and dependency flag.
3. Retrieve the checksum-verified long-window prepared bundle separately; do
   not redownload 47 GB raw archives. Perform event-cohort, hour, month,
   corridor and train/validation/test coverage, then consider paired modeling.
4. Run Streamlit with optional UI dependencies and verify actual browser tiles,
   selection and responsiveness (not verified here). No new model results claimed.
