// Screening load test (S6.5). Runs the same workload at 5 and at 50 concurrent clients (10x) and
// reports p95 latency per stage. Run against a stack you own, never production data:
//
//   docker run --rm -i --network finshield_finshield-network -e BASE_URL=http://backend:8091 \
//     -v "$PWD/loadtest:/scripts" grafana/k6:0.54.0 run /scripts/screening.js
//
// setup() registers a throwaway tenant and an API key, so the run never touches existing tenants.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8091';
const TYPES = ['wire', 'ach', 'card', 'crypto'];
const COUNTRIES = ['US', 'GB', 'DE', 'PH', 'SG', 'AE', 'IR'];

export const options = {
  scenarios: {
    c5: { executor: 'constant-vus', vus: 5, duration: __ENV.STAGE || '60s', tags: { stage: 'c5' } },
    c50: { executor: 'constant-vus', vus: 50, duration: __ENV.STAGE || '60s', startTime: __ENV.GAP || '65s',
           tags: { stage: 'c50' } },
  },
  thresholds: {
    'http_req_failed{stage:c5}': ['rate<0.01'],
    'http_req_failed{stage:c50}': ['rate<0.01'],
    'http_req_duration{stage:c5}': ['p(95)<1000'],
    'http_req_duration{stage:c50}': ['p(95)<2000'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  const email = `load-${Date.now()}@loadtest.invalid`;
  const reg = http.post(`${BASE}/api/auth/register`, JSON.stringify({
    email, password: 'LoadTest-Passw0rd!', first_name: 'Load', last_name: 'Test', company: 'loadtest',
  }), { headers: { 'Content-Type': 'application/json' } });
  check(reg, { registered: (r) => r.status === 201 });
  const token = reg.json('access_token');
  const key = http.post(`${BASE}/api/v1/keys`, JSON.stringify({ name: 'loadtest' }), {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  });
  // Plenty of credits so the run measures screening, not the credit limit (simulated payments).
  for (let i = 0; i < 10; i++) {
    http.post(`${BASE}/api/v1/credits/checkout`, JSON.stringify({ credits: 200000 }), {
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    });
  }
  return { key: key.json('key') };
}

export default function (data) {
  const body = {
    amount: Math.round(Math.random() * 90000 * 100) / 100 + 10,
    currency: 'USD',
    transaction_type: TYPES[Math.floor(Math.random() * TYPES.length)],
    sender_name: `Sender ${Math.floor(Math.random() * 500)}`,
    receiver_name: `Receiver ${Math.floor(Math.random() * 500)}`,
    account_id: `acct-${Math.floor(Math.random() * 200)}`,
    destination_country: COUNTRIES[Math.floor(Math.random() * COUNTRIES.length)],
    idempotency_key: `${__VU}-${__ITER}-${Date.now()}`,
  };
  const r = http.post(`${BASE}/api/v1/transactions`, JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.key}` },
  });
  check(r, { screened: (res) => res.status === 200 && res.json('data.status') !== undefined });
}
