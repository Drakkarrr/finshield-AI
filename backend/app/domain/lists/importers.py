"""Parsers for list sources. Each returns (entries, list_version); persistence is the caller's job."""
from __future__ import annotations

import csv
import hashlib
import io
from typing import Optional

from app.domain.lists import ListEntry

OFAC_SOURCE = "OFAC-SDN"
_NULL = "-0-"


def _clean(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return None if not v or v == _NULL else v


def _digest(*contents: str) -> str:
    h = hashlib.sha256()
    for c in contents:
        h.update(c.encode("utf-8"))
    return h.hexdigest()[:16]


def parse_ofac_sdn(sdn_csv: str, alt_csv: str = "", add_csv: str = "", version: Optional[str] = None,
                   source: str = OFAC_SOURCE) -> tuple[list[ListEntry], str]:
    """OFAC SDN legacy CSV layout (sdn.csv / alt.csv / add.csv, no header, '-0-' = empty).

    sdn: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type, Tonnage, GRT,
         Vess_flag, Vess_owner, Remarks
    alt: ent_num, alt_num, alt_type, alt_name, alt_remarks
    add: ent_num, add_num, address, city/state/postal, country, add_remarks
    The version is a content digest unless given, so re-importing an unchanged file is detectable.
    """
    list_version = version or _digest(sdn_csv, alt_csv, add_csv)
    aliases: dict[str, list[str]] = {}
    for row in csv.reader(io.StringIO(alt_csv)):
        name = _clean(row[3]) if len(row) >= 4 else None
        if name:
            aliases.setdefault(row[0].strip(), []).append(name)
    countries: dict[str, str] = {}
    for row in csv.reader(io.StringIO(add_csv)):
        country = _clean(row[4]) if len(row) >= 5 else None
        if country:
            countries.setdefault(row[0].strip(), country)
    entries = []
    for row in csv.reader(io.StringIO(sdn_csv)):
        name = _clean(row[1]) if len(row) >= 4 else None
        if not name:
            continue
        ent = row[0].strip()
        entries.append(ListEntry(
            id=f"{source}:{ent}", source=source, list_version=list_version, list_type="sanctions",
            primary_name=name, aliases=tuple(aliases.get(ent, ())),
            entity_type=_clean(row[2]) or "entity", country=countries.get(ent),
        ))
    return entries, list_version


def parse_pep_csv(pep_csv: str, source: str, version: Optional[str] = None) -> tuple[list[ListEntry], str]:
    """Generic PEP CSV with header: id,name,aliases(';'-separated),country,position."""
    list_version = version or _digest(pep_csv)
    entries = []
    for row in csv.DictReader(io.StringIO(pep_csv)):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        aliases = tuple(a.strip() for a in (row.get("aliases") or "").split(";") if a.strip())
        entries.append(ListEntry(
            id=f"{source}:{row['id'].strip()}", source=source, list_version=list_version, list_type="pep",
            primary_name=name, aliases=aliases, entity_type="individual", country=(row.get("country") or None),
        ))
    return entries, list_version
