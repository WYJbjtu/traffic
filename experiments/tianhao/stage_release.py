"""Verify the published release, then stage only three required input members."""
import hashlib, json, shutil, zipfile
from paths import BASE, DATA
EXPECTED = "53688e6e095798f50c124376da1f0f354ca4b2aedf9e83e960fef04fc7298bc9"
path = BASE / "sources/traffic_prepared.zip"
with path.open("rb") as stream:
    assert hashlib.file_digest(stream, "sha256").hexdigest() == EXPECTED
with zipfile.ZipFile(path) as archive:
    payload = archive.read("SHARED_DATA_MANIFEST.json")
    manifest = json.loads(payload)["files"]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "SHARED_DATA_MANIFEST.json").write_bytes(payload)
    for member in ["processed/derived/events.parquet", "processed/derived/cohort_bins.parquet", "reports/events_review.csv", "metadata/detectors.csv"]:
        target = DATA / member
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        with target.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest[member]["sha256"]
        print("Verified:", member)
