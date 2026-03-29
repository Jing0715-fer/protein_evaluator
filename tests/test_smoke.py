"""
Smoke tests for Protein Evaluator Application
Quick tests to verify basic functionality
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.smoke
class TestAppCreation:
    """Smoke tests for Flask app creation"""

    def test_create_app(self):
        """Test Flask app can be created"""
        from app import create_app
        app = create_app()
        assert app is not None
        assert app.name == 'app'

    def test_app_has_secret_key(self):
        """Test app has SECRET_KEY configured"""
        from app import create_app
        with patch.dict(os.environ, {'SECRET_KEY': 'test-secret-key'}):
            app = create_app()
            assert 'SECRET_KEY' in app.config
            assert app.config['SECRET_KEY'] == 'test-secret-key'

    def test_app_debug_config(self, monkeypatch):
        """Test app debug configuration via explicit debug parameter.

        Uses monkeypatch instead of importlib.reload() to avoid mutating
        global module state that other tests depend on.
        """
        from app import create_app

        # Test explicit debug=True parameter
        app = create_app(debug=True)
        assert app.config['DEBUG'] is True

        # Test explicit debug=False parameter
        app = create_app(debug=False)
        assert app.config['DEBUG'] is False

        # Test environment-variable-driven DEBUG=true
        monkeypatch.setenv('DEBUG', 'true', raising=False)
        app = create_app()  # no explicit override — should read env
        assert app.config['DEBUG'] is True

        # Test environment-variable-driven DEBUG=false
        monkeypatch.setenv('DEBUG', 'false', raising=False)
        app = create_app()
        assert app.config['DEBUG'] is False


@pytest.mark.smoke
class TestHealthEndpoint:
    """Smoke tests for health check endpoint"""

    def test_health_endpoint(self):
        """Test health endpoint returns ok"""
        from app import create_app
        app = create_app()
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'ok'
            assert data['service'] == 'protein-evaluator'

    def test_index_page(self):
        """Test index page loads"""
        from app import create_app
        app = create_app()
        with app.test_client() as client:
            response = client.get('/')
            # Should return HTML or redirect
            assert response.status_code in [200, 302]


@pytest.mark.smoke
class TestConfig:
    """Smoke tests for configuration"""

    def test_config_has_required_vars(self):
        """Test config has required variables"""
        import config
        required_vars = ['AI_MODEL', 'AI_TEMPERATURE', 'AI_MAX_TOKENS',
                        'DATABASE_PATH', 'HOST', 'PORT']
        for var in required_vars:
            assert hasattr(config, var), f"Missing config variable: {var}"

    def test_database_path_is_set(self):
        """Test database path is configured"""
        import config
        assert config.DATABASE_PATH is not None
        assert isinstance(config.DATABASE_PATH, str)
        assert len(config.DATABASE_PATH) > 0

    def test_ai_model_default(self):
        """Test AI model has default value"""
        import config
        assert config.AI_MODEL is not None
        assert isinstance(config.AI_MODEL, str)


@pytest.mark.smoke
class TestCoreModules:
    """Smoke tests for core modules"""

    def test_uniprot_client_import(self):
        """Test UniProt client can be imported"""
        from core.uniprot_client import UniProtAPIClient, UniProtEntry
        assert UniProtAPIClient is not None
        assert UniProtEntry is not None

    def test_pdb_fetcher_import(self):
        """Test PDB fetcher can be imported"""
        from core.pdb_fetcher import PDBFetcher
        assert PDBFetcher is not None

    def test_ai_client_import(self):
        """Test AI client can be imported"""
        from utils.ai_client import OpenAIClient, AnthropicClient, GeminiClient
        assert OpenAIClient is not None
        assert AnthropicClient is not None
        assert GeminiClient is not None

    def test_uniprot_client_creation(self):
        """Test UniProt client can be instantiated"""
        from core.uniprot_client import UniProtAPIClient
        client = UniProtAPIClient(timeout=10)
        assert client is not None
        assert client.timeout == 10

    def test_pdb_fetcher_creation(self):
        """Test PDB fetcher can be instantiated"""
        from core.pdb_fetcher import PDBFetcher
        fetcher = PDBFetcher(timeout=10)
        assert fetcher is not None
        assert fetcher.timeout == 10


@pytest.mark.smoke
class TestUtilsModules:
    """Smoke tests for utility modules"""

    def test_exceptions_import(self):
        """Test exceptions module can be imported"""
        from utils.exceptions import ProteinEvaluationError
        assert ProteinEvaluationError is not None

    def test_api_utils_import(self):
        """Test API utils can be imported"""
        from utils.api_utils import retry_with_backoff
        assert retry_with_backoff is not None
