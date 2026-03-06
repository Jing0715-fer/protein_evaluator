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
