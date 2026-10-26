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
            assert len(versions) == 1
            assert versions[0].version_number == 1
            assert versions[0].narrative == "Updated after submission"
            assert versions[0].changed_by == user_id
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
        # Filing was submitted directly in DB (bypassing API), so no version 1 snapshot.
        # The two narrative updates create versions 1 and 2.
        assert len(versions) == 2
        # Descending order
        assert versions[0]["version_number"] == 2
        assert versions[0]["narrative"] == "Second update"
        assert versions[1]["version_number"] == 1
        assert versions[1]["narrative"] == "First update"
