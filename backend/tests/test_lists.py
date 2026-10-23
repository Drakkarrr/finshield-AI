"""Tests for sanctions/PEP list provider (S2.3)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db_models import Base, PEPEntry, SanctionsEntry
from app.domain.lists import DBListProvider, MatchType
from app.domain.lists.ofac_importer import seed_sample_sanctions
from app.domain.lists.pep_seeder import seed_sample_peps


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def seeded_db(db_session):
    """Database with sample sanctions and PEP data."""
    seed_sample_sanctions(db_session)
    seed_sample_peps(db_session)
    return db_session


class TestDBListProvider:
    """Test DB-backed list provider with fuzzy matching."""

    def test_exact_sanctions_match(self, seeded_db):
        """Exact name match should return confidence 1.0."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_sanctions("AL QAEDA")
        assert len(matches) > 0
        assert matches[0].match_type == MatchType.EXACT
        assert matches[0].confidence == 1.0
        assert matches[0].entity_name == "AL QAEDA"

    def test_alias_sanctions_match(self, seeded_db):
        """Alias match should return confidence 0.95."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_sanctions("Al-Qaida")
        assert len(matches) > 0
        assert matches[0].match_type == MatchType.ALIAS
        assert matches[0].confidence == 0.95
        assert "Al-Qaida" in matches[0].match_details

    def test_fuzzy_sanctions_match(self, seeded_db):
        """Fuzzy match should return similarity-based confidence."""
        provider = DBListProvider(seeded_db, fuzzy_threshold=0.7)
        matches = provider.check_sanctions("AL QAEDA")  # Exact match
        assert len(matches) > 0
        # Should also find fuzzy matches for similar names
        fuzzy_matches = [m for m in matches if m.match_type == MatchType.FUZZY]
        # Fuzzy matches should have confidence < 1.0
        for m in fuzzy_matches:
            assert m.confidence < 1.0

    def test_sanctions_no_match(self, seeded_db):
        """Non-matching name should return empty list."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_sanctions("John Doe Regular Person")
        assert len(matches) == 0

    def test_sanctions_country_filter(self, seeded_db):
        """Country filter should exclude entries from other countries."""
        provider = DBListProvider(seeded_db)
        # PUTIN is from RU, should not match when filtering for SY
        matches = provider.check_sanctions("PUTIN, VLADIMIR", country="SY")
        assert len(matches) == 0

        # Should match when filtering for RU
        matches = provider.check_sanctions("PUTIN, VLADIMIR", country="RU")
        assert len(matches) > 0

    def test_exact_pep_match(self, seeded_db):
        """Exact PEP name match should return confidence 1.0."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_pep("TRUMP, DONALD")
        assert len(matches) > 0
        assert matches[0].match_type == MatchType.EXACT
        assert matches[0].confidence == 1.0
        assert "Former President" in matches[0].match_details

    def test_alias_pep_match(self, seeded_db):
        """PEP alias match should return confidence 0.95."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_pep("Donald J. Trump")
        assert len(matches) > 0
        assert matches[0].match_type == MatchType.ALIAS
        assert matches[0].confidence == 0.95

    def test_pep_no_match(self, seeded_db):
        """Non-matching name should return empty list for PEP."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_pep("Random Person Not a PEP")
        assert len(matches) == 0

    def test_pep_country_filter(self, seeded_db):
        """PEP country filter should work correctly."""
        provider = DBListProvider(seeded_db)
        # TRUMP is from US, should not match when filtering for CN
        matches = provider.check_pep("TRUMP, DONALD", country="CN")
        assert len(matches) == 0

        # Should match when filtering for US
        matches = provider.check_pep("TRUMP, DONALD", country="US")
        assert len(matches) > 0

    def test_match_provenance(self, seeded_db):
        """Matches should include source provenance."""
        provider = DBListProvider(seeded_db)
        matches = provider.check_sanctions("AL QAEDA")
        assert len(matches) > 0
        assert matches[0].source_provenance.startswith("sanctions_entries:")

        matches = provider.check_pep("TRUMP, DONALD")
        assert len(matches) > 0
        assert matches[0].source_provenance.startswith("pep_entries:")


class TestSeedData:
    """Test seed data functions."""

    def test_seed_sanctions(self, db_session):
        """seed_sample_sanctions should insert entries."""
        count = seed_sample_sanctions(db_session)
        assert count > 0
        entries = db_session.query(SanctionsEntry).all()
        assert len(entries) == count

    def test_seed_peps(self, db_session):
        """seed_sample_peps should insert entries."""
        count = seed_sample_peps(db_session)
        assert count > 0
        entries = db_session.query(PEPEntry).all()
        assert len(entries) == count

    def test_seed_sanctions_data_integrity(self, db_session):
        """Seeded sanctions data should have required fields."""
        seed_sample_sanctions(db_session)
        entries = db_session.query(SanctionsEntry).all()
        for entry in entries:
            assert entry.id is not None
            assert entry.name is not None
            assert entry.type is not None
            assert entry.program is not None

    def test_seed_peps_data_integrity(self, db_session):
        """Seeded PEP data should have required fields."""
        seed_sample_peps(db_session)
        entries = db_session.query(PEPEntry).all()
        for entry in entries:
            assert entry.id is not None
            assert entry.name is not None
            assert entry.position is not None
            assert entry.country is not None
            assert entry.category is not None
