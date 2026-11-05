"""Synthetic boundary fixture for the real Parquet predicate call pattern."""
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


def test_arrow_filter_uses_iana_hkt_timezone(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    from scripts.validate_january_references import hkt_boundary
    day = hkt_boundary('2023-01-01T00:00:00+08:00')
    path = tmp_path / 'capture.parquet'
    pd.DataFrame({'timestamp': pd.to_datetime(['2023-01-01T00:30:00+08:00']).tz_convert('Asia/Hong_Kong'),
                  'detector_id': ['AID01101']}).to_parquet(path)
    table = pq.read_table(path, filters=[('timestamp','>',day), ('timestamp','<=',day + pd.Timedelta(days=1)),
                                           ('detector_id','==','AID01101')])
    assert len(table) == 1
    assert str(day.tzinfo) == 'Asia/Hong_Kong'
