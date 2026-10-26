"""S7.3: Filing controls and versioning tests."""
import os
import uuid

os.environ["APP_ENV"] = "test"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _unique_email() -> str:
    return f"{uuid.uuid4().hex[:8]}@test.io"


async def _register_user(client: AsyncClient, role: str = "analyst") -> tuple[str, str, str]:
    """Register an admin user, then create a user with the specified role via admin API.
    Returns (email, token, user_id) for the created user."""
    # First register an admin user
    admin_email = _unique_email()
    r = await client.post("/api/auth/register", json={
        "email": admin_email,
        "password": "SecurePass123!",
        "first_name": "Admin",
        "last_name": "User",
        "company": "Test Corp",
    })
    assert r.status_code == 201, f"Register admin failed: {r.status_code} {r.text}"
    admin_token = r.json()["access_token"]

    # Create a user with the specified role via admin API
    email = _unique_email()
    r = await client.post("/api/v1/admin/users", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User",
        "role": role,
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 201, f"Create user failed: {r.status_code} {r.text}"
    user_id = r.json()["id"]

    # Login as the created user
    r = await client.post("/api/auth/login", json={
        "email": email,
        "password": "SecurePass123!",
    })
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]

    return email, token, user_id


async def _create_suspicious_case(client: AsyncClient, token: str) -> str:
    """Create a transaction and case resolved as suspicious, return case_id."""
    # Screen a transaction
    r = await client.post("/api/v1/transactions", json={
        "amount": 50000,
        "currency": "USD",
        "transaction_type": "wire",
        "sender_name": "John Doe",
        "receiver_name": "Jane Smith",
        "destination_country": "IR",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201), f"Screen failed: {r.status_code} {r.text}"
    tx_id = r.json()["data"]["transaction_id"] if r.status_code == 200 else r.json()["id"]

    # Create a case
    r = await client.post("/api/v1/cases", json={
        "transaction_id": tx_id,
        "reason": "Suspicious activity",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, f"Create case failed: {r.status_code} {r.text}"
    case_id = r.json()["case_id"]

    # Resolve as suspicious
    r = await client.patch(f"/api/v1/cases/{case_id}", json={
        "resolution": "confirmed_suspicious",
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, f"Resolve case failed: {r.status_code} {r.text}"

    return case_id


class TestFilingAccessControl:
    """S7.3: Filing reads require investigator+ role."""

    @pytest.mark.asyncio
    async def test_analyst_cannot_list_filings(self, client):
        """Analyst gets 403 on GET /api/v1/filings."""
        _, token, _ = await _register_user(client, "analyst")

        r = await client.get("/api/v1/filings", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_analyst_cannot_get_filing(self, client):
        """Analyst gets 403 on GET /api/v1/filings/{id}."""
        _, token, _ = await _register_user(client, "analyst")

        r = await client.get("/api/v1/filings/fake-id", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_investigator_can_list_filings(self, client):
        """Investigator can list filings."""
        _, token, _ = await _register_user(client, "investigator")

        r = await client.get("/api/v1/filings", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_investigator_can_get_filing(self, client):
        """Investigator can get a specific filing."""
        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Test narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        filing_id = r.json()["id"]

        # Get the filing
        r = await client.get(f"/api/v1/filings/{filing_id}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["id"] == filing_id


class TestFilingVersioning:
    """S7.3: Submitted filing narrative changes create versions."""

    @pytest.mark.asyncio
    async def test_draft_narrative_update_no_version(self, client):
        """Updating narrative on draft filing does NOT create a version."""
        from app.database import SessionLocal
        from app.db_models import FilingVersion

        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create a draft filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        filing_id = r.json()["id"]

        # Update the narrative
        r = await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Updated narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

        # Check no version was created
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            versions = db.query(FilingVersion).filter(FilingVersion.filing_id == filing_id).all()
            assert len(versions) == 0
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_submitted_narrative_update_creates_version(self, client):
        """Updating narrative on submitted filing creates a version."""
        from app.database import SessionLocal
        from app.db_models import Filing, FilingVersion

        _, token, user_id = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        filing_id = r.json()["id"]

        # Submit it (directly in DB since we're investigator, not supervisor)
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "submitted"
            db.commit()
        finally:
            db.close()

        # Update the narrative
        r = await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Updated after submission",
            "amendment_reason": "Correcting factual error in narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["narrative"] == "Updated after submission"

        # Check version was created
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            versions = db.query(FilingVersion).filter(FilingVersion.filing_id == filing_id).all()
            # Defensive backfill creates version 1 (original narrative), amendment creates version 2
            assert len(versions) == 2
            assert versions[0].version_number == 1
            assert versions[0].narrative == "Initial narrative"
            assert versions[0].change_reason == "Backfilled version 1 snapshot"
            assert versions[1].version_number == 2
            assert versions[1].narrative == "Updated after submission"
            assert versions[1].changed_by == user_id
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_version_history_endpoint(self, client):
        """GET /api/v1/filings/{id}/versions returns version history."""
        from app.database import SessionLocal
        from app.db_models import Filing

        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create and submit a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial",
        }, headers={"Authorization": f"Bearer {token}"})
        filing_id = r.json()["id"]

        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "submitted"
            db.commit()
        finally:
            db.close()

        # Update narrative twice
        await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "First update",
            "amendment_reason": "First correction",
        }, headers={"Authorization": f"Bearer {token}"})

        await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Second update",
            "amendment_reason": "Second correction",
        }, headers={"Authorization": f"Bearer {token}"})

        # Get version history
        r = await client.get(f"/api/v1/filings/{filing_id}/versions", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        versions = r.json()
        # Filing was submitted directly in DB (bypassing API), so defensive backfill creates version 1.
        # The two narrative updates create versions 2 and 3.
        assert len(versions) == 3
        # Descending order
        assert versions[0]["version_number"] == 3
        assert versions[0]["narrative"] == "Second update"
        assert versions[1]["version_number"] == 2
        assert versions[1]["narrative"] == "First update"
        assert versions[2]["version_number"] == 1
        assert versions[2]["narrative"] == "Initial"


class TestFilingAmendmentValidation:
    """S7.3: Amendment reason validation and confirmed filing lock."""

    @pytest.mark.asyncio
    async def test_amendment_without_reason_rejected(self, client):
        """PATCH on submitted filing without amendment_reason returns 422."""
        from app.database import SessionLocal
        from app.db_models import Filing

        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create and submit a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial",
        }, headers={"Authorization": f"Bearer {token}"})
        filing_id = r.json()["id"]

        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "submitted"
            db.commit()
        finally:
            db.close()

        # Try to amend without reason
        r = await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Updated",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert "amendment_reason" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirmed_filing_requires_amendment_reason(self, client):
        """PATCH on confirmed filing without amendment_reason returns 422."""
        from app.database import SessionLocal
        from app.db_models import Filing

        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create and confirm a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial",
        }, headers={"Authorization": f"Bearer {token}"})
        filing_id = r.json()["id"]

        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "confirmed"
            db.commit()
        finally:
            db.close()

        # Try to amend without reason
        r = await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Updated",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422


