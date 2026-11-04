"""Official gazetted holiday editions and archive-time-safe HKO station joins."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, csv, hashlib, io, json, re, sys, zipfile
from urllib.parse import urlencode
import numpy as np
import pandas as pd
from html.parser import HTMLParser
from paths import ROOT, BASE, DATA, traffic_file
SOURCES = BASE / 'sources'
PREP = BASE / 'prepared'
sys.path.insert(0, str(ROOT / 'src'))
from traffic_recovery.external.calendar import calendar_features

class _HolidayHTML(HTMLParser):
    """Read table cells and page evidence using only the Python standard library."""
    def __init__(self) -> None:
        super().__init__(); self.rows = []; self.text = []; self.row = None; self.cell = None
    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == 'tr': self.row = []
        if tag in ('td', 'th') and self.row is not None: self.cell = []
    def handle_data(self, data: str) -> None:
        self.text.append(data.strip())
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split())); self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row); self.row = None


def events(data_dir: Path = DATA) -> pd.DataFrame:
    return pd.read_parquet(traffic_file(data_dir,'events.parquet'))

def holidays(*, data_dir: Path = DATA, source_cache: Path = SOURCES, output_dir: Path = PREP) -> None:
    """Parse published annual editions; derive event-time calendar features."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    editions = []
    for year in range(2023, 2027):
        path = source_cache / f'holidays_{year}.html'
        page = _HolidayHTML(); page.feed(path.read_text(encoding='utf-8-sig'))
        text = ' '.join(page.text)
        assert f'General holidays for {year}' in text
        dates = {2023: '2022-05-13', 2024: '2023-05-25', 2025: '2024-05-03', 2026: '2025-05-16'}
        published = pd.Timestamp(dates[year] + ' 11:00', tz='Asia/Hong_Kong')
        assert 'Issued at HKT 11:00' in text
        assert datetime.strptime(dates[year], '%Y-%m-%d').strftime('%B %d, %Y').replace(' 0', ' ') in text
        meta = json.loads(path.with_suffix('.html.meta.json').read_text(encoding='utf-8'))
        common = {'available_at': published, 'source_url': meta['requested_url'], 'source_retrieved_at': pd.Timestamp(meta['retrieved_at']), 'source_sha256': meta['sha256']}
        explicit = []
        for cells in page.rows:
            if len(cells) != 3 or cells[0] == 'Every Sunday':
                continue
            if not re.match('^[A-Za-z]+ \\d{1,2}$', cells[1]):
                continue
            local = datetime.strptime(f'{year} {cells[1]}', '%Y %B %d').date()
            assert local.strftime('%A') == cells[2]
            explicit.append(local)
            rows.append({'holiday_id': f'gazette-{year}-{local.isoformat()}', 'local_date': str(local), 'holiday_name': cells[0], **common})
        assert len(explicit) == 17, f'Expected 17 named general holidays for {year}'
        assert 'Every Sunday' in text
        for date in pd.date_range(f'{year}-01-01', f'{year}-12-31', freq='W-SUN'):
            if date.date() not in explicit:
                rows.append({'holiday_id': f'gazette-{year}-{date.date()}', 'local_date': str(date.date()), 'holiday_name': 'Every Sunday', **common})
        editions.append({'year': year, 'published_at': published.isoformat(), 'named_holidays': len(explicit), **{k: str(v) for k, v in common.items()}})
    table = pd.DataFrame(rows)
    assert table.local_date.is_unique
    table.to_parquet(output_dir / 'official_holiday_editions.parquet', index=False)
    context = calendar_features(events(data_dir)[['event_id', 'prediction_time']], table)
    assert context.is_public_holiday.notna().all()
    assert (context.calendar_max_source_available_at <= context.prediction_time).all()
    context.to_parquet(output_dir / 'calendar_event_features.parquet', index=False)
    (output_dir / 'holiday_source_manifest.json').write_text(json.dumps(editions, indent=2), encoding='utf-8')
    print('Official calendar:', len(table), 'holidays;', len(context), 'event features', flush=True)

