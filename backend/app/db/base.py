"""
SQLAlchemy declarative base.
All models import from here so Alembic can discover them.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass