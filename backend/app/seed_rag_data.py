"""
Seed data for RAG retrieval service.
Adds sample compliance documents, sanctions entries, and precedent decisions.
"""

from app.rag_service import RAGRetrievalService, ComplianceDocument
from datetime import datetime
import uuid

def seed_rag_data(database_url: str):
    """Seed the RAG database with sample data (idempotent)."""
    print("Initializing RAG seed data...")

    service = RAGRetrievalService(database_url)

    # Skip if already seeded
    db = service._get_db()
    try:
        existing = db.query(ComplianceDocument).count()
    finally:
        db.close()
    if existing > 0:
        print(f"RAG already seeded ({existing} documents). Skipping.")
        return
    
    # Add compliance documents
    compliance_docs = [
        {
            "doc_id": "DOC-001",
            "title": "BSA/AML Compliance Program Requirements",
            "content": """Financial institutions must establish and maintain a comprehensive Anti-Money Laundering (AML) compliance program. The program must include: (1) internal policies, procedures, and controls; (2) designation of a compliance officer; (3) ongoing employee training; and (4) independent testing. The program must be risk-based and tailored to the institution's specific products, services, and customer base. Transactions exceeding $10,000 must be reported via Currency Transaction Reports (CTRs). Suspicious transactions must be reported via Suspicious Activity Reports (SARs) within 30 days of detection.""",
            "category": "regulation",
            "jurisdiction": "US",
            "effective_date": datetime(2020, 1, 1),
            "metadata": {"source": "FinCEN", "regulation": "31 CFR 1020.210"}
        },
        {
            "doc_id": "DOC-002",
            "title": "OFAC Sanctions Compliance Guidelines",
            "content": """The Office of Foreign Assets Control (OFAC) administers and enforces economic and trade sanctions. Financial institutions must screen customers and transactions against OFAC's Specially Designated Nationals (SDN) list and other sanctions lists. Strict liability applies - institutions can be penalized even for inadvertent violations. Red flags include: transactions involving sanctioned countries, entities with names similar to SDN entries, complex ownership structures designed to obscure beneficial owners, and transactions inconsistent with customer's known business activities.""",
            "category": "policy",
            "jurisdiction": "US",
            "effective_date": datetime(2019, 7, 1),
            "metadata": {"source": "OFAC", "framework": "Sanctions Compliance Commitment"}
        },
        {
            "doc_id": "DOC-003",
            "title": "Wire Transfer Reporting Requirements",
            "content": """International wire transfers exceeding $3,000 must include complete originator and beneficiary information. Financial institutions must maintain records of all wire transfers for 5 years. Red flags for wire transfers include: rapid movement of funds through multiple accounts, transfers to/from high-risk jurisdictions, transfers with no apparent business purpose, structuring to avoid reporting thresholds, and transfers involving shell companies or nominee accounts.""",
            "category": "guideline",
            "jurisdiction": "US",
            "effective_date": datetime(2021, 3, 1),
            "metadata": {"source": "FinCEN", "topic": "wire_transfers"}
        },
        {
            "doc_id": "DOC-004",
            "title": "Politically Exposed Persons (PEP) Risk Management",
            "content": """Financial institutions must identify and apply enhanced due diligence to Politically Exposed Persons (PEPs). PEPs include foreign government officials, their family members, and close associates. Enhanced due diligence measures include: senior management approval for account opening, establishing source of wealth and source of funds, conducting enhanced ongoing monitoring, and applying higher risk ratings. Domestic PEPs may also present elevated risk depending on position and jurisdiction.""",
            "category": "policy",
            "jurisdiction": "US",
            "effective_date": datetime(2020, 6, 1),
            "metadata": {"source": "FinCEN", "topic": "pep"}
        },
        {
            "doc_id": "DOC-005",
            "title": "High-Risk Jurisdiction Guidance",
            "content": """Transactions involving certain jurisdictions present elevated money laundering and terrorist financing risks. High-risk jurisdictions include countries subject to OFAC sanctions (Cuba, Iran, North Korea, Syria), FATF blacklisted countries, and jurisdictions identified as having strategic AML/CFT deficiencies. Enhanced due diligence is required for transactions involving these jurisdictions, including understanding the business purpose, verifying beneficial ownership, and obtaining senior management approval.""",
            "category": "guideline",
            "jurisdiction": "US",
            "effective_date": datetime(2022, 1, 1),
            "metadata": {"source": "FinCEN", "topic": "geographic_risk"}
        }
    ]
    
    print("Adding compliance documents...")
    for doc in compliance_docs:
        service.add_compliance_document(**doc)
    
    # Add sanctions entries (sample OFAC SDN list)
    sanctions_entries = [
        {
            "entry_id": "SDN-001",
            "name": "IVAN PETROV",
            "entry_type": "individual",
            "program": "SDN",
            "country": "RU",
            "aliases": ["IVAN PETROVICH PETROV", "I. PETROV"],
            "remarks": "Linked to sanctioned Russian entity. DOB: 1975-03-15"
        },
        {
            "entry_id": "SDN-002",
            "name": "NORTH KOREA MINISTRY OF STATE SECURITY",
            "entry_type": "entity",
            "program": "DPRK",
            "country": "KP",
            "aliases": ["MSS", "MINISTRY OF STATE SECURITY"],
            "remarks": "Government intelligence agency"
        },
        {
            "entry_id": "SDN-003",
            "name": "AHMAD AL-RASHID",
            "entry_type": "individual",
            "program": "SDGT",
            "country": "SY",
            "aliases": ["AHMAD RASHID", "A. AL-RASHID"],
            "remarks": "Designated for providing financial support to terrorist organizations"
        },
        {
            "entry_id": "SDN-004",
            "name": "TEHRAN ENERGY CORPORATION",
            "entry_type": "entity",
            "program": "IRAN",
            "country": "IR",
            "aliases": ["TEC", "TEHRAN ENERGY"],
            "remarks": "State-owned energy company subject to secondary sanctions"
        },
        {
            "entry_id": "SDN-005",
            "name": "KIM JONG-SIK",
            "entry_type": "individual",
            "program": "DPRK2",
            "country": "KP",
            "aliases": ["KIM JONG SIK", "J. KIM"],
            "remarks": "Senior official in weapons development program"
        },
        {
            "entry_id": "SDN-006",
            "name": "CUBA MINISTRY OF INTERIOR",
            "entry_type": "entity",
            "program": "CUBA",
            "country": "CU",
            "aliases": ["MININT", "MINISTRY OF INTERIOR"],
            "remarks": "Government ministry subject to comprehensive sanctions"
        }
    ]
    
    print("Adding sanctions entries...")
    for entry in sanctions_entries:
        service.add_sanctions_entry(**entry)
    
    # Add precedent decisions
    precedent_decisions = [
        {
            "decision_id": "PREC-001",
            "case_summary": "Wire transfer of $45,000 from US account to account in Cyprus. Sender is a small retail business. Transfer described as 'consulting fees' but no supporting documentation provided. Receiver is a newly established entity with limited online presence.",
            "decision": "flagged",
            "reasoning": "Transaction exhibits multiple red flags: (1) amount significantly exceeds typical business transactions for stated business type, (2) destination jurisdiction (Cyprus) has elevated risk profile, (3) lack of supporting documentation for stated purpose, (4) receiver entity lacks established business history. Recommended enhanced due diligence and request for additional documentation before processing.",
            "risk_factors": {"amount_anomaly": True, "high_risk_jurisdiction": True, "missing_documentation": True, "new_entity": True}
        },
        {
            "decision_id": "PREC-002",
            "case_summary": "Customer attempted wire transfer of $12,500 to individual named 'Mohammed Al-Hassan' in Lebanon. Customer stated purpose as 'family support'. Customer has no previous transaction history with Middle East region.",
            "decision": "blocked",
            "reasoning": "Transfer blocked due to potential sanctions match. Name 'Mohammed Al-Hassan' returned high similarity score against OFAC SDN list. While not an exact match, the combination of name similarity, high-risk destination country, and lack of previous transaction history with the region warranted blocking pending further investigation. Compliance officer reviewed and confirmed block.",
            "risk_factors": {"sanctions_match": True, "high_risk_jurisdiction": True, "unusual_pattern": True}
        },
        {
            "decision_id": "PREC-003",
            "case_summary": "Series of 8 wire transfers ranging from $8,000 to $9,500 over 5 business days from corporate account to various domestic recipients. All transfers occurred just below the $10,000 CTR reporting threshold.",
            "decision": "flagged",
            "reasoning": "Transaction pattern strongly suggests structuring to avoid CTR reporting requirements. The consistent pattern of transactions just below the reporting threshold, combined with the frequency and multiple recipients, meets the criteria for suspicious activity. SAR filing recommended. Account flagged for enhanced monitoring.",
            "risk_factors": {"structuring": True, "threshold_avoidance": True, "unusual_frequency": True}
        },
        {
            "decision_id": "PREC-004",
            "case_summary": "International wire transfer of $28,000 from established import/export business to supplier in China. Transaction consistent with customer's historical pattern and business type. All documentation provided including invoices and shipping records.",
            "decision": "approved",
            "reasoning": "Transaction approved after review. Key factors: (1) transaction amount and destination consistent with customer's established business pattern, (2) complete documentation provided including commercial invoices and bills of lading, (3) no sanctions matches identified, (4) customer has strong compliance history with no previous flags. Standard processing approved.",
            "risk_factors": {"established_pattern": True, "complete_documentation": True, "low_risk_jurisdiction": False}
        },
        {
            "decision_id": "PREC-005",
            "case_summary": "PEP customer (foreign government official) opened account and initiated first wire transfer of $150,000 to offshore account in Cayman Islands. Stated purpose as 'investment diversification'.",
            "decision": "flagged",
            "reasoning": "Transaction flagged due to PEP status combined with high-risk characteristics: (1) customer is a foreign PEP requiring enhanced due diligence, (2) first transaction is unusually large, (3) destination is a known tax haven, (4) stated purpose is vague. Enhanced due diligence required including source of wealth verification, senior management approval, and ongoing monitoring. Transaction held pending completion of EDD procedures.",
            "risk_factors": {"pep_status": True, "large_first_transaction": True, "tax_haven_destination": True, "vague_purpose": True}
        }
    ]
    
    print("Adding precedent decisions...")
    for precedent in precedent_decisions:
        service.add_precedent_decision(**precedent)
    
    print("RAG seed data initialization complete!")
    print(f"Added {len(compliance_docs)} compliance documents")
    print(f"Added {len(sanctions_entries)} sanctions entries")
    print(f"Added {len(precedent_decisions)} precedent decisions")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    database_url = os.getenv("RAG_DATABASE_URL", "postgresql://finshield:finshield_secret@localhost:5432/finshield")
    seed_rag_data(database_url)
