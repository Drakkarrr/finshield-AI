# FinShield AI — AML/CFT Compliance

Anti-Money Laundering (AML) and Counter-Financing of Terrorism (CFT) compliance documentation.

## Regulatory Framework

FinShield AI is designed to support compliance with:
- **Bank Secrecy Act (BSA)** — US AML/CFT regulations
- **USA PATRIOT Act** — Enhanced due diligence requirements
- **EU 4th/5th/6th AML Directives** — European AML/CFT framework
- **FATF Recommendations** — International AML/CFT standards

## Compliance Program Elements

### 1. Transaction Monitoring

**Automated controls**:
- 7-stage compliance pipeline (idempotency → validation → rules → behavioral → ML → scoring → decision)
- Rule-based screening (OFAC sanctions, PEP, geographic risk, transaction thresholds)
- Behavioral anomaly detection (30-day baseline, z-score analysis)
- ML classification (neural network for high-risk transactions)

**Evidence**: `backend/app/compliance_engine.py`, `tests/test_compliance.py`

### 2. Sanctions Screening

**Automated controls**:
- OFAC SDN list matching with fuzzy matching (difflib, confidence scoring)
- Weekly automated list refresh
- PEP list screening
- Hit provenance tracking (source, match type, confidence)

**Evidence**: `backend/app/domain/lists.py`, `backend/app/db_models.py:SanctionsEntry`

### 3. Risk Scoring

**Automated controls**:
- Deterministic explainable scoring (no randomness)
- Rule weights configurable per customer
- Risk bands (low/medium/high/critical)
- Decision logic: approved/flagged/blocked/in_review

**Evidence**: `backend/app/compliance_engine.py:_compute_risk()`

### 4. Case Management

**Automated controls**:
- Automatic case creation for flagged transactions
- Case assignment and status tracking
- Priority levels (critical/high/medium/low)
- Audit trail for all case actions

**Evidence**: `backend/app/api/cases.py`, `tests/test_cases.py`

### 5. Filing Generation

**Semi-automated controls**:
- SAR (Suspicious Activity Report) template generation
- CTR (Currency Transaction Report) automatic filing for >$10,000
- Narrative generation from case data
- Human review required before submission

**Evidence**: `backend/app/api/filings.py`, `docs/compliance/FILING_PROCEDURES.md`

### 6. Record Keeping

**Automated controls**:
- 7-year retention for all transactions and decisions
- Immutable audit trail with hash chain
- Automated backup with checksum verification
- Data export capabilities for regulatory examinations

**Evidence**: `docs/operations/RETENTION_MATRIX.md`, `scripts/backup.sh`

## Independent Testing

### Internal Testing

- **Quarterly**: Labeled scenario testing (precision/recall/FPR metrics)
- **Semi-annually**: Penetration testing by third-party firm
- **Annually**: Full compliance audit

### External Testing

- **Annual**: Independent audit by certified compliance firm
- **Ad hoc**: Regulatory examinations (OCC, FinCEN, etc.)

**Evidence**: Audit reports stored securely, available upon request.

## Known Limitations

See `docs/compliance/LIMITATIONS.md` for detailed disclosure of:
- False positive/negative rates
- Sanctions list update frequency
- Behavioral analysis accuracy
- ML model limitations

## Customer Responsibilities

FinShield AI supports but does not replace customer compliance programs:

1. **KYC/CDD**: Customer must perform Know Your Customer / Customer Due Diligence at onboarding
2. **Filing submission**: Customer must review and submit SARs/CTRs to regulators
3. **Legal review**: Customer must consult legal counsel for jurisdiction-specific requirements
4. **Monitoring**: Customer must monitor system alerts and investigate flagged transactions

## Compliance Contacts

- **Compliance Officer**: compliance@finshield.ai
- **Data Protection Officer**: dpo@finshield.ai
- **Legal Counsel**: legal@finshield.ai

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-10-24 | 1.0 | Initial AML/CFT documentation | Compliance Team |
