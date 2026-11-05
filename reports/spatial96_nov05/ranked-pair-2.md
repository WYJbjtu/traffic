# Evidence-ranked official road candidate — independent review needed

Source direction map: [ranked-directed-pair-2.png](ranked-directed-pair-2.png). Original official LineStrings in EPSG:2326; no straight-line road inference.
Detectors: `AID01131` (North East/Slow Lane) → `AID01133` (North East/Fast Lane).
Arcs: `62198:F|61564:F|61190:F|62476:F|61436:F`; source routes `62198|61564|61190|62476|61436`; endpoint keys `83855450:82656289:0|83856003:82657748:0|83858877:82662879:0|83869200:82680956:0`.
Source INTERSECTION IDs `25818|25831|25866|25968`; candidate path length `877.4819775349679` m (distance along projected source geometry, excludes point-to-road offsets).
Candidate evidence score `8.39685504368527`; ranking uses names, point distances, metadata-direction agreement and ambiguity only, **not** test model performance.

## AID01131: authentic metadata and candidate route

- Detector description: Sha Tin Road near Sha Tin Wai New Village - Northbound ; source metadata direction: North East; observed direction: North East; agree: True.
- Road: `SHA TIN ROAD` route `62198` arc `62198:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (838512.0, 826339.0); actual point-to-polyline 27.72 m; local tangent error 18.7°; name check `name_in_detector_description`; parallel/grade risk `False`.
- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.

## AID01133: authentic metadata and candidate route

- Detector description: Sha Tin Road near Shing Mun River - Northbound(1) ; source metadata direction: North East; observed direction: North East; agree: True.
- Road: `SHA TIN ROAD` route `61436` arc `61436:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (838796.0, 827166.0); actual point-to-polyline 4.35 m; local tangent error 31.5°; name check `name_in_detector_description`; parallel/grade risk `False`.
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
