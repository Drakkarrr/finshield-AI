// FinShield AI - k6 Load Tests
// Tests p95 latency at 1x and 10x load with regression gates

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const transactionDuration = new Trend('transaction_duration', true);

// Test configuration
export const options = {
  scenarios: {
    // 1x load: Normal operation
    normal_load: {
      executor: 'constant-vus',
      vus: 10,
      duration: '5m',
      exec: 'normalLoad',
      tags: { load_type: '1x' },
    },
    // 10x load: Stress test
    stress_test: {
      executor: 'constant-vus',
      vus: 100,
      duration: '5m',
      startTime: '6m', // Start after normal load
      exec: 'stressTest',
      tags: { load_type: '10x' },
    },
  },
  thresholds: {
    // p95 latency thresholds
    'http_req_duration{load_type:1x}': ['p(95)<500'], // <500ms at 1x
    'http_req_duration{load_type:10x}': ['p(95)<2000'], // <2s at 10x
    'transaction_duration{load_type:1x}': ['p(95)<400'], // Transaction screening <400ms
    'transaction_duration{load_type:10x}': ['p(95)<1500'], // <1.5s under stress
    // Error rate thresholds
    'errors': ['rate<0.01'], // <1% errors
    'http_req_failed': ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8091';
const API_KEY = __ENV.API_KEY || 'test-api-key';

const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${API_KEY}`,
};

// Helper: Generate random transaction data
function randomTransaction() {
  const currencies = ['USD', 'EUR', 'GBP', 'PHP', 'SGD'];
  const types = ['wire', 'ach', 'international', 'crypto', 'p2p'];
  
  return {
    sender_name: `Sender ${Math.random().toString(36).substring(7)}`,
    receiver_name: `Receiver ${Math.random().toString(36).substring(7)}`,
    amount: Math.floor(Math.random() * 100000) + 100,
    currency: currencies[Math.floor(Math.random() * currencies.length)],
    transaction_type: types[Math.floor(Math.random() * types.length)],
    destination_country: ['US', 'GB', 'PH', 'SG', 'JP'][Math.floor(Math.random() * 5)],
  };
}

// Normal load scenario (1x)
export function normalLoad() {
  // Health check
  const healthRes = http.get(`${BASE_URL}/api/health`, { tags: { name: 'health' } });
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);
  
  sleep(1);
  
  // Screen transaction
  const txPayload = JSON.stringify(randomTransaction());
  const txRes = http.post(`${BASE_URL}/api/v1/transactions`, txPayload, {
    headers,
    tags: { name: 'screen_transaction' },
  });
  
  transactionDuration.add(txRes.timings.duration, { load_type: '1x' });
  
  check(txRes, {
    'transaction status is 200': (r) => r.status === 200,
    'transaction has result': (r) => r.json('data') !== undefined,
  }) || errorRate.add(1);
  
  sleep(2);
  
  // Get stats
  const statsRes = http.get(`${BASE_URL}/api/v1/stats`, {
    headers,
    tags: { name: 'get_stats' },
  });
  
  check(statsRes, {
    'stats status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);
  
  sleep(1);
}

// Stress test scenario (10x)
export function stressTest() {
  // Rapid transaction screening
  const txPayload = JSON.stringify(randomTransaction());
  const txRes = http.post(`${BASE_URL}/api/v1/transactions`, txPayload, {
    headers,
    tags: { name: 'screen_transaction_stress' },
  });
  
  transactionDuration.add(txRes.timings.duration, { load_type: '10x' });
  
  check(txRes, {
    'transaction status is 200 or 429': (r) => r.status === 200 || r.status === 429,
    'transaction has result or rate limit': (r) => {
      if (r.status === 200) return r.json('data') !== undefined;
      if (r.status === 429) return r.headers['Retry-After'] !== undefined;
      return false;
    },
  }) || errorRate.add(1);
  
  // Occasional health check
  if (Math.random() < 0.1) {
    const healthRes = http.get(`${BASE_URL}/api/health`, { tags: { name: 'health_stress' } });
    check(healthRes, {
      'health status is 200 under stress': (r) => r.status === 200,
    });
  }
  
  sleep(0.5);
}

// Setup: Authenticate and get API key
export function setup() {
  const res = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify({
    email: 'test@example.com',
    password: 'test-password',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  if (res.status === 200) {
    return { token: res.json('access_token') };
  }
  
  return { token: null };
}

// Teardown: Cleanup
export function teardown(data) {
  console.log('Load test completed');
  console.log(`Normal load (1x): ${options.scenarios.normal_load.vus} VUs`);
  console.log(`Stress test (10x): ${options.scenarios.stress_test.vus} VUs`);
}
