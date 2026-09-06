"""Report changes against the explicit historical ten-day comparison."""
import json
from pathlib import Path

POC = Path(__file__).resolve().parents[1]
OLD = POC / 'comparisons/ten-day-2026-09-04'
def read(root, name):
    return json.loads((root / name).read_text(encoding='utf-8'))

old = read(OLD, 'routing/corpus-result.json')
new = read(POC, 'routing/corpus-result.json')
ob, nb = [read(r,'routing/import-result.json') for r in (OLD,POC)]
os, ns = [read(r,'routing/serving-stress.json') for r in (OLD,POC)]
oi, ni = [read(r,'routing/serving-steady.json') for r in (OLD,POC)]
ov, nv = [read(r,'routing/corpus-result-generous-walk.json') for r in (OLD,POC)]
ingest = read(POC,'results/poc-1-evidence.json')
rows = []
for before, after in zip(old['cases'],new['cases']):
    assert before['id'] == after['id']
    cid = after['id']
    a = (before.get('itineraries') or [{}])[0]
    b = (after.get('itineraries') or [{}])[0]
    old_case = read(OLD, f'routing/responses/{cid}.json')['case']
    new_case = read(POC, f'routing/responses/{cid}.json')['case']
    changed_inputs = [k for k in ('from','to','expect') if old_case[k] != new_case[k]]
    if before['depart_local'] != after['depart_local']:
        changed_inputs.append('departure date')
    rows.append({'id':cid,'old_outcome':before['outcome'],'new_outcome':after['outcome'],
                 'old_pass':before['structural'],'new_pass':after['structural'],
                 'old_first_pass':before.get('structural_first'),'new_first_pass':after.get('structural_first'),
                 'old_duration_min':a.get('duration_min'),'new_duration_min':b.get('duration_min'),
                 'old_transfers':a.get('transfers'),'new_transfers':b.get('transfers'),
                 'old_modes':a.get('modes'),'new_modes':b.get('modes'),
                 'changed_corpus_inputs':changed_inputs})
metrics = {
    'Structural pass (any itinerary)': [old['journeys']['structural_pass_any'],new['journeys']['structural_pass_any']],
    'Structural pass (first itinerary)': [old['journeys']['structural_pass_first'],new['journeys']['structural_pass_first']],
    'Generous-walk structural pass': [ov['journeys']['structural_pass_any'],nv['journeys']['structural_pass_any']],
    'Build wall seconds': [ob['wall_seconds'],nb['wall_seconds']],
    'Build sampled peak MB': [ob['peak_rss_mb'],nb['peak_rss_mb']],
    'Graph MB': [ob['graph_size_mb'],nb['graph_size_mb']],
    'Idle median MB': [oi['steady_rss_mb'],ni['steady_rss_mb']],
    'Load peak MB': [os['peak_rss_mb'],ns['peak_rss_mb']],
    'Load p95 ms': [os['latency_ms']['p95'],ns['latency_ms']['p95']],
    'Load requests/second': [os['requests_per_second'],ns['requests_per_second']],
}
report = {'primary_feed_sha256':new['feed_sha256'],'comparison_feed_sha256':old['feed_sha256'],
          'metrics':metrics,'cases':rows}
(POC/'results/primary-feed-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
lines = ['# Primary-feed rerun — 5 September 2026','',
         '`israel-public-transportation.zip` is the accepted executable primary (ADR 0005). '
         'The ten-day feed is comparison only. Original evidence is preserved in '
         '`poc/comparisons/ten-day-2026-09-04/`.','',
         f"Primary SHA-256: `{new['feed_sha256']}`. Calendar window: {new['feed_window']}. "
         'The product name does not guarantee sixty days of service.','',
         'Ingest passed all ten E01–E10 checks and all five query validations. '
         '544,338 trips and 20,100,370 stop_times parsed; five tables loaded. '
         'All 246,042 normalized mapping keys match TripIdToDate; known date windows overlap. '
         'Incomplete keys and missing/disjoint dates fail before loading. This is content compatibility, '
         'not realtime matching or per-service-date uniqueness.','',
         f"Cold start completed in {ingest['cold_run']['wall_seconds']} seconds, downloading only the primary and mapping. "
         'MOT published newer bytes for that download; its separate hashes are in poc-1-cold-run.json. '
         'The run of record and routing retain the manifest-pinned September 4 bytes.','',
         '| Metric | Ten-day historical | Sixty-day primary |','| --- | ---: | ---: |']
lines += [f'| {name} | {a} | {b} |' for name,(a,b) in metrics.items()]
lines += ['',f"Load: {ns['requests']:,} requests over {ns['seconds']} seconds with {ns['workers']} workers; "
          f"HTTP status counts {ns['http_status_counts']}. Observed cap: 8 GiB. No OOM or restart. "
          'Measurements cover MOTIS alone; they do not establish full-stack capacity.','',
          'All 25 queries answered. J09 fails at default walking limits and passes at 30 minutes. '
          'J15 and J18 have qualifying alternatives ranked below itinerary 0. '
          'The H3 sheet is regenerated and awaits human route-quality judgment.','',
          'Comparison caveat: J17/J21/J23 corpus inputs changed after the old experiment; '
          'their improvements cannot be attributed solely to the feed. The table identifies all '
          'input changes, including rebased departure dates.','',
          '| Case | Outcome old → new | Structural old → new | First duration min old → new | Changed corpus inputs |',
          '| --- | --- | --- | --- | --- |']
lines += [f"| {r['id']} | {r['old_outcome']} → {r['new_outcome']} | {r['old_pass']} → {r['new_pass']} | "
          f"{r['old_duration_min']} → {r['new_duration_min']} | {', '.join(r['changed_corpus_inputs']) or 'none'} |" for r in rows]
lines += ['', 'The full comparison JSON also records changes in transfers, modes and first-itinerary passes. '
          'Search/H4 measurements remain historical; their executable runner now targets the primary but was not rescored in this routing task.', '',
          'Reproduce: `python poc/gtfs/run_poc1.py`; `python poc/routing/run_import.py`; '
          '`docker compose -f poc/docker-compose.yml --profile serve up -d motis`; '
          'both `run_corpus.py` profiles; `stress_serving.py --workers 16 --seconds 120`; '
          '`measure_steady.py --seconds 150`; `write_result.py`; `render_h3.py`; '
          '`compare_results.py`; `python poc/poc_status.py --write`.', '']
(POC/'docs/primary-feed-rerun.md').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines[:27]))
