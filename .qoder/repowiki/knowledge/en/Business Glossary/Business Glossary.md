---
kind: business_term
name: Business Glossary
category: business_term
scope:
    - '**'
---

### FinShield AI
- Definition：Internal product name for the full-lifecycle financial transaction compliance engine covering screening (hard rules, behavioral monitoring, ML classifier), case management, and SAR/STR regulatory filing. All inference runs on customer-controlled infrastructure; no transaction data leaves the boundary.
- Aliases：FinShield、FinShield-AI

### SAR/STR filing
- Definition：Regulatory filing workflow for Suspicious Activity Reports (SAR) and Suspicious Transaction Reports (STR). Includes draft generation, narrative assistance, deadline tracking, and safe-harbor logging within the case lifecycle.
- Aliases：SAR filing、STR filing、regulatory filing

### Gating logic
- Definition：Decision reconciler that combines signals from the hard rule engine, behavioral monitor, RAG+classifier, and independent risk scorer; forces human review on disagreement or low confidence rather than auto-resolving.
- Aliases：gate、gating

### Behavioral monitoring
- Definition：Per-account anomaly detection running against 100% of transactions using statistical scoring (z-score / isolation forest); includes cold-start handling for new accounts and acts as a trigger gate before RAG+ML paths.
- Aliases：behavioral monitor、behavioral scoring

### Hard rule engine
- Definition：Deterministic, no-code compliance rules (sanctions blocks, country restrictions, amount thresholds) authored from the admin UI and evaluated before ML paths; decisions are priority-ordered and auditable.
- Aliases：rules engine、hard rules

### LoRA fine-tuned classifier
- Definition：DSPy-compiled, Pydantic-validated model producing compliance decisions (approve/flag/block) via LoRA adapters served through vLLM; decoupled from the independent risk scorer to avoid correlated blind spots.
- Aliases：classifier、LoRA adapter、ML classifier

### Circuit breaker
- Definition：Resilience pattern that degrades gracefully when downstream dependencies fail — routing to manual human review instead of silently auto-approving transactions.
- Aliases：circuit-breaker、degraded mode

### DSAR
- Definition：Data Subject Access Request — GDPR/CCPA privacy workflow endpoint (`/api/v1/privacy/dsar`) for handling erasure and access requests against stored transaction/case data.
- Aliases：data subject access request、right-to-erasure

### Multi-tenant isolation
- Definition：Tenant separation strategy using distinct PostgreSQL schemas per tenant to achieve regulatory-grade data isolation across customers sharing the same instance.
- Aliases：schema-per-tenant、tenant isolation

### Shadow mode
- Definition：Model lifecycle state where a candidate LoRA adapter runs alongside the active model without affecting live decisions, used for drift detection and evaluation before promotion.
- Aliases：shadow testing、model shadowing
