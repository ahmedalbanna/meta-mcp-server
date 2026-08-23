/* k6 load test — Phase 6.3
   Tests webhook receiver (and optionally MCP via HTTP transport).

   Run: k6 run --vus 20 --duration 30s scripts/k6_load.js
   Env: BASE_URL=http://localhost:8080 (webhook) or MCP_URL=http://localhost:8000
*/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

export let options = {
  vus: 20,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<400'],
    http_req_failed: ['rate<0.01'],
  },
};

let verifyTrend = new Trend('verify_duration');
let webhookTrend = new Trend('webhook_duration');

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const VERIFY_TOKEN = __ENV.FB_META_WEBHOOK_VERIFY_TOKEN || 'test_token';

export default function () {
  // 1) Verify handshake (GET /webhook/meta)
  let verifyRes = http.get(`${BASE}/webhook/meta?hub.mode=subscribe&hub.verify_token=${VERIFY_TOKEN}&hub.challenge=1234`);
  check(verifyRes, { 'verify 200|403': (r) => r.status === 200 || r.status === 403 });
  verifyTrend.add(verifyRes.timings.duration);

  // 2) Webhook ingest (POST /webhook/meta)
  let payload = JSON.stringify({ entry: [{ id: '123', changes: [{ field: 'feed', value: { item: 'comment', verb: 'add' } }] }] });
  let params = { headers: { 'Content-Type': 'application/json', 'X-Hub-Signature-256': 'sha256=dummy', 'X-Correlation-ID': `k6-${__VU}-${__ITER}` } };
  let webhookRes = http.post(`${BASE}/webhook/meta`, payload, params);
  // 403 expected without valid signature if APP_SECRET set; 200 if skipped
  check(webhookRes, { 'webhook 200|403|400': (r) => [200, 403, 400].includes(r.status) });
  webhookTrend.add(webhookRes.timings.duration);

  // 3) Metrics
  let metricsRes = http.get(`${BASE}/metrics`);
  check(metricsRes, { 'metrics 200': (r) => r.status === 200 });

  // 4) Dashboard
  let dashRes = http.get(`${BASE}/dashboard`);
  check(dashRes, { 'dashboard 200|401': (r) => r.status === 200 || r.status === 401 });

  sleep(0.2);
}

export function handleSummary(data) {
  return {
    stdout: `k6 summary — p95 verify ${data.metrics.verify_duration ? data.metrics.verify_duration.values['p(95)'] : 'n/a'}ms, webhook ${data.metrics.webhook_duration ? data.metrics.webhook_duration.values['p(95)'] : 'n/a'}ms\n`,
  };
}
