# Migration validation

Windows local verification with the GitHub command `uv run --locked pytest`: **255 passed, 1 warning**. Targeted publication and spatial tests: **14 passed**. All 11 committed files named by the spatial manifest match their original SHA-256 and are protected with directory-local `-text` attributes. No frozen manifest, source data or result numbers were edited.

Release upload sizes and GitHub server digests match the preserved original ZIPs. Public download verification and final CI results are recorded separately.
