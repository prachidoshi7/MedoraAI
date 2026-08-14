"""
MedoraAI — Database Engine & Session Management
SQLite via SQLAlchemy 2.0 ORM
"""

from sqlalchemy import create_engine, inspect, text
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
    _apply_compatibility_migrations(engine)


def _apply_compatibility_migrations(engine) -> None:
    """Add v2 columns to an existing hackathon SQLite database in place.

    ``create_all`` deliberately does not alter existing tables.  Keeping these
    small additive migrations here lets an existing demo database boot after the
    role/workflow redesign without requiring users to delete their scans.
    """
    if engine.dialect.name != "sqlite":
        return

    additions = {
        "users": {
            "role": "VARCHAR(20) NOT NULL DEFAULT 'patient'",
            "full_name": "VARCHAR(150) DEFAULT ''",
            "email": "VARCHAR(150) DEFAULT ''",
            "phone": "VARCHAR(20) DEFAULT ''",
            "specialization": "VARCHAR(100) DEFAULT ''",
            "qualification": "VARCHAR(150) DEFAULT ''",
            "department_id": "INTEGER REFERENCES departments(id)",
            "avatar_url": "VARCHAR(500) DEFAULT ''",
            "is_active": "BOOLEAN DEFAULT 1",
            "is_available": "BOOLEAN DEFAULT 1",
            "availability_note": "VARCHAR(250) DEFAULT ''",
        },
        "scans": {
            "lab_tech_id": "INTEGER REFERENCES users(id)",
        },
        "reports": {
            "reviewed_by_doctor_id": "INTEGER REFERENCES users(id)",
            "doctor_notes": "TEXT DEFAULT ''",
            "doctor_approved_at": "DATETIME",
            "forwarded_to_doctor_id": "INTEGER REFERENCES users(id)",
        },
        "pharmacy_inventory": {
            "expiry_date": "DATE",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}')
                    )
