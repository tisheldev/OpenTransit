"""Assemble current measurements, rejecting mixed-feed evidence."""
import json
from pathlib import Path
from datetime import datetime, timezone
from feed_context import verified_context, PRIMARY

POC = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((POC / 'routing' / name).read_text(encoding='utf-8'))

sha, _ = verified_context()
primary = read('corpus-result.json')
variant = read('corpus-result-generous-walk.json')
build = read('import-result.json')
stress = read('serving-stress.json')
steady = read('serving-steady.json')
for item in (primary, variant, build, stress, steady):
    if item.get('feed_sha256') != sha:
        raise ValueError('Mixed-feed evidence; rerun all routing measurements')
j = primary['journeys']
state = stress['container_state_after']
fits = (stress['samples'] > 0 and stress['cap_observed_bytes'] == 8 * 1024**3
        and stress['peak_rss_bytes'] < 8 * 1024**3 and not state.get('oom_killed', True)
        and state.get('status') == 'running' and state.get('restart_count') == 0)
out = {
    'poc': 2, 'name': 'Public transportation routing', 'status': 'PARTIAL',
    'generated': datetime.now(timezone.utc).isoformat(), 'feed_name': PRIMARY, 'feed_sha256': sha,
    'headline': f"{j['answered']}/{j['total']} answered; {j['structural_pass_any']} structural passes "
                f"({j['structural_pass_first']} first itinerary); load peak {stress['peak_rss_mb']} MB; H3 pending",
    'capabilities': {'route_gtfs': build['ok'] and any(c['outcome']=='route' for c in primary['cases']),
                     'walk_transit_transfer': bool(primary['wttw_shape_cases'])},
    'metrics': {
        'build': {k: build[k] for k in ('wall_seconds','peak_rss_mb','graph_size_mb','memory_cap','service_window')},
        'serving': {'steady_rss_mb': steady['steady_rss_mb'], 'memory_cap_gb': 8,
                    'fits_in_8gb': fits, 'peak_rss_mb_under_load': stress['peak_rss_mb'],
                    'cap_verified_bytes': stress['cap_observed_bytes'], 'load_test': stress},
        'journeys': {**j, 'structural_pass': j['structural_pass_any'],
                     'structural_pass_first_itinerary': j['structural_pass_first'],
                     'structural_pass_generous_walk_profile': variant['journeys']['structural_pass_any']},
    },
    'human_checkpoint': {'id':'H3','status':'pending','sheet':'poc/results/journeys-h3-review.md',
                         'bar':'9/10 required journeys reasonable and usable, checked by a person'},
    'cases': primary['cases'],
    'notes': [
        'Primary is the 60-day product; sampled calendar: '+ ' .. '.join(build['service_window'])+'.',
        'TripIdToDate has complete normalized key coverage and an overlapping date window. This does not prove realtime matching or identical publication versions.',
        'Dates derive from service calendars and use Asia/Jerusalem. Calendar extension is disabled.',
        'Build is uncapped; serving is capped at 8 GiB. This measures MOTIS only, not full-stack capacity.',
        'Structural checks do not judge route quality. H3 remains pending.',
        'Ten-day evidence: poc/comparisons/ten-day-2026-09-04. Later corpus coordinate changes confound comparisons for J17/J21/J23.',
    ],
}
path = POC / 'results/poc-2.json'
path.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'wrote {path}')
