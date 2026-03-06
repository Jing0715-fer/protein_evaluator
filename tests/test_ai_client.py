"""
Tests for AI client module
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAIClients:
    """Test cases for AI clients"""

    def test_openai_client_init(self):
        """Test OpenAI client initialization"""
        from utils.ai_client import OpenAIClient
        client = OpenAIClient(api_key="test-key", model="gpt-4o")
        assert client.model == "gpt-4o"
        assert client.api_key == "test-key"

    def test_openai_client_default_model(self):
        """Test OpenAI client default model"""
        from utils.ai_client import OpenAIClient
        client = OpenAIClient(api_key="test-key")
        # Just check that model is set
        assert client.model is not None

    def test_anthropic_client_init(self):
        """Test Anthropic client initialization"""
        from utils.ai_client import AnthropicClient
        client = AnthropicClient(api_key="test-key", model="claude-3-opus")
        assert client.model == "claude-3-opus"
        assert client.api_key == "test-key"

    def test_anthropic_client_default_model(self):
        """Test Anthropic client default model"""
        from utils.ai_client import AnthropicClient
        client = AnthropicClient(api_key="test-key")
        # Just check that model is set
        assert client.model is not None

    def test_gemini_client_init(self):
        """Test Gemini client initialization"""
        from utils.ai_client import GeminiClient
        client = GeminiClient(api_key="test-key", model="gemini-pro")
        assert client.model == "gemini-pro"
        assert client.api_key == "test-key"


class TestAIClientFactory:
    """Test cases for AI client factory"""

    def test_get_openai_client(self):
        """Test getting OpenAI client"""
        from utils.ai_client import get_ai_client

        with patch.dict(os.environ, {'AI_API_KEY': 'test-key', 'AI_MODEL': 'gpt-4o'}):
            client = get_ai_client()
            assert client is not None

    def test_get_anthropic_client(self):
        """Test getting Anthropic client"""
        from utils.ai_client import get_ai_client

        with patch.dict(os.environ, {'AI_API_KEY': 'test-key', 'AI_MODEL': 'claude-3-opus'}):
            client = get_ai_client()
            assert client is not None

    def test_get_gemini_client(self):
        """Test getting Gemini client"""
        from utils.ai_client import get_ai_client

        with patch.dict(os.environ, {'AI_API_KEY': 'test-key', 'AI_MODEL': 'gemini-pro'}):
            client = get_ai_client()
            assert client is not None
