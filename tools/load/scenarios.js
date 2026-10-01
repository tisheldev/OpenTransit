import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// No setup traffic: supply generation-matched synthetic fixtures.
const base = (__ENV.BASE_URL || '').replace(/\/$/, '');
if (!/^https?:\/\//.test(base) || /[?#]/.test(base)) throw new Error('Set BASE_URL to authorized origin');
if (!__ENV.FIXTURES) throw new Error('Set FIXTURES to curated JSON');
const fixtures = JSON.parse(open(__ENV.FIXTURES));
const endpoints = ['journeys', 'places', 'departures', 'trips'];
const selected = __ENV.SCENARIO || 'all';
if (selected !== 'all' && !endpoints.includes(selected)) throw new Error('Invalid SCENARIO');
const enabled = selected === 'all' ? endpoints : [selected];
const defaults = { journeys: 180, places: 180, departures: 150, trips: 90 };
const clientTime = new Trend('client_round_trip_ms', true);
const failures = new Rate('response_failure');
const partialPlaces = new Rate('places_partial');
const statuses = new Counter('response_status');
const thresholds = { dropped_iterations: ['count==0'] };
const scenarios = {};
function integer(value, label) {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 1) throw new Error(label + ' must be positive integer');
  return n;
}
const vus = integer(__ENV.VUS_PER_SCENARIO || 10, 'VUS_PER_SCENARIO');
const maxVus = integer(__ENV.MAX_VUS_PER_SCENARIO || 50, 'MAX_VUS_PER_SCENARIO');
if (maxVus < vus) throw new Error('MAX_VUS_PER_SCENARIO must be >= VUS_PER_SCENARIO');
const maxP95 = Number(__ENV.MAX_CLIENT_P95_MS || 400);
if (!Number.isFinite(maxP95) || maxP95 <= 0) throw new Error('Invalid MAX_CLIENT_P95_MS');
for (const endpoint of enabled) {
  const items = fixtures[endpoint];
  if (!Array.isArray(items) || !items.length || JSON.stringify(items).includes('REPLACE_')) {
    throw new Error('Supply nonempty, completed ' + endpoint + ' fixtures');
  }
  scenarios[endpoint] = {
    executor: 'constant-arrival-rate', exec: endpoint,
    rate: integer(__ENV[endpoint.toUpperCase() + '_RPM'] || defaults[endpoint], endpoint + '_RPM'),
    timeUnit: '1m', duration: __ENV.DURATION || '1m',
    preAllocatedVUs: vus, maxVUs, gracefulStop: '15s',
  };
  thresholds['client_round_trip_ms{endpoint:' + endpoint + '}'] = ['p(95)<' + maxP95];
  thresholds['response_failure{endpoint:' + endpoint + '}'] = ['rate<0.005'];
}
export const options = {
  scenarios, thresholds, summaryTrendStats: ['avg', 'min', 'p(50)', 'p(95)', 'max'],
  // Never tag queries, URLs, IPs or request IDs.
  systemTags: ['name', 'method', 'status', 'scenario', 'expected_response'],
};
function pick(endpoint) {
  const items = fixtures[endpoint];
  return items[(__ITER + __VU - 1) % items.length];
}
function query(params) {
  return Object.keys(params).flatMap((key) => {
    const values = Array.isArray(params[key]) ? params[key] : [params[key]];
    return values.map((value) => encodeURIComponent(key) + '=' + encodeURIComponent(value));
  }).join('&');
}
function send(endpoint, method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (__ENV.AUTH_TOKEN) headers.Authorization = 'Bearer ' + __ENV.AUTH_TOKEN;
  const started = Date.now();
  const response = http.request(method, base + path, body, {
    headers, tags: { name: endpoint, endpoint }, timeout: __ENV.TIMEOUT || '5s', redirects: 0,
  });
  // Includes connection/TLS and body read around the synchronous request.
  const elapsed = Date.now() - started;
  clientTime.add(elapsed, { endpoint });
  statuses.add(1, { endpoint, status: String(response.status) });
  let payload;
  try { payload = response.json(); } catch (_) { payload = null; }
  const valid = check(response, {
    '200 with data and generation metadata': (r) => r.status === 200 &&
      payload !== null && payload.data !== undefined && Boolean(payload.meta?.generationId),
  }, { endpoint });
  failures.add(!valid, { endpoint }); // Includes 429/503/504 in denominator.
  if (endpoint === 'places' && response.status === 200) {
    partialPlaces.add(Boolean(payload?.partial), { endpoint });
  }
  if (__ENV.CORRELATE === '1') {
    const header = Object.keys(response.headers).find((key) => key.toLowerCase() === 'x-request-id');
    console.log('OT_LOAD_TIMING ' + JSON.stringify({
      request_id: header ? response.headers[header] : null,
      endpoint, client_ms: elapsed, status: response.status, valid,
    }));
  }
}
export function journeys() { send('journeys', 'POST', '/v1/journeys', JSON.stringify(pick('journeys'))); }
export function places() { send('places', 'GET', '/v1/places?' + query(pick('places')), null); }
export function departures() {
  const item = pick('departures');
  send('departures', 'GET', '/v1/stops/' + encodeURIComponent(item.stopId) + '/departures?' + query({
    from: item.from, horizonMinutes: item.horizonMinutes || 60, limit: item.limit || 20,
  }), null);
}
export function trips() { send('trips', 'GET', '/v1/trips/' + encodeURIComponent(pick('trips').tripRef), null); }
