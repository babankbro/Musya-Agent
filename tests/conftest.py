"""Shared test fixtures for Agent backend tests."""
import os
import pytest
from dotenv import load_dotenv

# Load .env before any imports that use settings
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.config import get_settings
from src.db.pool import get_sync_pool, close_sync_pool, query_db


@pytest.fixture(scope="session")
def settings():
    """Get application settings."""
    return get_settings()


@pytest.fixture(scope="session")
def db_pool(settings):
    """Create and teardown sync DB pool for tests."""
    pool = get_sync_pool()
    yield pool
    close_sync_pool()


@pytest.fixture
def db_query(db_pool):
    """Provide the query_db helper."""
    return query_db
