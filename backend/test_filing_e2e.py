#!/usr/bin/env python3
"""
E2E Test: SAR/STR Filing Module
Tests the complete filing workflow from case resolution to filing submission.
"""
import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8091"

def test_filing_workflow():
    """Test complete filing workflow."""
    print("=" * 60)
    print("E2E Test: SAR/STR Filing Module")
    print("=" * 60)
    
    # Step 1: Register user
    print("\n[1/8] Registering user...")
    unique_email = f"test.filing.{int(time.time())}@example.com"
    resp = httpx.post(f"{BASE_URL}/api/auth/register", json={
        "email": unique_email,
        "password": "TestPass123!",
        "first_name": "Test",
        "last_name": "User",
        "company": "Test Bank"
    })
    if resp.status_code != 201:
        print(f"❌ Failed to register: {resp.text}")
        return False
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ User registered")
    
    # Step 2: Create transaction
    print("\n[2/8] Creating transaction...")
    resp = httpx.post(f"{BASE_URL}/api/v1/transactions", headers=headers, json={
        "amount": 15000,
        "currency": "USD",
        "transaction_type": "wire",
        "sender_name": "John Doe",
        "receiver_name": "Jane Smith",
        "destination_country": "US",
        "description": "Large wire transfer"
    })
    if resp.status_code not in [200, 201]:
        print(f"❌ Failed to create transaction: {resp.text}")
        return False
    tx_id = resp.json()["data"]["transaction_id"] if "data" in resp.json() else resp.json()["transaction_id"]
    print(f"✓ Transaction created: {tx_id}")
    
    # Step 3: Create case
    print("\n[3/8] Creating case...")
    resp = httpx.post(f"{BASE_URL}/api/v1/cases", headers=headers, json={
        "transaction_id": tx_id,
        "reason": "Suspicious large wire transfer",
        "priority": "high"
    })
    if resp.status_code != 201:
        print(f"❌ Failed to create case: {resp.text}")
        return False
    case_data = resp.json()
    case_id = case_data.get("case_id") or case_data.get("id") or case_data.get("data", {}).get("id")
    print(f"✓ Case created: {case_id}")
    
    # Step 4: Resolve case as suspicious (required before filing)
    print("\n[4/8] Resolving case as suspicious...")
    resp = httpx.patch(f"{BASE_URL}/api/v1/cases/{case_id}", headers=headers, json={
        "status": "resolved",
        "resolution": "confirmed_suspicious",
        "resolution_summary": "Confirmed suspicious after investigation"
    })
    if resp.status_code != 200:
        print(f"❌ Failed to resolve case: {resp.text}")
        return False
    print("✓ Case resolved as suspicious")
    
    # Step 5: Create filing draft
    print("\n[5/8] Creating SAR filing draft...")
    resp = httpx.post(f"{BASE_URL}/api/v1/filings", headers=headers, json={
        "case_id": case_id,
        "filing_type": "SAR",
        "narrative": "This transaction is suspicious because it involves a large wire transfer of $15,000 to an unusual destination. The account has no prior history of such transactions."
    })
    if resp.status_code != 201:
        print(f"❌ Failed to create filing: {resp.text}")
        return False
    filing = resp.json()
    filing_id = filing["id"]
    print(f"✓ Filing created: {filing_id}")
    print(f"  - Type: {filing['filing_type']}")
    print(f"  - Status: {filing['status']}")
    print(f"  - Deadline: {filing['deadline']}")
    
    # Step 6: List filings
    print("\n[6/8] Listing filings...")
    resp = httpx.get(f"{BASE_URL}/api/v1/filings", headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to list filings: {resp.text}")
        return False
    filings = resp.json()
    print(f"✓ Found {len(filings)} filing(s)")
    assert len(filings) == 1, "Expected 1 filing"
    
    # Step 7: Update filing to under_review
    print("\n[7/8] Updating filing to under_review...")
    resp = httpx.patch(f"{BASE_URL}/api/v1/filings/{filing_id}", headers=headers, json={
        "status": "under_review"
    })
    if resp.status_code != 200:
        print(f"❌ Failed to update filing: {resp.text}")
        return False
    print("✓ Filing status: under_review")
    
    # Step 8: Submit filing
    print("\n[8/8] Submitting filing...")
    resp = httpx.patch(f"{BASE_URL}/api/v1/filings/{filing_id}", headers=headers, json={
        "status": "submitted",
        "reference_number": "SAR-2026-001234"
    })
    if resp.status_code != 200:
        print(f"❌ Failed to submit filing: {resp.text}")
        return False
    filing = resp.json()
    print("✓ Filing submitted")
    print(f"  - Status: {filing['status']}")
    print(f"  - Reference: {filing['reference_number']}")
    print(f"  - Submitted at: {filing['submitted_at']}")
    
    # Bonus: Test filtering
    print("\n[Bonus] Testing filing filters...")
    resp = httpx.get(f"{BASE_URL}/api/v1/filings?status=submitted", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    print("✓ Filter by status works")
    
    resp = httpx.get(f"{BASE_URL}/api/v1/filings?filing_type=SAR", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    print("✓ Filter by filing_type works")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_filing_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