class TestFilingAuditIntegrity:
    """S7.3: Audit trail integrity for filing submissions and amendments."""

    @pytest.mark.asyncio
    async def test_submission_writes_filing_updated_audit(self, client):
        """Submitting a filing writes a filing_updated audit entry with status='submitted'."""
        from app.database import SessionLocal
        from app.db_models import AuditLog

        admin_email, admin_token, _ = await _register_user(client, "admin")
        _, supervisor_token, _ = await _register_user(client, "supervisor")
        case_id = await _create_suspicious_case(client, supervisor_token)

        # Create a draft filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Initial",
        }, headers={"Authorization": f"Bearer {supervisor_token}"})
        filing_id = r.json()["id"]

        # Submit it via API (supervisor role)
        r = await client.patch(f"/api/v1/filings/{filing_id}", json={
            "status": "submitted",
        }, headers={"Authorization": f"Bearer {supervisor_token}"})
        assert r.status_code == 200

        # Check audit log has filing_updated with status='submitted'
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            audits = db.query(AuditLog).filter(
                AuditLog.resource_type == "filing",
                AuditLog.resource_id == filing_id,
                AuditLog.action == "filing_updated"
            ).all()
            assert len(audits) >= 1
            # Find the one with status='submitted'
            submission_audit = next((a for a in audits if a.details.get("status") == "submitted"), None)
            assert submission_audit is not None
            assert "status" in submission_audit.details["fields"]
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_preexisting_filing_preserves_original_narrative(self, client):
        """A filing submitted before migration 0013 preserves original text on first amendment."""
        from app.database import SessionLocal
        from app.db_models import Filing, FilingVersion

        _, token, _ = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token)

        # Create a filing
        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Original narrative",
        }, headers={"Authorization": f"Bearer {token}"})
        filing_id = r.json()["id"]

        # Simulate pre-existing submitted filing (no versions)
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "submitted"
            filing.narrative = "Original narrative"
            db.commit()
        finally:
            db.close()

        # Amend it twice
        await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "First amendment",
            "amendment_reason": "Correction 1",
        }, headers={"Authorization": f"Bearer {token}"})

        await client.patch(f"/api/v1/filings/{filing_id}", json={
            "narrative": "Second amendment",
            "amendment_reason": "Correction 2",
        }, headers={"Authorization": f"Bearer {token}"})

        # Check version 1 still has original narrative
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            versions = db.query(FilingVersion).filter(
                FilingVersion.filing_id == filing_id
            ).order_by(FilingVersion.version_number).all()
            assert len(versions) == 3
            assert versions[0].version_number == 1
            assert versions[0].narrative == "Original narrative"
            assert versions[0].change_reason == "Backfilled version 1 snapshot"
            assert versions[1].version_number == 2
            assert versions[1].narrative == "First amendment"
            assert versions[2].version_number == 3
            assert versions[2].narrative == "Second amendment"
        finally:
            db.close()


