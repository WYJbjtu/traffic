# Evidence-ranked official road candidate — independent review needed

Source direction map: [ranked-directed-pair-3.png](ranked-directed-pair-3.png). Original official LineStrings in EPSG:2326; no straight-line road inference.
Detectors: `AID01222` (South West/Middle Lane) → `AID01223` (North West/Middle Lane).
Arcs: `2404:F|1060:F|4255:F`; source routes `2404|1060|4255`; endpoint keys `83432083:81204426:0|83405511:81204771:0`.
Source INTERSECTION IDs `18907|18530`; candidate path length `441.7578190417821` m (distance along projected source geometry, excludes point-to-road offsets).
Candidate evidence score `7.657693696637308`; ranking uses names, point distances, metadata-direction agreement and ambiguity only, **not** test model performance.

## AID01222: authentic metadata and candidate route

- Detector description: Aberdeen Praya Road near Ocean Court - Westbound ; source metadata direction: South West; observed direction: South West; agree: True.
- Road: `ABERDEEN PRAYA ROAD` route `2404` arc `2404:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (834430.0, 812095.0); actual point-to-polyline 41.14 m; local tangent error 22.8°; name check `name_in_detector_description`; parallel/grade risk `False`.
- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.

## AID01223: authentic metadata and candidate route

- Detector description: Aberdeen Praya Road near Aberdeen Bus Terminus - Westbound ; source metadata direction: North West; observed direction: North West; agree: True.
- Road: `ABERDEEN PRAYA ROAD` route `4255` arc `4255:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (833976.0, 812080.0); actual point-to-polyline 5.71 m; local tangent error 26.9°; name check `name_in_detector_description`; parallel/grade risk `False`.
- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.

## Source INTERSECTION and TURN evidence

- Original INTERSECTION records: [ranked_pair_intersections.csv](ranked_pair_intersections.csv); TURN records touching reviewed routes: [ranked_pair_turns.csv](ranked_pair_turns.csv).
- Source endpoint continuity and intersection membership do **not** prove legal movements; negative NO_TURN restrictions blocked, conditional/fractional restrictions and absence-of-prohibition require human check.

## Historical and measurement review gate (leave blank until independent approval)

- [ ] Identify both physical lanes, parallel carriageways, bridges/tunnels and source elevation code meanings.
- [ ] Confirm path arc direction, endpoint/intersection membership, TURN movement conditions and relevant traffic regulations.
- [ ] Obtain 2023–September 2026 effective network versions, changes, and detector install/retirement evidence; `irn_version=20221210` is NOT reconciled to October 2026 CENTERLINE.
- [ ] Confirm neighbor lane measurement independence and as-of archive replay semantics; do not fit on candidate-level opportunity data.
- Reviewer identity: ______  Decision: ______  Evidence URLs/SHA-256: ______  Historical [valid_from, valid_to): ______

## Original network source SHA-256 / timestamps

- `CENTERLINE.gml`: https://static.data.gov.hk/td/road-network-v2/CENTERLINE.gml; SHA-256 `4fad0303e65c759ac7abe8eea3920b3ffcfcd5149c978fa9540bf032933a32c2`; retrieved `2026-10-27T08:18:13.720420+00:00`; HTTP Last-Modified `Fri, 09 Oct 2026 04:20:50 GMT`.
- `INTERSECTION.gml`: https://static.data.gov.hk/td/road-network-v2/INTERSECTION.gml; SHA-256 `79119240315ea989b18e715d54f7146ff8bcbc9c51aeb91ed46857c0bf72fa5f`; retrieved `2026-10-27T11:10:09.851369+00:00`; HTTP Last-Modified `Fri, 09 Oct 2026 04:20:05 GMT`.
- `TURN.gml`: https://static.data.gov.hk/td/road-network-v2/TURN.gml; SHA-256 `790ce25722354a796f59becc7c6adf82766ebb4289f96621ef118ed4179a38b0`; retrieved `2026-10-27T11:09:51.963224+00:00`; HTTP Last-Modified `Fri, 09 Oct 2026 04:20:21 GMT`.
- Detector metadata SHA-256: `f30818ec94984c024f0188e2e45139ac684c4636aae7906561e227f01407423d`; source metadata historical date unspecified.
