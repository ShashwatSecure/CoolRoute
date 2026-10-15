"""Database engine configuration."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy engine configured by ``DB_CONN``."""
    load_dotenv()
    database_url = os.getenv("DB_CONN")
    if not database_url:
        raise RuntimeError("DB_CONN is not set; configure it in .env")
    return create_engine(database_url, pool_pre_ping=True)