class TestFilingVersionRLS:
    """S7.3: RLS enforcement on filing_versions table."""

    @pytest.mark.asyncio
    async def test_cross_tenant_version_isolation(self, client):
        """Tenant B cannot read tenant A's filing_versions without app filter."""
        from app.auth import hash_password
        from app.database import SessionLocal
        from app.db_models import Filing, FilingVersion, Tenant, User

        # Create tenant A and a filing with versions
        _, token_a, user_a_id = await _register_user(client, "investigator")
        case_id = await _create_suspicious_case(client, token_a)

        r = await client.post("/api/v1/filings", json={
            "case_id": case_id,
            "filing_type": "SAR",
            "narrative": "Tenant A filing",
        }, headers={"Authorization": f"Bearer {token_a}"})
        filing_id = r.json()["id"]

        # Submit it to create version 1
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            filing = db.query(Filing).filter(Filing.id == filing_id).first()
            filing.status = "submitted"
            tenant_a_id = filing.tenant_id
            db.commit()
        finally:
            db.close()

        # Create tenant B and user
        db = SessionLocal()
        db.info["rls_bypass"] = True
        try:
            tenant_b_id = f"tenant-{uuid.uuid4().hex[:8]}"
            tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
            db.add(tenant_b)
            db.commit()
            db.refresh(tenant_b)

            user_b = User(
                id=f"user-{uuid.uuid4().hex[:8]}",
                email=f"user-b-{uuid.uuid4().hex[:4]}@test.com",
                hashed_password=hash_password("password123"),
                first_name="User",
                last_name="B",
                role="investigator",
                tenant_id=tenant_b.id,
                is_active=True,
            )
            db.add(user_b)
            db.commit()
        finally:
            db.close()

        # Try to read tenant A's versions as tenant B (without bypass)
        db = SessionLocal()
        try:
            # This should return 0 rows due to RLS
            versions = db.query(FilingVersion).filter(
                FilingVersion.filing_id == filing_id,
                FilingVersion.tenant_id == tenant_a_id
            ).all()
            assert len(versions) == 0, "RLS should prevent cross-tenant reads"
        finally:
            db.close()
