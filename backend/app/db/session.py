"""
Database utilities - using sync psycopg2 for Render compatibility.
"""

import psycopg2
import psycopg2.extras
from app.core.config import settings

def get_sync_connection():
    """Get a synchronous psycopg2 connection."""
    # Convert asyncpg URL to psycopg2 URL
    db_url = settings.DATABASE_URL
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.replace("?ssl=true", "?sslmode=require")
    db_url = db_url.replace("&prepared_statement_cache_size=0", "")
    return psycopg2.connect(db_url)


def execute_query(query: str, params: dict = None) -> list:
    """Execute a SELECT query and return results as list of dicts."""
    conn = get_sync_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        results = cur.fetchall()
        return [dict(r) for r in results]
    finally:
        conn.close()


def execute_write(query: str, params: dict = None):
    """Execute an INSERT/UPDATE query."""
    conn = get_sync_connection()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(query, params)
    finally:
        conn.close()


# Keep AsyncSessionLocal for backward compatibility
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)