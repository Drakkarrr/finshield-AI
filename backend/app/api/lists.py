"""FinShield AI — Sanctions/PEP list management API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.db_models import PEPEntry, SanctionsEntry, User
from app.domain.lists.ofac_importer import seed_sample_sanctions
from app.domain.lists.pep_seeder import seed_sample_peps

router = APIRouter()


@router.post("/api/v1/lists/seed-sample", tags=["Lists"])
def seed_sample_lists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Seed sample sanctions and PEP data for testing/demo purposes."""
    sanctions_count = seed_sample_sanctions(db)
    pep_count = seed_sample_peps(db)

    return {
        "success": True,
        "sanctions_imported": sanctions_count,
        "pep_imported": pep_count,
        "message": f"Seeded {sanctions_count} sanctions entries and {pep_count} PEP entries",
    }


@router.get("/api/v1/lists/stats", tags=["Lists"])
def get_list_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get statistics on sanctions and PEP lists."""
    sanctions_count = db.query(SanctionsEntry).count()
    pep_count = db.query(PEPEntry).count()

    return {
        "sanctions_entries": sanctions_count,
        "pep_entries": pep_count,
        "total_entries": sanctions_count + pep_count,
    }


@router.get("/api/v1/lists/sanctions", tags=["Lists"])
def list_sanctions(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List sanctions entries (paginated)."""
    entries = (
        db.query(SanctionsEntry)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "entries": [
            {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "program": e.program,
                "country": e.country,
                "aliases": e.aliases or [],
                "remarks": e.remarks,
            }
            for e in entries
        ],
        "count": len(entries),
    }


@router.get("/api/v1/lists/peps", tags=["Lists"])
def list_peps(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List PEP entries (paginated)."""
    entries = (
        db.query(PEPEntry)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "entries": [
            {
                "id": e.id,
                "name": e.name,
                "position": e.position,
                "country": e.country,
                "category": e.category,
                "aliases": e.aliases or [],
                "source": e.source,
            }
            for e in entries
        ],
        "count": len(entries),
    }
