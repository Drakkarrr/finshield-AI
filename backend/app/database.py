"""
FinShield AI — Database Configuration
SQLite database with SQLAlchemy ORM for production persistence.
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use test database in test environment
if os.getenv("APP_ENV") == "test":
    DATABASE_URL = "sqlite:///./test_finshield.db"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finshield.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("DEBUG", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def reset_db():
    """Drop and recreate all tables (for testing only)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
