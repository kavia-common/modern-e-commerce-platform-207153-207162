import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _env(name: str) -> Optional[str]:
    """Return an environment variable if present and non-empty."""
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_database_url() -> str:
    """
    Build a PostgreSQL connection URL from environment variables.

    Prefers a full URL in POSTGRES_URL if provided. Otherwise composes:

      postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}

    Defaults are aligned to ecommerce_database/db_connection.txt:
      psql postgresql://appuser:dbuser123@localhost:5000/myapp

    Env vars supported:
      - POSTGRES_URL (full connection string)
      - POSTGRES_USER
      - POSTGRES_PASSWORD
      - POSTGRES_DB
      - POSTGRES_PORT
      - POSTGRES_HOST  (optional; defaults to 'localhost')
    """
    # Prefer full URL if the environment provides it.
    postgres_url = _env("POSTGRES_URL")
    if postgres_url:
        # Accept plain postgresql://... and SQLAlchemy dialect URLs.
        if postgres_url.startswith("postgresql://") or postgres_url.startswith("postgresql+psycopg://"):
            return postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return postgres_url

    user = _env("POSTGRES_USER") or "appuser"
    password = _env("POSTGRES_PASSWORD") or "dbuser123"
    db = _env("POSTGRES_DB") or "myapp"
    port = _env("POSTGRES_PORT") or "5000"
    host = _env("POSTGRES_HOST") or "localhost"

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


DATABASE_URL = build_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for ORM models."""


# PUBLIC_INTERFACE
def get_db() -> Generator:
    """FastAPI dependency that provides a SQLAlchemy session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