def weather(*, data_dir: Path = DATA, source_cache: Path = SOURCES, output_dir: Path = PREP) -> None:
    """Replay archived station observations available before each prediction."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out = []
    errors = []
    inventories = []
    event_times = events(data_dir).prediction_time.astype('int64').to_numpy()
    for kind, column, position in [('temperature', 'temperature_c', 2), ('wind', 'wind_speed_kmh', 3)]:
        paths = sorted(source_cache.glob(f'{kind}_????????.zip'))
        for j, path in enumerate(paths, 1):
            metadata = json.loads(path.with_suffix('.zip.meta.json').read_text(encoding='utf-8'))
            count = 0
            with zipfile.ZipFile(path) as z:
                tokens = sorted({Path(i.filename).name[:13] for i in z.infolist() if i.filename.endswith('.csv') and re.fullmatch('\\d{8}-\\d{4}', Path(i.filename).name[:13])})
                capture_times = pd.to_datetime(tokens, format='%Y%m%d-%H%M').tz_localize('Asia/Hong_Kong').asi8
                positions = np.searchsorted(capture_times, event_times, side='right') - 1
                needed = {tokens[i] for i in positions if i >= 0}
                seen = set()
                for info in z.infolist():
                    if not info.filename.endswith('.csv'):
                        continue
                    token = Path(info.filename).name[:13]
                    if token not in needed:
                        continue
                    if not re.fullmatch('\\d{8}-\\d{4}', token):
                        errors.append({'archive': path.name, 'member': info.filename, 'reason': 'invalid_capture_filename'})
                        continue
                    payload = z.read(info)
                    signature = (info.filename, hashlib.sha256(payload).hexdigest())
                    if signature in seen:
                        continue
                    seen.add(signature)
                    reader = csv.reader(io.StringIO(payload.decode('utf-8-sig')))
                    header = next(reader, None)
                    if not header or header[:2] != ['Date time', 'Automatic Weather Station']:
                        errors.append({'archive': path.name, 'member': info.filename, 'reason': 'unrecognised_schema'})
                        continue
                    matches = [row for row in reader if len(row) > position and row[1].strip() == "King's Park"]
                    if len(matches) != 1:
                        errors.append({'archive': path.name, 'member': info.filename, 'reason': 'station_missing_or_ambiguous'})
                        continue
                    row = matches[0]
                    observed = pd.to_datetime(row[0], format='%Y%m%d%H%M', errors='coerce')
                    if pd.isna(observed):
                        errors.append({'archive': path.name, 'member': info.filename, 'reason': 'invalid_observation_time'})
                        continue
                    observed = observed.tz_localize('Asia/Hong_Kong')
                    available = pd.Timestamp(datetime.strptime(token, '%Y%m%d-%H%M'), tz='Asia/Hong_Kong')
                    if available < observed:
                        errors.append({'archive': path.name, 'member': info.filename, 'reason': 'capture_precedes_observation'})
                        continue
                    value = pd.to_numeric(row[position], errors='coerce')
                    if pd.notna(value) and (kind == 'wind' and value < 0 or (kind == 'temperature' and (not -20 <= value <= 60))):
                        value = np.nan
                    original = {'temperature': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_1min_temperature.csv', 'wind': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind.csv'}[kind]
                    out.append({'kind': kind, 'station_id': "King's Park", 'observed_at': observed, 'available_at': available, 'value': value, 'source_url': 'https://app.data.gov.hk/v1/historical-archive/get-file?' + urlencode({'url': original, 'time': token}), 'archive_file': path.name, 'archive_member': info.filename, 'source_sha256': signature[1], 'source_retrieved_at': pd.Timestamp(metadata['retrieved_at'])})
                    count += 1
            inventories.append({'kind': kind, 'archive': path.name, 'usable_station_records': count, 'archive_sha256': metadata['sha256']})
            if j % 10 == 0 or j == len(paths):
                print(kind, j, '/', len(paths), 'archives parsed', flush=True)
    observations = pd.DataFrame(out)
    observations = observations.sort_values(['kind', 'available_at', 'observed_at', 'source_sha256']).drop_duplicates(['kind', 'available_at', 'observed_at', 'source_sha256'])
    observations.to_parquet(output_dir / 'weather_station_snapshots.parquet', index=False)
    e = events(data_dir)[['event_id', 'prediction_time']].sort_values('prediction_time')
    result = e.copy()
    for kind, column in [('temperature', 'temperature_c'), ('wind', 'wind_speed_kmh')]:
        source = observations.loc[observations.kind.eq(kind)].copy()
        ambiguous = source.duplicated('available_at', keep=False)
        source = source.loc[~ambiguous].sort_values('available_at')
        payload = source.rename(columns={'value': column, 'available_at': kind + '_available_at', 'observed_at': kind + '_observed_at'})
        cols = [kind + '_available_at', kind + '_observed_at', column, 'archive_file', 'archive_member', 'source_sha256']
        payload = payload[cols].rename(columns={c: kind + '_' + c for c in ('archive_file', 'archive_member', 'source_sha256')})
        joined = pd.merge_asof(e, payload, left_on='prediction_time', right_on=kind + '_available_at', direction='backward', tolerance=pd.Timedelta(hours=1))
        age = (joined.prediction_time - joined[kind + '_observed_at']).dt.total_seconds() / 60
        valid = age.between(0, 60) & joined[kind + '_available_at'].le(joined.prediction_time)
        joined.loc[~valid, column] = np.nan
        joined[kind + '_age_minutes'] = age.where(valid)
        joined[kind + '_missing'] = joined[column].isna().astype(int)
        result = result.merge(joined, on=['event_id', 'prediction_time'], validate='one_to_one')
    result['weather_station_id'] = "King's Park"
    for kind in ('temperature', 'wind'):
        value = 'temperature_c' if kind == 'temperature' else 'wind_speed_kmh'
        populated = result[value].notna()
        assert (result.loc[populated, kind + '_available_at'] <= result.loc[populated, 'prediction_time']).all()
        assert result.loc[populated, kind + '_age_minutes'].between(0, 60).all()
    result.to_parquet(output_dir / 'weather_event_features.parquet', index=False)
    (output_dir / 'weather_parser_exclusions.json').write_text(json.dumps(errors, indent=2), encoding='utf-8')
    pd.DataFrame(inventories).to_csv(output_dir / 'weather_archive_inventory.csv', index=False)
    print('Weather event features:', result.shape, 'temperature known', result.temperature_c.notna().sum(), 'wind known', result.wind_speed_kmh.notna().sum(), flush=True)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['calendar', 'weather'])
    args = parser.parse_args()
    {'calendar': holidays, 'weather': weather}[args.step]()
