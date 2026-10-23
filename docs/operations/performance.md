# Screening performance

**Status: measured on 2026-10-23 with [loadtest/screening.js](../../loadtest/screening.js) (k6 0.54.0). Slice S6.5.**

The test screens random transactions through `POST /api/v1/transactions` with an API key. It runs
60 s at 5 concurrent clients, then 60 s at 50 (10×). The backend is the production image with the
real OFAC SDN list (19,471 entries, 20,192 aliases) and MiniLM RAG, on Postgres 16 + pgvector. It ran
on a developer machine (10 CPUs, 8 GB shared by Docker, k6, Postgres and the running stack), so
absolute numbers are indicative only. Thresholds in the script: p95 < 1 s at 5 clients and < 2 s at 50.
Failed requests: 0% in every run.

## Results

| Run | Backend | Throughput | p95 at 5 clients | p95 at 50 clients |
|---|---|---|---|---|
| Baseline | 1 process, 2 CPUs | 2.2 req/s | 2.36 s ✗ | 31.7 s ✗ |
| + torch 1 thread, cached embeddings, vectorised list matching | 1 process, 2 CPUs | 3.8 req/s | 1.48 s ✗ | 20.5 s ✗ |
| + API-key lookup by SHA-256 digest (no bcrypt per request) | 1 process, 2 CPUs | 10.8 req/s | 0.86 s ✓ | 5.96 s ✗ |
| Same code | 2 workers, 2 CPUs | 13.7 req/s | 0.56 s ✓ | 9.51 s ✗ |
| Same code | 4 workers, 4 CPUs | 15.8 req/s | 0.52 s ✓ | 7.67 s ✗ |

## What the profiles showed

These come from py-spy, sampling the live process under load.

1. **API-key authentication: 79% of CPU.** Every request ran bcrypt to check its API key
   (~250 ms of CPU each). API keys are 256-bit random values, so they are now looked up by an indexed
   SHA-256 digest (migration 0011). Keys created earlier are verified with bcrypt once, then get a digest.
2. **MiniLM: about 60% of screening CPU.** Torch defaulted to one thread per *host* core inside a
   2-CPU container, while several request threads encoded at once, so the CPUs were oversubscribed.
   Torch now uses `TORCH_NUM_THREADS` (default 1), and query texts are embedded one per call with a
   bounded cache. Vectors are identical, and the eval harness shows no regression on 20 metrics.
3. **Sanctions fuzzy matching: about 40% after fix 2.** Four full scans of the list per transaction were
   replaced by one vectorised `rapidfuzz.process.cdist` pass per name, cached per list snapshot.
   Results are identical: 800 queries against the real OFAC list gave 0 mismatches. Uncached cost
   fell from 20.7 to 12.7 ms per name.

## Capacity and the 10× question

After these fixes one screening costs about 0.14 CPU-seconds. At 50 concurrent clients the CPUs are
saturated (`docker stats`: 200% of 2 CPUs), so latency is queueing (Little's law: 50 / 14 req/s ≈ 3.6 s).
Doubling cores and workers gave sub-linear gains on this shared host.

**The S6.5 target, a p95 that holds at 10× concurrency, is NOT met on a single small instance.**
It needs horizontal scaling sized to the peak rate, about 1 CPU per 7 screenings/s at p95 < 1 s, or
admission control. This has not been tested on a dedicated multi-instance deployment.

## Reproduce

Run this against a stack you own (it registers a throwaway tenant):

```bash
docker run --rm -i --network finshield_finshield-network -e BASE_URL=http://backend:8091 \
  -v "$PWD/loadtest:/scripts:ro" grafana/k6:0.54.0 run /scripts/screening.js
```

Screening is rate-limited per credential (`SCREENING_RATE_LIMIT`, default `60/minute`). Raise it on the
target, or the run measures 429 responses instead of screening.
