# Evidence-ranked official road candidate — independent review needed

Source direction map: [ranked-directed-pair-1.png](ranked-directed-pair-1.png). Original official LineStrings in EPSG:2326; no straight-line road inference.
Detectors: `AID03120` (North West/Slow Lane) → `AID03121` (North West/Middle Lane).
Arcs: `279966:F|93503:F`; source routes `279966|93503`; endpoint keys `82409003:83306746:0`.
Source INTERSECTION IDs `13565`; candidate path length `382.7234751265588` m (distance along projected source geometry, excludes point-to-road offsets).
Candidate evidence score `8.595973724286152`; ranking uses names, point distances, metadata-direction agreement and ambiguity only, **not** test model performance.

## AID03120: authentic metadata and candidate route

- Detector description: Tsing Long Highway near MTR Kam Sheung Road Station - Northbound (2) ; source metadata direction: North West; observed direction: North West; agree: True.
- Road: `TSING LONG HIGHWAY` route `279966` arc `279966:F`, source direction code `3` grade `0`; last road update `20221111103536` (not historical proof).
- EPSG:2326 point (824312.0, 832852.0); actual point-to-polyline 10.55 m; local tangent error 6.1°; name check `name_in_detector_description`; parallel/grade risk `False`.
- Other plausible carriageways/grade-separated alternatives: [all candidates](mapping_candidates96.parquet); human review required.

## AID03121: authentic metadata and candidate route

- Detector description: Tsing Long Highway near Kam Tin Road - Northbound (1) ; source metadata direction: North West; observed direction: North West; agree: True.
- Road: `TSING LONG HIGHWAY` route `93503` arc `93503:F`, source direction code `3` grade `0`; last road update `20090508200000` (not historical proof).
- EPSG:2326 point (824037.0, 833122.0); actual point-to-polyline 17.53 m; local tangent error 13.6°; name check `name_in_detector_description`; parallel/grade risk `False`.
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
