"""Database-backed sanctions/PEP list provider with fuzzy matching."""

import difflib
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import PEPEntry, SanctionsEntry
from app.domain.lists.provider import ListMatch, MatchType


class DBListProvider:
    """List provider backed by sanctions_entries and pep_entries tables."""

    def __init__(self, db: Session, fuzzy_threshold: float = 0.8):
        self.db = db
        self.fuzzy_threshold = fuzzy_threshold

    def check_sanctions(
        self,
        name: str,
        country: Optional[str] = None,
    ) -> list[ListMatch]:
        """Check name against sanctions lists with exact, alias, and fuzzy matching."""
        matches = []
        name_lower = name.lower().strip()

        # Load all sanctions entries (could be cached for performance)
        entries = self.db.query(SanctionsEntry).all()

        for entry in entries:
            # Country filter if provided
            if country and entry.country and entry.country.lower() != country.lower():
                continue

            # Exact match on name
            if entry.name.lower().strip() == name_lower:
                matches.append(ListMatch(
                    list_name=f"sanctions:{entry.program or 'unknown'}",
                    entity_id=entry.id,
                    entity_name=entry.name,
                    match_type=MatchType.EXACT,
                    confidence=1.0,
                    match_details="Exact name match",
                    source_provenance=f"sanctions_entries:{entry.program}",
                ))
                continue

            # Check aliases
            if entry.aliases:
                for alias in entry.aliases:
                    if isinstance(alias, str) and alias.lower().strip() == name_lower:
                        matches.append(ListMatch(
                            list_name=f"sanctions:{entry.program or 'unknown'}",
                            entity_id=entry.id,
                            entity_name=entry.name,
                            match_type=MatchType.ALIAS,
                            confidence=0.95,
                            match_details=f"Alias match: {alias}",
                            source_provenance=f"sanctions_entries:{entry.program}",
                        ))
                        break

            # Fuzzy match on name
            similarity = difflib.SequenceMatcher(
                None, name_lower, entry.name.lower().strip()
            ).ratio()

            if similarity >= self.fuzzy_threshold:
                matches.append(ListMatch(
                    list_name=f"sanctions:{entry.program or 'unknown'}",
                    entity_id=entry.id,
                    entity_name=entry.name,
                    match_type=MatchType.FUZZY,
                    confidence=similarity,
                    match_details=f"Fuzzy match (similarity: {similarity:.2f})",
                    source_provenance=f"sanctions_entries:{entry.program}",
                ))

        return matches

    def check_pep(
        self,
        name: str,
        country: Optional[str] = None,
    ) -> list[ListMatch]:
        """Check name against PEP lists with exact, alias, and fuzzy matching."""
        matches = []
        name_lower = name.lower().strip()

        # Load all PEP entries
        entries = self.db.query(PEPEntry).all()

        for entry in entries:
            # Country filter if provided
            if country and entry.country and entry.country.lower() != country.lower():
                continue

            # Exact match on name
            if entry.name.lower().strip() == name_lower:
                matches.append(ListMatch(
                    list_name=f"pep:{entry.category or 'unknown'}",
                    entity_id=entry.id,
                    entity_name=entry.name,
                    match_type=MatchType.EXACT,
                    confidence=1.0,
                    match_details=f"Exact name match (position: {entry.position})",
                    source_provenance=f"pep_entries:{entry.source}",
                ))
                continue

            # Check aliases
            if entry.aliases:
                for alias in entry.aliases:
                    if isinstance(alias, str) and alias.lower().strip() == name_lower:
                        matches.append(ListMatch(
                            list_name=f"pep:{entry.category or 'unknown'}",
                            entity_id=entry.id,
                            entity_name=entry.name,
                            match_type=MatchType.ALIAS,
                            confidence=0.95,
                            match_details=f"Alias match: {alias}",
                            source_provenance=f"pep_entries:{entry.source}",
                        ))
                        break

            # Fuzzy match on name
            similarity = difflib.SequenceMatcher(
                None, name_lower, entry.name.lower().strip()
            ).ratio()

            if similarity >= self.fuzzy_threshold:
                matches.append(ListMatch(
                    list_name=f"pep:{entry.category or 'unknown'}",
                    entity_id=entry.id,
                    entity_name=entry.name,
                    match_type=MatchType.FUZZY,
                    confidence=similarity,
                    match_details=f"Fuzzy match (similarity: {similarity:.2f})",
                    source_provenance=f"pep_entries:{entry.source}",
                ))

        return matches

    def refresh_lists(self) -> None:
        """Refresh is a no-op for DB-backed provider (data is always current)."""
        pass
