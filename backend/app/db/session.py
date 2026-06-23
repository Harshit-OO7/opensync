"""
Shared database session factory.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Build connection args for asyncpg
connect_args = {}
if "render.com" in settings.DATABASE_URL or "amazonaws" in settings.DATABASE_URL:
    connect_args = {
        "server_settings": {"jit": "off"},
        "timeout": 60,
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)