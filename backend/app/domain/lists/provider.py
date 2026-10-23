"""List provider interface and match models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class MatchType(str, Enum):
    """Type of list match."""
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"


@dataclass
class ListMatch:
    """A match against a sanctions/PEP list."""
    list_name: str
    entity_id: str
    entity_name: str
    match_type: MatchType
    confidence: float
    match_details: str = field(default="")
    source_provenance: str = field(default="")


class ListProvider(Protocol):
    """Protocol for sanctions/PEP list providers."""

    def check_sanctions(
        self,
        name: str,
        country: str | None = None,
    ) -> list[ListMatch]:
        """Check name against sanctions lists."""
        ...

    def check_pep(
        self,
        name: str,
        country: str | None = None,
    ) -> list[ListMatch]:
        """Check name against PEP lists."""
        ...

    def refresh_lists(self) -> None:
        """Refresh lists from source (e.g., reload from DB or file)."""
        ...
