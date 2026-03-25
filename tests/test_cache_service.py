"""
Unit tests for data cache service - simplified version.
"""

import pytest
import json
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '/Users/lijing/literature_agent-V2-claude/protein_evaluator')

from src.cache_service import (
    DataCacheService,
    CacheConfig
)
from src.models import DataCache


class TestCacheConfig:
    """Tests for CacheConfig."""
    
    def test_get_ttl_uniprot(self):
        """Test TTL for uniprot."""
        assert CacheConfig.get_ttl_days('uniprot') == 30
    
    def test_get_ttl_pdb(self):
        """Test TTL for pdb."""
        assert CacheConfig.get_ttl_days('pdb') == 30
    
    def test_get_ttl_alphafold(self):
        """Test TTL for alphafold."""
        assert CacheConfig.get_ttl_days('alphafold') == 90
    
    def test_get_ttl_blast(self):
        """Test TTL for blast."""
        assert CacheConfig.get_ttl_days('blast') == 7
    
    def test_get_ttl_unknown(self):
        """Test TTL for unknown type."""
        assert CacheConfig.get_ttl_days('unknown') == 7  # default


class TestDataCacheServiceBasics:
    """Basic tests for DataCacheService."""
    
    def test_compute_hash(self):
        """Test data hash computation."""
        service = DataCacheService()
        data = {"key": "value", "num": 123}
        
        hash1 = service._compute_hash(data)
        hash2 = service._compute_hash(data)
        
        assert len(hash1) == 64  # SHA256 hex length
        assert hash1 == hash2  # Consistent
    
    def test_compute_hash_different_order(self):
        """Test hash is consistent regardless of key order."""
        service = DataCacheService()
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        
        hash1 = service._compute_hash(data1)
        hash2 = service._compute_hash(data2)
        
        assert hash1 == hash2
    
    def test_compute_hash_changes_with_data(self):
        """Test different data produces different hash."""
        service = DataCacheService()
        data1 = {"a": 1}
        data2 = {"a": 2}
        
        hash1 = service._compute_hash(data1)
        hash2 = service._compute_hash(data2)
        
        assert hash1 != hash2
    
    def test_service_init_with_db(self):
        """Test service initialization with provided db."""
        mock_db = MagicMock()
        service = DataCacheService(db=mock_db)
        assert service.db == mock_db
        assert service._local_db is False


class TestDataCacheModel:
    """Tests for DataCache model methods."""
    
    def test_data_cache_is_expired_when_valid(self):
        """Test is_expired when cache is valid and not expired."""
        cache = DataCache(
            cache_type='uniprot',
            cache_key='P12345',
            data={'name': 'test'},
            expires_at=datetime.now() + timedelta(days=7),
            is_valid=True
        )
        assert cache.is_expired() is False
    
    def test_data_cache_is_expired_when_invalid(self):
        """Test is_expired when cache is marked invalid."""
        cache = DataCache(
            cache_type='uniprot',
            cache_key='P12345',
            data={'name': 'test'},
            expires_at=datetime.now() + timedelta(days=7),
            is_valid=False
        )
        assert cache.is_expired() is True
    
    def test_data_cache_is_expired_when_past_expiration(self):
        """Test is_expired when past expiration date."""
        cache = DataCache(
            cache_type='uniprot',
            cache_key='P12345',
            data={'name': 'test'},
            expires_at=datetime.now() - timedelta(days=1),
            is_valid=True
        )
        assert cache.is_expired() is True
    
    def test_data_cache_touch(self):
        """Test touch updates access info."""
        from datetime import datetime
        cache = DataCache(
            cache_type='uniprot',
            cache_key='P12345',
            data={'name': 'test'},
            expires_at=datetime.now() + timedelta(days=7),
            access_count=5,
            last_accessed_at=datetime.now()
        )
        old_access_time = cache.last_accessed_at
        
        import time
        time.sleep(0.01)  # Small delay to ensure time changes
        cache.touch()
        
        assert cache.access_count == 6
        assert cache.last_accessed_at >= old_access_time
    
    def test_data_cache_to_dict(self):
        """Test to_dict method."""
        cache = DataCache(
            cache_type='uniprot',
            cache_key='P12345',
            data={'name': 'test'},
            source_api='test_api',
            is_valid=True
        )
        
        result = cache.to_dict()
        
        assert result['cache_type'] == 'uniprot'
        assert result['cache_key'] == 'P12345'
        assert result['data'] == {'name': 'test'}
        assert result['source_api'] == 'test_api'
        assert result['is_valid'] is True
        assert 'created_at' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
