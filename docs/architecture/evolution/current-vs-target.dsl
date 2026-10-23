workspace "FinShield AI" "Current vs target architecture. Produced by architecture-visualization:evolution-planner + c4model. Evidence in ../evidence.md." {

    model {
        analyst = person "Compliance Analyst" "Screens flagged transactions, works cases, files SAR/STR"
        integrator = person "Integrating Engineer" "Submits transactions via API key, consumes webhooks"
        regulator = person "Regulator (FinCEN)" "Receives SAR/STR filings — currently manual export only"

        finshield = softwareSystem "FinShield AI" "Local-first transaction compliance engine" {

            # ---------- CURRENT (evidence-backed) ----------
            webapp = container "Platform Web App" "Next.js 14 App Router. 11 routes; 8 backed by real CRUD. No middleware.ts, no route protection, no RBAC, no data-fetching library" "TypeScript / React 18 / Tailwind 3" {
                tags "Current"
            }
            marketing = container "Marketing Site" "Static nginx site. website/platform/*.html legacy console is dead code (zero fetch calls)" "HTML / BEM CSS" {
                tags "Current" "Deprecated"
            }
            api = container "Screening API" "FastAPI, 68 routes, 2855-line main.py. JWT + API-key auth applied on 64/68 routes. All handlers async def with blocking sync SQLAlchemy" "Python 3.11" {
                tags "Current"
                engine = component "Compliance Engine" "7-stage screen(). Rules are 4 hardcoded checks over 3-entry sanctions/PEP Python sets. Behavioral stage and _ml_classify return random.uniform. Only the precedence gate is real" "compliance_engine.py" {
                    tags "Current" "Stub"
                }
                behavioral = component "Z-score Behavioral Monitor" "Real per-account z-score + cold-start thresholds + account_baselines recompute. NEVER called by screen() — reachable only via POST /api/v1/behavioral/score. Crashes on update-baseline (function-local import math used at main.py:2274)" "main.py:2170-2328" {
                    tags "Current" "DeadCode"
                }
                rag = component "pgvector RAG Retrieval" "Real cosine-distance SQL against Postgres. Embeddings are MD5 feature-hashing stand-in (sentence-transformers not in requirements). Gated on RAG_DATABASE_URL: enabled in compose, disabled in local .env. When on, it can flip approved -> flagged only" "rag_service.py" {
                    tags "Current" "DeadCode"
                }
                breakers = component "Circuit Breaker State" "Three-state machine persisted in DB, but transitions are driven only by client HTTP POSTs. Wraps no actual call" "main.py:2381-2546" {
                    tags "Current" "DeadCode"
                }
                webhooks = component "Webhook Event Rows" "dispatch inserts status=pending and returns. No HTTP client, no retry executor, no DLQ transition" "main.py:2589-2667" {
                    tags "Current" "Stub"
                }
                health = component "Health Endpoint" "Returns a hardcoded map where behavioral_ml, rag_classifier and database are statically healthy. Probes nothing" "main.py:2830-2845" {
                    tags "Current" "Stub"
                }
            }
            sqlitedb = container "Primary Database" "SQLite by default (finshield.db) via create_all. 14 tables. No Alembic, no migrations, no tenant_id, no role column" "SQLite / SQLAlchemy 2.0" {
                tags "Current"
            }
            pg = container "pgvector Postgres" "Runs in compose but is used ONLY as the RAG store. Not the primary DB" "PostgreSQL 16 + pgvector" {
                tags "Current"
            }

            # ---------- TARGET (proposed — no code evidence) ----------
            worker = container "Async Worker" "Webhook delivery with exponential backoff + DLQ, baseline recomputation jobs, SLA escalation sweep, filing deadline reminders, async screening for bulk ingest" "Celery + Redis (proposed)" {
                tags "Target"
            }
            mlsvc = container "Scoring Service" "Deterministic, explainable risk model (gradient-boosted) behind a versioned Model interface, with shadow mode and drift checks. Replaces random.uniform" "Python / scikit-learn (proposed)" {
                tags "Target"
            }
            embeddings = container "Embedding Service" "Real sentence embeddings (all-MiniLM-L6-v2, CPU) so RAG retrieval is semantic rather than lexical" "sentence-transformers (proposed)" {
                tags "Target"
            }
            listdata = container "Sanctions / PEP Data Store" "DB-backed OFAC SDN + PEP lists with an import job and fuzzy matching, replacing the 3-element Python sets" "Postgres tables + loader (proposed)" {
                tags "Target"
            }
            observability = container "Observability Stack" "OpenTelemetry traces, Prometheus /metrics, structured JSON logs, Sentry, real dependency health probes" "OTel + Prometheus (proposed)" {
                tags "Target"
            }
            migrations = container "Migration Framework" "Alembic versioned migrations; Postgres as the primary database; SQLite retained for tests only" "Alembic (proposed)" {
                tags "Target"
            }
            tenancy = container "Tenancy & RBAC" "tenant_id on every owned row + Postgres RLS; role column with require_role dependencies; per-tenant config and feature flags" "Postgres RLS (proposed)" {
                tags "Target"
            }
            audit = container "Immutable Audit Trail" "Append-only enforcement, hash chaining, read API and chain-of-custody export. Screening decisions become audited events" "Postgres triggers (proposed)" {
                tags "Target"
            }
            privacy = container "Privacy / DSAR Service" "Real DSAR entity and workflow, right-to-erasure, field-level PII masking" "proposed" {
                tags "Target"
            }
            payments = container "Payment Provider" "Stripe Checkout. Removes plaintext card columns from the users table" "proposed" {
                tags "Target"
            }
            designsystem = container "Design System" "DESIGN.md + tokens, Radix-based primitives (Button/Input/Card/Table/Badge/Modal), focus management, AA contrast, SWR data layer, pagination, SSE or WebSocket for live updates" "proposed" {
                tags "Target"
            }
        }

        analyst -> webapp "works cases, files SAR/STR" "HTTPS"
        integrator -> api "POST /api/v1/transactions" "HTTPS + API key"
        integrator -> webhooks "subscribes to events (target)" "HTTPS"
        webapp -> api "calls ~24 endpoints via /api rewrite" "HTTP JSON"
        api -> engine "screen()" "in-process"
        engine -> sqlitedb "reads/writes transactions, cases, filings, rules" "SQL"
        engine -> behavioral "TARGET: consult per-account baseline" "in-process"
        engine -> rag "enrich decision (currently gated off in local dev)" "in-process"
        rag -> pg "cosine_distance search" "SQL"
        rag -> embeddings "TARGET: semantic vectors" "in-process"
        engine -> mlsvc "TARGET: deterministic risk score" "in-process"
        engine -> listdata "TARGET: sanctions/PEP lookup" "SQL"
        api -> audit "TARGET: append-only decision log" "SQL"
        api -> worker "TARGET: enqueue webhook delivery, baseline jobs, SLA sweeps" "Redis"
        worker -> observability "TARGET: emits traces/metrics" "OTLP"
        api -> observability "TARGET: traces, /metrics, JSON logs" "OTLP"
        api -> payments "TARGET: checkout sessions" "HTTPS"
        api -> privacy "TARGET: DSAR + erasure" "in-process"
        migrations -> pg "TARGET: primary store, versioned schema" "SQL"
        tenancy -> pg "TARGET: RLS policies" "SQL"
        webapp -> designsystem "TARGET: primitives + tokens" "in-process"
        regulator -> audit "TARGET: chain-of-custody export" "file"

        # Deployment model
        prod = deploymentEnvironment "Production (proposed)" {
            deploymentNode "Container host / Kubernetes" "" "" "proposed" {
                infrastructure "TLS terminator + security headers" "" "" "HSTS, CSP, Referrer-Policy" {
                    tags "Target"
                }
            }
        }
    }

    views {
        systemContext finshield "L1-context" "Who uses FinShield and what is proposed but not built" {
            include *
            autoLayout tb
        }

        container finshield "L2-current-vs-target" "Current deployables (solid) vs proposed additions (dashed)" {
            include *
            autoLayout tb
        }

        component api "L3-detection-pipeline" "Inside the Screening API: what is real, what is dead code, what is a stub" {
            include *
            autoLayout tb
        }

        theme default

        styles {
            element "Person" {
                shape person
                background #1168bd
                color #ffffff
            }
            element "Current" {
                background #1e6f5c
                color #ffffff
            }
            element "Target" {
                background #7a5195
                color #ffffff
                border dashed
            }
            element "Stub" {
                background #b0632a
                color #ffffff
            }
            element "DeadCode" {
                background #8a6d1f
                color #ffffff
                border dashed
            }
            element "Deprecated" {
                background #6b6b6b
                color #ffffff
                border dashed
            }
        }
    }
}
