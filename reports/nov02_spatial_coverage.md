# 2026-11-02 · Spatial candidate coverage diagnostic (read-only review)

**Scientific gate: NO-GO.** This is a cross-check of previously preserved real-source outputs, not a newly reviewed matching campaign. Scope: `reports/spatial_feasibility/quality.json`, `detector_mapping.csv`, `candidate_detector_connections.csv`, `spatial_features_review.csv`; official CENTERLINE/INTERSECTION/TURN source hashes and network snapshot described in `docs/spatial_feasibility.md`. The 500m corridor around 39 short-pilot detector-direction units is not the 24-unit 2023–2026 long-window cohort. Do not transfer its proportions to long-window model coverage.

| Evidence item | Observed subset | Scientific status |
|---|---:|---|
| Official road segments / directed arcs | 3,197 / 4,017 | Source geometry and direction codes; subset-limited |
| Endpoint weak components | 156 | Not legal route reachability |
| Candidate mapped detector-direction units | 39 / 39 | Automatic candidates, not confirmed |
| Ambiguous compatible matches | 23 / 39 | Review required |
| Direction disagreements with current metadata | 8 / 39 | Version/direction reconciliation required |
| Source-supported candidate detector pairs | 6 | Leads only, not upstream/downstream |
| Human-verified detector matches / transitions | 0 / 0 | **No valid directed neighbor features** |
| Medium-pilot event rows eligible for spatial ablation | 0 / 40 | All-null reviewed feature output |

**Maps for human review (already generated from authentic source geometry):** [overview](spatial_feasibility/detector_map.png), [detail 1](spatial_feasibility/detector_review_1.png), [detail 2](spatial_feasibility/detector_review_2.png), [detail 3](spatial_feasibility/detector_review_3.png), [detail 4](spatial_feasibility/detector_review_4.png). [All 300 match candidates](spatial_feasibility/matching_candidates.csv) include distance, compass/tangent error and review status. [Connection sample](spatial_feasibility/connection_review_sample.csv) includes pending/rejected evidence. Displayed in Streamlit Network Evidence as candidates, never verified routes. Geometry in EPSG:2326; do not join based on geographic proximity.

**Feasibility distinction:** segment length, official direction code and source elevation can be read now. Candidate endpoint degree and junction incidence can be computed for a *scoped topology diagnostic*, but not certified as legal/historical node degree until topology, elevation and turn rules are reviewed. Official road class has not been validated as a usable field. For dynamic upstream/downstream speed, ratio and coverage require approved detector-carriageway mappings, approved directed transitions, contemporaneous network version/effective dates and neighbor bins observed **and available** before prediction. The current 2026-10-08 network snapshot does not certify 2023–2026 validity. No candidate feature is added to experimental metrics.

**Next owner decision:** Member 2 review ambiguous/grade-separated roads, current metadata disagreement, turns and historical versions with explicit reviewer/effective interval; Member 1/4 approve event definitions and a paired event-row eligibility test. Rebuild coverage under verified-only gates and report eligible counts by horizon before requesting spatial ablation approval.
