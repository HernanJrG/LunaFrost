"""
Database configuration and session management

Provides SQLAlchemy engine and session factory for database operations.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager

# Database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://lunafrost:change-me-in-production@postgres:5432/lunafrost_db')

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL logging during development
)

# Create session factory
SessionFactory = sessionmaker(bind=engine)

# Thread-safe scoped session
SessionLocal = scoped_session(SessionFactory)


def get_db_session():
    """Get a database session"""
    return SessionLocal()


@contextmanager
def db_session_scope():
    """
    Provide a transactional scope around a series of operations.
    
    Usage:
        with db_session_scope() as session:
            novel = Novel(title="Example")
            session.add(novel)
            # Automatically commits on success, rolls back on exception
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables"""
    from database.db_models import Base
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all tables (DANGER: Use only in development!)"""
    from database.db_models import Base
    Base.metadata.drop_all(bind=engine)
