"""PEP list seeder."""

import uuid

from sqlalchemy.orm import Session

from app.db_models import PEPEntry


def seed_sample_peps(db: Session) -> int:
    """Seed sample PEP data for testing/demo purposes."""
    sample_data = [
        {
            "name": "TRUMP, DONALD",
            "position": "Former President of the United States",
            "country": "US",
            "category": "domestic",
            "aliases": ["Donald J. Trump", "D. Trump"],
            "source": "sample",
        },
        {
            "name": "BIDEN, JOE",
            "position": "President of the United States",
            "country": "US",
            "category": "domestic",
            "aliases": ["Joseph R. Biden", "J. Biden"],
            "source": "sample",
        },
        {
            "name": "XI JINPING",
            "position": "President of the People's Republic of China",
            "country": "CN",
            "category": "foreign",
            "aliases": ["Xi Jinping", "President Xi"],
            "source": "sample",
        },
        {
            "name": "MACRON, EMMANUEL",
            "position": "President of France",
            "country": "FR",
            "category": "foreign",
            "aliases": ["Emmanuel Macron", "E. Macron"],
            "source": "sample",
        },
        {
            "name": "MERKEL, ANGELA",
            "position": "Former Chancellor of Germany",
            "country": "DE",
            "category": "foreign",
            "aliases": ["Angela Merkel", "A. Merkel"],
            "source": "sample",
        },
    ]

    imported = 0
    for item in sample_data:
        entry_id = str(uuid.uuid4())
        entry = PEPEntry(
            id=entry_id,
            name=item["name"],
            position=item["position"],
            country=item["country"],
            category=item["category"],
            aliases=item.get("aliases", []),
            source=item["source"],
        )
        db.add(entry)
        imported += 1

    db.commit()
    return imported
