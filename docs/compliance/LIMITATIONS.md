# FinShield AI — System Limitations

Honest disclosure of FinShield AI's current limitations, known gaps, and areas where human judgment is required.

## Purpose

This document provides transparent disclosure of system limitations to:
1. Set accurate expectations for customers and auditors
2. Guide proper use of the system
3. Identify areas requiring human oversight
4. Drive continuous improvement

## Last Updated

2026-10-24

---

## Detection Limitations

### 1. False Positives and False Negatives

**Limitation**: No screening system is 100% accurate.

- **False positives**: Legitimate transactions flagged as suspicious (estimated rate: 2-5%)
- **False negatives**: Suspicious transactions approved (estimated rate: <0.1%, but non-zero)

**Mitigation**:
- All flagged transactions require human review before blocking
- Continuous model tuning based on analyst feedback
- Quarterly accuracy reviews with labeled test scenarios

**Customer action**: Do not rely solely on automated decisions for high-value or high-risk transactions.

---

### 2. Sanctions List Coverage

**Limitation**: Sanctions lists are updated periodically, not in real-time.

- OFAC SDN list refresh: Weekly (automated)
- PEP list refresh: Monthly (automated)
- Gap between list update and system availability: 24-72 hours

**Mitigation**:
- Automated list refresh jobs with audit logging
- Manual list updates available for critical situations
- Alerts when list refresh fails

**Customer action**: For time-sensitive screening against newly sanctioned entities, verify against official OFAC website.

---

### 3. Behavioral Analysis Accuracy

**Limitation**: Behavioral anomaly detection relies on historical patterns and may not detect novel fraud schemes.

- Requires minimum 30 days of transaction history for baseline
- Novel transaction types may trigger false positives
- Sophisticated fraud patterns may evade detection

**Mitigation**:
- Behavioral scoring is one signal among many (rules, sanctions, ML)
- Analyst review required for all behavioral flags
- Continuous model retraining with new data

**Customer action**: Combine behavioral alerts with other risk indicators.

---

### 4. Machine Learning Model Limitations

**Limitation**: ML classification is probabilistic and not infallible.

- Model accuracy: ~92% on labeled test set (8% error rate)
- Model drift: Performance may degrade over time as fraud patterns evolve
- Explainability: ML decisions are less interpretable than rule-based decisions

**Mitigation**:
- ML is used only in `full_ml` credit tier (highest-risk transactions)
- Shadow mode available for A/B testing new models
- Model versioning with rollback capability
- Human review required for all ML-flagged transactions

**Customer action**: Review ML confidence scores; low-confidence predictions should be escalated.

---

## Data Limitations

### 5. RAG Retrieval Quality

**Limitation**: RAG (Retrieval-Augmented Generation) context may be incomplete or irrelevant.

- Retrieval accuracy: ~85% (15% of retrieved context may be low-relevance)
- Embedding model limitations: Semantic similarity does not guarantee relevance
- Degraded mode: If pgvector is unavailable, RAG context is omitted

**Mitigation**:
- RAG context is supplementary, not determinative
- Circuit breaker prevents RAG failures from blocking screening
- Honest degraded signal in API responses (`rag_context: null`)

**Customer action**: Do not rely solely on RAG context for compliance decisions.

---

### 6. Transaction Data Completeness

**Limitation**: Screening accuracy depends on data quality provided by the customer.

- Missing fields (e.g., destination country) reduce screening effectiveness
- Inaccurate sender/receiver names reduce sanctions matching accuracy
- No validation of real-world identity (KYC not performed by FinShield)

**Mitigation**:
- Input validation ensures required fields are present
- Fuzzy matching compensates for minor name variations
- Clear API documentation with field requirements

**Customer action**: Ensure transaction data is complete and accurate. Implement KYC at onboarding.

---

## Operational Limitations

### 7. Rate Limiting

**Limitation**: API rate limits may impact high-volume customers.

- Default rate limit: 100 requests/minute per API key
- Burst limit: 20 requests/second
- Rate limit errors (HTTP 429) require client-side retry logic

