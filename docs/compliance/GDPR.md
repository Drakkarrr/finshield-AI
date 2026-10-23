# FinShield AI — GDPR Compliance

General Data Protection Regulation (GDPR) compliance documentation.

## Data Controller and Processor

- **Data Controller**: FinShield AI (for customer account data)
- **Data Processor**: FinShield AI (for transaction data processed on behalf of customers)
- **Customer**: Data Controller for end-user transaction data

## Data Processing Activities

### Personal Data Collected

| Data Category | Fields | Purpose | Legal Basis |
|---------------|--------|---------|-------------|
| Account data | email, first_name, last_name, company | User authentication, communication | Contract performance |
| Transaction data | sender_name, receiver_name, amount, destination_country | AML/CFT screening | Legal obligation (AML laws) |
| Technical data | IP address, user agent, timestamps | Security, fraud prevention | Legitimate interest |
| Behavioral data | transaction patterns, risk scores | Anomaly detection | Legitimate interest |

### Data Retention

| Data Type | Retention Period | Justification |
|-----------|------------------|---------------|
| Account data | Duration of account + 2 years | Contract, legal claims |
| Transaction data | 7 years | AML/CFT regulatory requirement |
| Audit logs | 7 years | Regulatory requirement, security |
| Behavioral baselines | 2 years | Anomaly detection accuracy |
| Cookies | 1 year | Session management |

**Evidence**: `docs/operations/RETENTION_MATRIX.md`

## Data Subject Rights

### 1. Right to Access (Article 15)

**Implementation**: Automated DSAR endpoint
- Endpoint: `GET /api/v1/privacy/access`
- Response: Complete user data export (JSON/CSV)
- Processing time: <72 hours
- Evidence: `backend/app/api/privacy.py`, `tests/test_privacy.py`

### 2. Right to Rectification (Article 16)

**Implementation**: User profile update
- Endpoint: `PUT /api/v1/users/me`
- Users can update: first_name, last_name, company, timezone
- Transaction data cannot be modified (regulatory requirement)
- Evidence: `backend/app/api/auth.py`

### 3. Right to Erasure (Article 17)

**Implementation**: Automated erasure with retention preservation
- Endpoint: `DELETE /api/v1/privacy/erasure`
- Erased: Account data, preferences, notifications
- Retained: Transaction data (7-year AML requirement), audit logs
- Evidence: `backend/app/api/privacy.py`, `tests/test_privacy.py`

### 4. Right to Data Portability (Article 20)

**Implementation**: Automated data export
- Endpoint: `GET /api/v1/transactions/export?format=csv`
- Formats: JSON, CSV
- Includes: All transaction data, screening results
- Evidence: `backend/app/api/transactions.py`

### 5. Right to Restrict Processing (Article 18)

**Implementation**: Account suspension
- Endpoint: `POST /api/v1/users/me/suspend`
- Effect: No new transactions processed, data retained
- Evidence: `backend/app/api/auth.py`

### 6. Right to Object (Article 21)

**Implementation**: Marketing opt-out
- Endpoint: `PUT /api/v1/notifications/preferences`
- Users can opt out of: email notifications, marketing communications
- Evidence: `backend/app/api/notifications.py`

## Data Protection by Design

### 1. Pseudonymization

- Audit logs mask PII: email → `u***@example.com`, names → `J*** D***`
- Transaction data encrypted at rest (PostgreSQL TDE)
- API keys hashed (bcrypt), never stored in plaintext

**Evidence**: `backend/app/api/audit.py:mask_pii()`, `backend/app/auth.py:hash_password()`

### 2. Encryption

- **In transit**: TLS 1.2+ enforced, HSTS headers
- **At rest**: PostgreSQL TDE, AES-256
- **Backups**: Encrypted with customer-managed keys

**Evidence**: `deploy/nginx.conf`, `scripts/backup.sh`

### 3. Access Control

- Role-based access control (RBAC): user/analyst/admin/super_admin
- Multi-tenancy with row-level security (RLS)
- API key authentication with scope restrictions

**Evidence**: `backend/app/auth.py:require_role()`, `backend/app/domain/tenancy.py`

### 4. Audit Trail

- Immutable append-only audit logs
- SHA-256 hash chain for tamper detection
- All data access logged (who, what, when)

**Evidence**: `backend/app/db_models.py:AuditLog`, `backend/app/api/audit.py`

## Data Breach Notification

### Notification Process

1. **Detection**: Automated alerts for suspicious activity
2. **Assessment**: Security team evaluates breach severity within 24 hours
3. **Notification**: 
   - Supervisory authority: Within 72 hours (if required)
   - Data subjects: Without undue delay (if high risk)
   - Customer: Within 48 hours

### Contact

- **Data Protection Officer**: dpo@finshield.ai
- **Security team**: security@finshield.ai
- **Emergency contact**: +1-555-FINSHIELD (24/7)

## International Data Transfers

### Data Residency

- Primary data center: US-East (AWS)
- Backup location: EU-West (AWS)
- Processing: All data processing occurs in data center region

### Transfer Mechanisms

- **EU-US Data Privacy Framework**: FinShield AI is certified
- **Standard Contractual Clauses (SCCs)**: Available upon request
- **Adequacy decisions**: For transfers to adequate jurisdictions

## Data Protection Impact Assessment (DPIA)

### When DPIA is Required

- New data processing activities
- Changes to existing processing
- High-risk processing (e.g., behavioral profiling)

### DPIA Process

1. **Screening**: Determine if DPIA is required
2. **Assessment**: Evaluate necessity, proportionality, risks
3. **Mitigation**: Identify measures to reduce risk
4. **Sign-off**: DPO and legal counsel approval
5. **Review**: Annual review or when processing changes

**Evidence**: DPIA reports stored securely, available upon request.

## Customer Responsibilities

As a data processor, FinShield AI requires customers to:

1. **Obtain consent**: Ensure end users have consented to data processing
2. **Privacy notice**: Provide privacy notice to end users
3. **Data minimization**: Only submit necessary transaction data
4. **Breach cooperation**: Notify FinShield AI of any customer-side breaches

## Sub-Processors

| Sub-Processor | Service | Location | Purpose |
|---------------|---------|----------|---------|
| AWS | Cloud hosting | US, EU | Data storage and processing |
| Stripe | Payment processing | US | Credit card processing |
| SendGrid | Email delivery | US | Transactional emails |
| Sentry | Error tracking | US | Application monitoring |

**Updated**: 2026-10-24  
**Notification**: Customers notified 30 days before adding new sub-processors

## Compliance Contacts

- **Data Protection Officer**: dpo@finshield.ai
- **Privacy team**: privacy@finshield.ai
- **Legal counsel**: legal@finshield.ai

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-10-24 | 1.0 | Initial GDPR documentation | DPO |
