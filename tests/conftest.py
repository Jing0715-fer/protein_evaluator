"""
Pytest configuration and fixtures for Protein Evaluator tests
"""
import os
import sys
import pytest
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_env():
    """Set up mock environment variables for testing"""
    old_env = os.environ.copy()
    os.environ['AI_API_KEY'] = 'test-api-key'
    os.environ['AI_MODEL'] = 'gpt-4o'
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture(autouse=True, scope="function")
def _reset_cache_service():
    """Reset the cache service singleton after every test.

    This fixture runs automatically for all tests. It ensures that any
    locally-created DB session inside the singleton DataCacheService is
    closed and the singleton is discarded, providing test isolation.
    """
    from src.cache_service import reset_cache_service
    yield
    reset_cache_service()
