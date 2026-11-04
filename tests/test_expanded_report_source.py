"""Synthetic path/evidence tests; not research observations."""
import pytest
from traffic_recovery.data.selection_evidence import selection_directory
from traffic_recovery.data.http import sha256_file


def test_manifest_path_locates_frozen_selection_on_data_owner_machine(tmp_path):
    profile=tmp_path/'coverage_lane_day.parquet';profile.write_bytes(b'synthetic evidence')
    result={'selection_frozen_from':str(profile),'selection_profile_sha256':sha256_file(profile)}
    assert selection_directory(result)==tmp_path


def test_relocated_selection_requires_matching_frozen_hash(tmp_path):
    profile=tmp_path/'coverage_lane_day.parquet';profile.write_bytes(b'synthetic evidence')
    result={'selection_frozen_from':'absent/coverage_lane_day.parquet','selection_profile_sha256':sha256_file(profile)}
    assert selection_directory(result,tmp_path)==tmp_path
    profile.write_bytes(b'changed evidence')
    with pytest.raises(ValueError,match='checksum mismatch'):selection_directory(result,tmp_path)
