"""Acquire authentic inputs with original bytes, URLs, timestamps and hashes."""
from __future__ import annotations
from pathlib import Path
import argparse, concurrent.futures, json, sys, zipfile
from bs4 import BeautifulSoup
from paths import ROOT, BASE, DATA
sys.path.insert(0, str(ROOT / 'src'))
from traffic_recovery.data.http import EvidenceClient
from traffic_recovery.data.sources import archive_url
SOURCES = BASE / 'sources'
SOURCES.mkdir(parents=True, exist_ok=True)
URLS = {'holidays_2023.html': 'https://www.info.gov.hk/gia/general/202205/13/P2022051000340.htm', 'holidays_2024.html': 'https://www.info.gov.hk/gia/general/202305/25/P2023052500208p.htm', 'holidays_2025.html': 'https://www.info.gov.hk/gia/general/202405/03/P2024043000417.htm', 'holidays_2026.html': 'https://www.info.gov.hk/gia/general/202505/16/P2025051300353.htm', 'archive_api_spec.html': 'https://data.gov.hk/en/help/api-spec', 'terms.html': 'https://data.gov.hk/en/terms-and-conditions'}
WEATHER = {'temperature': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_1min_temperature.csv', 'wind': 'https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind.csv'}

def fetch(name: str, url: str) -> Path:
    p = EvidenceClient(SOURCES, timeout=90, attempts=2, reuse=True).fetch(url, name)
    return p

def probe():
    for name, url in URLS.items():
        path = fetch(name, url)
        print(name, path.stat().st_size, flush=True)

def weather_all():
    import pandas as pd
    months = pd.period_range('2023-01', '2026-09', freq='M').strftime('%Y%m')
    jobs = [(f'{kind}_{m}01.zip', archive_url('get-file', url=url, time=m + '01')) for kind, url in WEATHER.items() for m in months]
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(fetch, name, url): name for name, url in jobs}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            name = futs[f]
            try:
                path = f.result()
                with zipfile.ZipFile(path) as z:
                    n = len(z.infolist())
                print(f'[{i}/{len(jobs)}] {name}: {path.stat().st_size} bytes; {n} members', flush=True)
            except Exception as exc:
                failures.append({'file': name, 'error': str(exc)})
                print(f'[{i}/{len(jobs)}] {name}: FAILED', flush=True)
    (SOURCES / 'weather_acquisition_failures.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
    if failures:
        raise RuntimeError(f'{len(failures)} required weather archives failed; see failure manifest')

def traffic():
    url = 'https://github.com/CityuHK-wyj/hk-traffic-recovery-prediction/releases/download/data-long-window-2023-2026-v1/HK_Traffic_Long_Window_Prepared_Data.zip'
    p = fetch('traffic_prepared.zip', url)
    from traffic_recovery.data.http import sha256_file
    expected = '53688e6e095798f50c124376da1f0f354ca4b2aedf9e83e960fef04fc7298bc9'
    assert sha256_file(p) == expected, 'Published whole-ZIP checksum mismatch'
    print('Prepared traffic ZIP: published whole-file SHA256 passed', flush=True)

def conditional_audit():
    sources = {'rainfall': 'https://data.weather.gov.hk/weatherAPI/opendata/hourlyRainfall.php?lang=en', 'incidents': 'https://www.td.gov.hk/en/special_news/trafficnews.xml', 'major_events': 'https://www.tourism.gov.hk/datagovhk/hktb_events/hktb_events_en.csv'}
    jobs = []
    for kind, url in sources.items():
        for start, end in [('20230201', '20230201'), ('20260930', '20260930')]:
            jobs.append((f'{kind}_inventory_{start}.json', archive_url('list-file-versions', url=url, start=start, end=end)))
    jobs.append(('hktb_events_current.csv', sources['major_events']))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(fetch, name, url): (name, url) for name, url in jobs}
        for f in concurrent.futures.as_completed(futs):
            name, url = futs[f]
            try:
                p = f.result()
                record = {'file': name, 'url': url, 'status': 'retrieved', 'bytes': p.stat().st_size}
                if name.endswith('.json'):
                    d = json.loads(p.read_text(encoding='utf-8'))
                    record.update(version_count=d.get('version-count'), returned_timestamps=len(d.get('timestamps', [])))
                else:
                    record['preview'] = p.read_text(encoding='utf-8-sig')[:1000]
            except Exception as exc:
                record = {'file': name, 'url': url, 'status': 'failed', 'error': str(exc)}
            results.append(record)
            print(record, flush=True)
    (SOURCES / 'conditional_source_audit.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['probe', 'weather', 'traffic', 'conditional-audit'])
    args = parser.parse_args()
    {'probe': probe, 'weather': weather_all, 'traffic': traffic, 'conditional-audit': conditional_audit}[args.step]()
