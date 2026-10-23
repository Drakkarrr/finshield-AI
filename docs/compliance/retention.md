# Data retention matrix

**Status: IMPLEMENTED where marked "enforced"; everything else is procedural.** Slice S4.5.
Not legal advice. The periods below are the record-keeping floors most AML regimes set; confirm
them with counsel for each jurisdiction you operate in.

Retention here is a **floor, not a purge**: FinShield refuses to erase records still inside their
retention window, but it never deletes a record automatically when the window ends. Deleting
expired records is a procedural step (below) until an automated purge is justified (rule R8).

| Data class | Table(s) | Minimum retention | Legal basis | How it is enforced |
|---|---|---|---|---|
| Screened transactions | `transactions` | 5 years from the transaction (`privacy.retention_years`, default 5) | US: 31 CFR 1010.430(d). PH: AMLA (RA 9160 as amended) s.9(b). EU: AMLD Art. 40. GDPR Art. 17(3)(b) exempts them from erasure. | **Enforced.** DSAR erasure retains them with `eligible_from` until the window ends ([privacy.py](../../backend/app/domain/privacy.py)). |
| Cases, case notes and comments | `cases`, `case_notes`, `case_comments` | 5 years from case closure | Supporting documentation of the monitoring programme (31 CFR 1020.320(d) when a SAR follows). | **Enforced** for the linked transaction: erasure retains it as "linked case/filing". Case rows are never erased. |
| Regulatory filings (SAR/STR) | `filings` | 5 years from the filing date | 31 CFR 1020.320(d); AMLA s.9(b). Confidential: 31 U.S.C. 5318(g)(2) (no tipping-off). | **Enforced.** Never erased, and withheld from DSAR access exports. |
| Audit trail | `audit_logs`, `audit_chain_heads` | At least as long as the records it evidences (5 years); kept indefinitely by default | Chain of custody for the records above. Entries hold pseudonyms only, so GDPR erasure doesn't touch them. | **Enforced.** A Postgres trigger makes the table append-only; DELETE and TRUNCATE always fail (migration 0006). |
| Data-subject requests | `privacy_requests` | 3 years after completion (policy) | GDPR Art. 5(2) accountability (evidence that requests were handled). | Procedural. Request details are encrypted at rest. |
| Notifications | `notifications` | 1 year (policy); no legal requirement | None; operational only. | Procedural. Deleted for a user on erasure. |
| Webhook delivery log | `webhook_events` | 90 days (policy) | None; operational only. Payloads carry ids, not personal data. | Procedural. |
| Job ledger | `job_runs` | 90 days (policy) | None; operational only. Arguments are ids only. | Procedural. |
| Sanctions/PEP list snapshots | `watchlist_entries`, `list_imports` | As long as the decisions that used them (5 years) | Explains historical decisions (each decision records the list version). | Procedural. Imports are append-only in practice. |
| Database backups | `./backups`, `BACKUP_S3_URI` | 35 days rolling (`BACKUP_RETENTION_DAYS`), newest 7 always kept | Disaster recovery only. A short window means erased data ages out of backups. | **Enforced** by [scripts/backup.sh](../../scripts/backup.sh). |

## Procedures

**Expired-record review (yearly).** List transactions older than the retention window that are not
linked to a case or filing, and pseudonymise them through the DSAR erasure path or a reviewed SQL
script. Record the run in the audit trail. There is no automated purge.

**Erasure and backups.** An erasure applies to the live database only. Backups taken before it
expire within `BACKUP_RETENTION_DAYS`. If you restore a backup, erasures completed after that
backup's timestamp are **not** in the restored data. Re-apply them from your DSAR ticket record
before reopening the service. Known gap: FinShield doesn't keep an off-database erasure log yet.

**Encryption keys.** `DATA_ENCRYPTION_KEY` encrypts sensitive columns and derives the audit
signing key. It isn't in the database dump. Keep it in the platform secret store, backed up
separately from the database. A backup without its key can be restored, but the encrypted
columns can't be read and new audit exports won't verify against previously published keys.
