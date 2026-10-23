"""Sanctions / PEP list data and name matching (S2.3, ruling D12).

Pure: a `WatchlistSnapshot` is an immutable in-memory index built from list entries; the
persistence-backed `ListProvider` lives in app.domain.lists.provider.
"""
from __future__ import annotations

import re
import threading
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from rapidfuzz import fuzz, process

LIST_TYPES = ("sanctions", "pep")
SCORE_CACHE_SIZE = 4096  # normalised query names per snapshot (counterparties recur)

# Legal-form tokens that carry no identity. Removed only as whole tokens.
_LEGAL_FORMS = {"ltd", "llc", "inc", "corp", "corporation", "co", "company", "limited", "plc", "gmbh",
                "sa", "ag", "bv", "nv", "srl", "spa", "jsc", "ojsc", "pjsc", "llp", "lp"}


def normalize(name: str) -> str:
    """Case-fold, strip accents (transliteration-lite for Latin scripts), drop punctuation and
    legal-form tokens, collapse whitespace. Non-Latin scripts are not transliterated."""
    decomposed = unicodedata.normalize("NFKD", name or "")
    ascii_ish = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    tokens = re.sub(r"[^\w\s]", " ", ascii_ish.replace(".", "")).split()  # "S.A." -> "sa", "J.P." -> "jp"
    kept = [t for t in tokens if t not in _LEGAL_FORMS]
    return " ".join(kept or tokens)


@dataclass(frozen=True)
class ListEntry:
    id: str
    source: str
    list_version: str
    list_type: str  # sanctions | pep
    primary_name: str
    aliases: tuple[str, ...] = ()
    entity_type: Optional[str] = None
    country: Optional[str] = None


@dataclass(frozen=True)
class ListHit:
    entry_id: str
    source: str
    list_version: str
    list_type: str
    primary_name: str
    matched_name: str
    query: str
    match_type: str  # exact | fuzzy
    score: float  # 0-1

    def as_dict(self) -> dict:
        return {
            "entry_id": self.entry_id, "source": self.source, "list_version": self.list_version,
            "list_type": self.list_type, "primary_name": self.primary_name, "matched_name": self.matched_name,
            "query": self.query, "match_type": self.match_type, "score": self.score,
        }


@dataclass
class WatchlistSnapshot:
    """Immutable index over the active entries. `versions` maps source -> list_version."""
    entries: list[ListEntry]
    versions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Per list type: parallel arrays of normalised names and the (entry, raw name) they came from.
        self._names: dict[str, list[str]] = {t: [] for t in LIST_TYPES}
        self._owners: dict[str, list[tuple[ListEntry, str]]] = {t: [] for t in LIST_TYPES}
        self._exact: dict[str, dict[str, list[tuple[ListEntry, str]]]] = {t: {} for t in LIST_TYPES}
        for e in self.entries:
            for raw in (e.primary_name, *e.aliases):
                norm = normalize(raw)
                if not norm:
                    continue
                self._names[e.list_type].append(norm)
                self._owners[e.list_type].append((e, raw))
                self._exact[e.list_type].setdefault(norm, []).append((e, raw))
        self._scores_cache: OrderedDict[tuple[str, str], np.ndarray] = OrderedDict()
        self._cache_lock = threading.Lock()

    def _scores(self, norm: str, list_type: str) -> np.ndarray:
        """Token-sort similarity (0-100) of `norm` to every listed name, one vectorised pass, cached.
        float64 so scores equal process.extract's exactly."""
        key = (list_type, norm)
        with self._cache_lock:
            hit = self._scores_cache.get(key)
            if hit is not None:
                self._scores_cache.move_to_end(key)
                return hit
        scores = process.cdist([norm], self._names[list_type], scorer=fuzz.token_sort_ratio, dtype=np.float64)[0]
        with self._cache_lock:
            self._scores_cache[key] = scores
            if len(self._scores_cache) > SCORE_CACHE_SIZE:
                self._scores_cache.popitem(last=False)
        return scores

    def has(self, list_type: str) -> bool:
        return bool(self._names.get(list_type))

    def match(self, query: str, list_type: str, threshold: float, limit: int = 5) -> list[ListHit]:
        """Exact normalised matches first, then fuzzy (token-sort ratio) at or above threshold.
        One hit per entry (its best-scoring name), ordered by score then entry id."""
        norm = normalize(query)
        if not norm or not self.has(list_type):
            return []
        best: dict[str, ListHit] = {}
        for entry, raw in self._exact[list_type].get(norm, []):
            best[entry.id] = ListHit(entry.id, entry.source, entry.list_version, list_type, entry.primary_name,
                                     raw, query, "exact", 1.0)
        scores = self._scores(norm, list_type)
        above = np.flatnonzero(scores >= threshold * 100)
        for idx in sorted(above.tolist(), key=lambda i: (-scores[i], i)):  # process.extract's order
            entry, raw = self._owners[list_type][idx]
            s = round(float(scores[idx]) / 100.0, 4)
            if entry.id not in best or best[entry.id].score < s:
                best[entry.id] = ListHit(entry.id, entry.source, entry.list_version, list_type,
                                         entry.primary_name, raw, query, "fuzzy", s)
        return sorted(best.values(), key=lambda h: (-h.score, h.entry_id))[:limit]

    def best_score(self, query: str, list_type: str) -> float:
        """Highest similarity to any listed name (0-1), used as a graded counterparty-risk feature."""
        norm = normalize(query)
        if not norm or not self.has(list_type):
            return 0.0
        scores = self._scores(norm, list_type)
        return round(float(scores.max()) / 100.0, 4) if scores.size else 0.0
