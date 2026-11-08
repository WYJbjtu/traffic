# Copy-ready figure captions

## Figure 1: 01_spatial_gain_cw

**Placement:** Main result; centre/right, largest result panel

Paired F7 minus F3 ROC-AUC differences for 30-minute recovery confirmation on 3,933 identical P1 retrospective inferred-network test events. F3 includes local, history, observation quality, calendar, temperature and wind; F7 adds inferred spatial features. Bars are unadjusted 95% detector-cluster Bootstrap intervals (1,000 paired draws; 44 target detectors), conditional on fixed fitted models. Shared-neighbor dependence is not fully addressed.

Files: `figures/01_spatial_gain_cw.png`, `.svg`, `.pdf`.

## Figure 2: 02_real_directed_network

**Placement:** Method; upper-left/centre

Official CENTERLINE polylines and real detector positions illustrate inferred directed relationships around AID01104. Colored paths follow adopted official road subsegments, not straight-line detector links. Dotted segments are mapping offsets. Geometry-based, score-independent selection; AID01103 remains ambiguously matched. A 2026 snapshot does not establish historical or legally verified connectivity.

Files: `figures/02_real_directed_network.png`, `.svg`, `.pdf`.

## Figure 3: 03_real_event_case

**Placement:** Data/label explanation; lower-left/centre

The first eligible chronological P1 test event (237614b88349c5712337, AID02110, 2 January 2026 at 08:35 HKT), selected without prediction-score filtering. Speeds are ratios to each unit’s own frozen reference. Neighbor measurements are as-of points, not continuous curves; orange local observations were unavailable at prediction. Thresholds and the 30-minute outcome window are shown. The negative label means no qualifying recovery confirmation within the horizon, not permanent non-recovery.

Files: `figures/03_real_event_case.png`, `.svg`, `.pdf`.

## Figure 4: 04_full_matrix_auc

**Placement:** Optional supplementary panel; omit if crowded

All 32 refitted model/feature arms on the same P1 test events. Base is local/history/observation quality; C is calendar, W is temperature/wind, and S is inferred spatial. Two fixed candidates per model/arm were selected by validation log loss. These previously examined test data do not select a new best model.

Files: `figures/04_full_matrix_auc.png`, `.svg`, `.pdf`.

## Figure 5: 05_matched_structure_controls

**Placement:** Optional small sensitivity panel

Current C/W-adjusted RF and XGBoost structure comparisons use F3 plus the same 12 S1 summary fields, not full F7. Directed and pooled representations use identical neighbor observations; geographic neighbors follow the frozen 250 m rule. Geographic availability is 67.2% of test events versus 100% for the other representations. The small directed–pooled differences do not establish a direction-specific effect; the vertical axis is explicitly zoomed.

Files: `figures/05_matched_structure_controls.png`, `.svg`, `.pdf`.
