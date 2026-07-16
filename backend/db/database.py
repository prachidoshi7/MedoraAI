"""
MedoraAI — Database Engine & Session Management
SQLite via SQLAlchemy 2.0 ORM
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Engine and session factory — initialized lazily
_engine = None
_SessionLocal = None


def get_engine(database_url: str = None):
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        if database_url is None:
            data_dir = os.environ.get("DATA_DIR", "./data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "app.db")
            database_url = f"sqlite:///{db_path}"
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
            echo=False,
        )
    return _engine


def get_session_factory(database_url: str = None):
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db():
    """
    FastAPI dependency that yields a database session.
    Usage: db: Session = Depends(get_db)
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(database_url: str = None):
    """
    Create all tables. Called once at application startup.
    Safe to call multiple times — only creates tables that don't exist.
    """
    # Import models to register them with Base.metadata
    from . import models as _  # noqa: F401
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
