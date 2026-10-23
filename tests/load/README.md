# FinShield AI - Load Tests

Performance and load testing suite using k6.

## Overview

Load tests validate system performance under normal (1x) and stress (10x) conditions, ensuring p95 latency thresholds are met.

### Test Scenarios

1. **Normal Load (1x)**: 10 virtual users for 5 minutes
   - Simulates typical production traffic
   - p95 latency threshold: <500ms

2. **Stress Test (10x)**: 100 virtual users for 5 minutes
   - Simulates peak load / traffic spikes
   - p95 latency threshold: <2000ms

### Metrics Tracked

- HTTP request duration (avg, p95, max)
- Transaction screening latency
- Error rate (<1% threshold)
- Request throughput (req/s)

## Prerequisites

- [k6](https://k6.io/docs/getting-started/installation/) installed
- Access to test environment
- API key with sufficient credits

## Installation

```bash
# macOS
brew install k6

# Linux (Ubuntu/Debian)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Windows
choco install k6
```

## Running Tests

### Local Testing

```bash
# Set environment variables
export BASE_URL=http://localhost:8091
export API_KEY=your-test-api-key

# Run full test suite (normal + stress)
k6 run tests/load/k6-load-test.js

# Run only normal load scenario
k6 run --scenario normal_load tests/load/k6-load-test.js

# Run only stress test scenario
k6 run --scenario stress_test tests/load/k6-load-test.js
```

### With Custom Thresholds

```bash
k6 run \
  --vus 50 \
  --duration 10m \
  --thresholds 'http_req_duration:p(95)<1000' \
  tests/load/k6-load-test.js
```

### Output to JSON

```bash
k6 run \
  --out json=results.json \
  --summary-export=summary.json \
  tests/load/k6-load-test.js
```

## CI/CD Integration

### GitHub Actions

Load tests run automatically:
- **Nightly**: Every day at 2 AM UTC
- **Manual**: Via workflow_dispatch

Results are uploaded as artifacts and compared against previous runs to detect performance regressions.

### Thresholds

The following thresholds are enforced:

| Metric | 1x Load | 10x Load |
|--------|---------|----------|
| HTTP p95 | <500ms | <2000ms |
| Transaction p95 | <400ms | <1500ms |
| Error rate | <1% | <1% |

### Regression Detection

Performance regression is flagged if:
- p95 latency increases by >20% compared to previous run
- Error rate exceeds 1%
- Any threshold fails

## Test Structure

```
tests/load/
├── k6-load-test.js          # Main test script
├── README.md                 # This file
└── results/                  # Test results (gitignored)
    ├── summary.json
    └── results.json
```

## Customization

### Adding New Endpoints

Edit `k6-load-test.js` and add new HTTP requests:

```javascript
const customRes = http.get(`${BASE_URL}/api/v1/custom`, {
  headers,
  tags: { name: 'custom_endpoint' },
});

check(customRes, {
  'custom status is 200': (r) => r.status === 200,
});
```

### Adjusting Load Profiles

Modify the `options` object in `k6-load-test.js`:

```javascript
export const options = {
  scenarios: {
    normal_load: {
      executor: 'constant-vus',
      vus: 20,        // Increase VUs
      duration: '10m', // Longer duration
    },
  },
};
```

### Using Different Executors

k6 supports various executors:

```javascript
// Ramp up load gradually
scenarios: {
  ramp_up: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '2m', target: 20 },
      { duration: '5m', target: 20 },
      { duration: '2m', target: 0 },
    ],
  },
}
```

## Monitoring During Tests

### Real-time Output

```bash
k6 run --out cloud tests/load/k6-load-test.js
```

### Grafana Dashboard

```bash
# Start Grafana + InfluxDB
docker-compose -f tests/load/docker-compose.monitoring.yml up -d

# Run k6 with InfluxDB output
k6 run --out influxdb=http://localhost:8086/k6 tests/load/k6-load-test.js
```

## Troubleshooting

### Connection Refused

Ensure the backend is running and accessible:

```bash
curl $BASE_URL/api/health
```

### Authentication Errors

Verify API key is valid and has sufficient credits:

```bash
curl -H "Authorization: Bearer $API_KEY" $BASE_URL/api/v1/credits
```

### Timeouts

Increase timeout in test script:

```javascript
const res = http.get(url, {
  timeout: '30s', // Increase from default 10s
});
```

## Performance Baselines

As of 2026-10-24:

| Metric | Value | Environment |
|--------|-------|-------------|
| HTTP p95 (1x) | 120ms | Staging |
| HTTP p95 (10x) | 850ms | Staging |
| Transaction p95 | 320ms | Staging |
| Error rate | 0.02% | Staging |
| Throughput | 45 req/s | Staging |

## Resources

- [k6 Documentation](https://k6.io/docs/)
- [k6 HTTP API](https://k6.io/docs/using-k6/http-requests/)
- [Performance Testing Guide](https://k6.io/docs/test-types/load-testing/)
