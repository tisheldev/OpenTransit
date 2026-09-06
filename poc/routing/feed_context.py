"""Verified primary input, service-calendar dates and graph provenance."""
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

POC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC.parent))
from poc.gtfs.fetch import sha256_file
from poc.gtfs.zipread import GtfsZip
from poc.gtfs.parse import parse_services
from poc.gtfs.pairing import parse_trip_id_to_date, pair_or_raise

PRIMARY = 'israel-public-transportation.zip'
IL = ZoneInfo('Asia/Jerusalem')

def departure_iso(local):
    return dt.datetime.fromisoformat(local).replace(tzinfo=IL).isoformat()

def resolve_rules(rules, window):
    resolved = {'feed_window': f'{window[0]} .. {window[1]}'}
    weekdays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    for name, rule in rules.items():
        if not isinstance(rule, dict) or 'weekday' not in rule:
            continue
        day = window[0] + dt.timedelta(days=(weekdays.index(rule['weekday']) - window[0].weekday()) % 7)
        if day > window[1]:
            raise ValueError(f'No date for {name} in feed window')
        resolved[name] = f'{day} {rule["time"]}'
    return resolved

def inputs():
    manifest = json.loads((POC / 'data/manifest.json').read_text(encoding='utf-8'))
    hashes = {}
    for name in (PRIMARY, 'TripIdToDate.zip', 'israel-and-palestine-latest.osm.pbf'):
        actual = sha256_file(POC / 'data' / name)
        if actual != manifest['files'][name]['sha256']:
            raise ValueError(f'{name} differs from manifest; record the new publication first')
        hashes[name] = actual
    return hashes

def prepare():
    hashes = inputs()
    with GtfsZip(POC / 'data' / PRIMARY) as z:
        services = parse_services(z)
        trips = {r['trip_id'] for r in z.rows('trips.txt')}
    dates = sorted({d for s in services.services.values() for d in s.active_dates})
    window = dates[0], dates[-1]
    pairing = pair_or_raise(trips, parse_trip_id_to_date(POC / 'data/TripIdToDate.zip'), window)
    corpus_path = POC / 'corpora/journeys.json'
    corpus = json.loads(corpus_path.read_text(encoding='utf-8'))
    rules = corpus['depart_rules']
    for key in list(rules):
        if key.startswith('resolved_for_feed_'):
            del rules[key]
    resolved = resolve_rules(rules, window)
    rules['note'] = 'Resolved from calendar.txt plus calendar_dates.txt exceptions; feed_info.txt is optional. First matching weekday in the actual service window, Asia/Jerusalem timezone.'
    rules['resolved_for_feed_' + hashes[PRIMARY][:16]] = resolved
    corpus_path.write_text(json.dumps(corpus,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    config_path = POC / 'routing/config.yml'
    import re
    config = config_path.read_text()
    config = re.sub(r'first_day: .*', f'first_day: {window[0]}', config)
    config = re.sub(r'num_days: .*', f'num_days: {(window[1]-window[0]).days+1}', config)
    config_path.write_text(config)
    return {'feed_name': PRIMARY, 'feed_sha256': hashes[PRIMARY], 'input_sha256': hashes,
            'config_sha256': sha256_file(config_path), 'service_window': list(map(str,window)),
            'pairing': pairing}

def verified_context():
    hashes = inputs()
    build = json.loads((POC / 'routing/import-result.json').read_text())
    if not build.get('ok') or build.get('input_sha256') != hashes:
        raise ValueError('Graph build does not match the primary inputs; rerun run_import.py')
    if build.get('config_sha256') != sha256_file(POC / 'routing/config.yml'):
        raise ValueError('Routing config changed since import')
    rules = json.loads((POC / 'corpora/journeys.json').read_text(encoding='utf-8'))['depart_rules']
    resolved = rules['resolved_for_feed_' + hashes[PRIMARY][:16]]
    expected = resolve_rules(rules, tuple(dt.date.fromisoformat(d) for d in build['service_window']))
    if resolved != expected:
        raise ValueError('Corpus departures differ from the service-window rules; rerun the import preflight')
    return hashes[PRIMARY], resolved

if __name__ == '__main__':
    print(json.dumps(prepare(),indent=2))
