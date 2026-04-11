"""Enterprise Database connection module simulating Teradata connections via standard SQLAlchemy."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

from config.settings import DATABASE_URL, TARGET_DB_URL

# For Teradata compatibility at work, we deliberately construct synchronous engines.
# (teradatasqlalchemy does not yet support asyncpg/asynchronous query layers natively).
source_engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, 
    pool_size=10, 
    max_overflow=20
)

# Target DB engine (Provisioning endpoint)
target_engine = create_engine(
    TARGET_DB_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SourceSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=source_engine)
TargetSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)

Base = declarative_base()

def get_source_db() -> Generator:
    """Dependency injector for Source Database connections."""
    db = SourceSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_target_db() -> Generator:
    """Dependency injector for Target Database connections."""
    db = TargetSessionLocal()
    try:
        yield db
    finally:
        db.close()
