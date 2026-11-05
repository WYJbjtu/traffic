# Evidence-ranked official road candidate — independent review needed

Source direction map: [ranked-directed-pair-6.png](ranked-directed-pair-6.png). Original official LineStrings in EPSG:2326; no straight-line road inference.
Detectors: `AID01103` (South East/Middle Lane) → `AID01104` (North East/Slow Lane).
Arcs: `493:F|4304:F|163989:F`; source routes `493|4304|163989`; endpoint keys `83483575:81220289:0|83496518:81218317:0`.
Source INTERSECTION IDs `19653|140385`; candidate path length `380.4374783740929` m (distance along projected source geometry, excludes point-to-road offsets).
Candidate evidence score `7.235141521157908`; ranking uses names, point distances, metadata-direction agreement and ambiguity only, **not** test model performance.

## AID01103: authentic metadata and candidate route

- Detector description: Wong Chuk Hang Road near Aberdeen Technical School - Eastbound ; source metadata direction: South East; observed direction: South East; agree: True.
- Road: `WONG CHUK HANG ROAD` route `493` arc `493:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (834750.0, 812208.0); actual point-to-polyline 5.98 m; local tangent error 43.8°; name check `name_in_detector_description`; parallel/grade risk `False`.
- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.

## AID01104: authentic metadata and candidate route

- Detector description: Wong Chuk Hang Road Flyover near AXA Southside - Eastbound ; source metadata direction: North East; observed direction: North East; agree: True.
- Road: `WONG CHUK HANG ROAD` route `163989` arc `163989:F`, source direction code `3` grade `0`; last road update `20140401121233` (not historical proof).
- EPSG:2326 point (835128.0, 812179.0); actual point-to-polyline 9.31 m; local tangent error 36.3°; name check `name_in_detector_description`; parallel/grade risk `True`.
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