**Mitigation**:
- Configurable rate limits per customer tier
- Exponential backoff retry logic in SDK
- Rate limit headers (`X-RateLimit-Remaining`) for client awareness

**Customer action**: Implement retry logic with exponential backoff. Contact sales for higher limits.

---

### 8. Availability and Uptime

**Limitation**: System is not 100% available.

- Target uptime: 99.9% (8.76 hours downtime/year allowed)
- Planned maintenance: 2-4 hours/month (with 48h notice)
- Unplanned outages: Possible due to infrastructure failures

**Mitigation**:
- Multi-AZ deployment for high availability
- Automated failover for database and cache
- Status page: status.finshield.ai
- Incident notifications via email and webhook

**Customer action**: Implement client-side retry logic. Cache results where appropriate.

---

### 9. Data Retention and Deletion

**Limitation**: Data deletion is not instantaneous.

- Erasure requests processed within 72 hours
- Backups retained for 7 years (regulatory requirement)
- Deleted data may persist in backups until backup rotation

**Mitigation**:
- Automated DSAR processing with audit logging
- Clear retention policy: `docs/operations/RETENTION_MATRIX.md`
- PII masking in audit logs reduces exposure

**Customer action**: Communicate 72-hour processing time to end users.

---

## Compliance Limitations

### 10. Regulatory Coverage

**Limitation**: FinShield AI is not a substitute for legal counsel or full compliance program.

- System supports AML/CFT compliance but does not guarantee regulatory approval
- Filing generation (SAR/CTR) requires human review and submission
- Jurisdiction-specific requirements may not be fully covered

**Mitigation**:
- System designed with regulatory best practices
- Regular review by compliance advisors
- Documentation of controls and limitations

**Customer action**: Consult legal counsel for jurisdiction-specific requirements. Retain qualified compliance officer.

---

### 11. Audit Trail Completeness

**Limitation**: Not all system actions are audited.

- Audited: API calls, data changes, authentication events
- Not audited: Internal system operations, background jobs, read-only queries

**Mitigation**:
- Comprehensive audit logging for all data-modifying operations
- Immutable audit trail with hash chain verification
- Audit logs retained for 7 years

**Customer action**: Supplement with application-level logging for custom workflows.

---

### 12. Multi-Tenancy Isolation

**Limitation**: Shared infrastructure introduces theoretical cross-tenant risk.

- PostgreSQL RLS enforced at database level
- Application-level tenant isolation in all queries
- No known cross-tenant data leakage incidents

**Mitigation**:
- Row-level security (RLS) policies on all tenant-scoped tables
- Automated tests verify cross-tenant isolation
- Penetration testing conducted annually

**Customer action**: For highly sensitive workloads, consider dedicated deployment.

---

## Known Issues

### Current Known Issues

| Issue ID | Description | Severity | Workaround | Target Fix |
|----------|-------------|----------|------------|------------|
| KI-001 | Behavioral baseline recomputation may timeout for users with >100k transactions | Low | Manual trigger with smaller batch | 2026-Q4 |
| KI-002 | RAG retrieval may return duplicate results in edge cases | Low | Deduplication in client code | 2027-Q1 |
| KI-003 | Webhook delivery retries may exceed 24h in case of prolonged subscriber outage | Medium | Monitor webhook health dashboard | 2026-Q4 |

### Reporting New Issues

If you discover a limitation not documented here:
- Email: support@finshield.ai
- Include: Description, impact, reproduction steps
- Response time: 2 business days

---

## Continuous Improvement

### Limitation Review Process

- **Quarterly**: Review customer feedback, incident reports, and accuracy metrics
- **Semi-annually**: Update this document with new limitations or resolved issues
- **Annually**: Third-party audit of limitation disclosures

### Feedback

We welcome feedback on this document and system limitations:
- Email: compliance@finshield.ai
- Customer advisory board: Quarterly meetings

---

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-10-24 | 1.0 | Initial limitations disclosure | Compliance Team |
