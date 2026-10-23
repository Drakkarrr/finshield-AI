"""OFAC sanctions list importer."""

import csv
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import SanctionsEntry


def import_ofac_csv(db: Session, csv_path: Path, program: str = "SDN") -> int:
    """
    Import OFAC sanctions data from CSV format.

    Expected CSV columns: name, type, country, aliases (JSON array), remarks
    Returns number of entries imported.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    imported = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry_id = str(uuid.uuid4())
            aliases = json.loads(row.get("aliases", "[]")) if row.get("aliases") else []

            entry = SanctionsEntry(
                id=entry_id,
                name=row["name"].strip(),
                type=row.get("type", "individual").strip(),
                program=program,
                country=row.get("country", "").strip() or None,
                aliases=aliases,
                remarks=row.get("remarks", "").strip() or None,
            )
            db.add(entry)
            imported += 1

    db.commit()
    return imported


def import_ofac_json(db: Session, json_path: Path, program: str = "SDN") -> int:
    """
    Import OFAC sanctions data from JSON format.

    Expected JSON structure:
    [
      {
        "name": "John Doe",
        "type": "individual",
        "country": "US",
        "aliases": ["J. Doe", "Johnny Doe"],
        "remarks": "Some remarks"
      },
      ...
    ]
    Returns number of entries imported.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    imported = 0
    for item in data:
        entry_id = str(uuid.uuid4())
        entry = SanctionsEntry(
            id=entry_id,
            name=item["name"].strip(),
            type=item.get("type", "individual").strip(),
            program=program,
            country=item.get("country", "").strip() or None,
            aliases=item.get("aliases", []),
            remarks=item.get("remarks", "").strip() or None,
        )
        db.add(entry)
        imported += 1

    db.commit()
    return imported


def seed_sample_sanctions(db: Session) -> int:
    """Seed sample sanctions data for testing/demo purposes."""
    sample_data = [
        {
            "name": "AL QAEDA",
            "type": "entity",
            "program": "SDN",
            "country": None,
            "aliases": ["Base", "Al-Qaida"],
            "remarks": "Terrorist organization",
        },
        {
            "name": "PUTIN, VLADIMIR",
            "type": "individual",
            "program": "SDN",
            "country": "RU",
            "aliases": ["Vladimir Putin", "V. Putin"],
            "remarks": "President of Russia",
        },
        {
            "name": "NORTH KOREA FOREIGN TRADE BANK",
            "type": "entity",
            "program": "DPRK",
            "country": "KP",
            "aliases": ["DPRK Foreign Trade Bank"],
            "remarks": "North Korean state bank",
        },
        {
            "name": "HEZBOLLAH",
            "type": "entity",
            "program": "SDGT",
            "country": "LB",
            "aliases": ["Party of God", "Hizballah"],
            "remarks": "Lebanese militant group",
        },
        {
            "name": "ASSAD, BASHAR",
            "type": "individual",
            "program": "SYRIA",
            "country": "SY",
            "aliases": ["Bashar al-Assad", "B. Assad"],
            "remarks": "President of Syria",
        },
    ]

    imported = 0
    for item in sample_data:
        entry_id = str(uuid.uuid4())
        entry = SanctionsEntry(
            id=entry_id,
            name=item["name"],
            type=item["type"],
            program=item["program"],
            country=item.get("country"),
            aliases=item.get("aliases", []),
            remarks=item.get("remarks"),
        )
        db.add(entry)
        imported += 1

    db.commit()
    return imported
