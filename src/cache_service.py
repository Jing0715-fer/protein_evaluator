"""
Data cache service for API response caching.
Avoids repeated API calls by caching responses with expiration.
"""

import logging
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.models import DataCache
from src.database import get_session

logger = logging.getLogger(__name__)


class CacheConfig:
    """Cache expiration configuration."""
    
    # 默认缓存过期时间 (天)
    DEFAULT_TTL_DAYS = 7
    
    # 按数据类型的过期时间配置
    TTL_CONFIG = {
        'uniprot': 30,      # UniProt 数据相对稳定
        'pdb': 30,          # PDB 数据稳定
        'alphafold': 90,    # AlphaFold 模型很少更新
        'emdb': 30,         # EMDB 数据稳定
        'blast': 7,         # BLAST 结果可能变化
        'pubmed': 30,       # PubMed 摘要不常变化
        'default': 7
    }
    
    @classmethod
    def get_ttl_days(cls, cache_type: str) -> int:
        """Get TTL for cache type."""
        return cls.TTL_CONFIG.get(cache_type, cls.DEFAULT_TTL_DAYS)


class DataCacheService:
    """Service for managing API data cache."""
    
    def __init__(self, db: Session = None):
        """
        Initialize cache service.
        
        Args:
            db: Database session (optional, will create if not provided)
        """
        self.db = db
        self._local_db = False
        if db is None:
            self.db = get_session()
            self._local_db = True
        logger.debug("DataCacheService initialized")
    
    def __del__(self):
        """Cleanup database session if we created it."""
        if self._local_db and self.db:
            try:
                self.db.close()
            except Exception:
                pass
    
    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute hash of data for change detection."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def get(self, cache_type: str, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data.
        
        Args:
            cache_type: Type of cached data (uniprot, pdb, etc.)
            cache_key: Cache key (ID or query)
            
        Returns:
            Cached data dict or None if not found/expired
        """
        try:
            cache_entry = self.db.query(DataCache).filter(
                DataCache.cache_type == cache_type,
                DataCache.cache_key == cache_key,
                DataCache.is_valid == True
            ).first()
            
            if not cache_entry:
                logger.debug(f"Cache miss: {cache_type}/{cache_key}")
                return None
            
            if cache_entry.is_expired():
                logger.debug(f"Cache expired: {cache_type}/{cache_key}")
                return None
            
            # Update access stats
            cache_entry.touch()
            self.db.commit()
            
            logger.debug(f"Cache hit: {cache_type}/{cache_key}")
            return cache_entry.data
            
        except Exception as e:
            logger.error(f"Error reading cache {cache_type}/{cache_key}: {e}")
            return None
    
    def set(self, cache_type: str, cache_key: str, data: Dict[str, Any],
            source_api: str = None, api_version: str = None,
            ttl_days: int = None) -> bool:
        """
        Set cached data.
        
        Args:
            cache_type: Type of data
            cache_key: Cache key
            data: Data to cache
            source_api: Source API name
            api_version: API version
            ttl_days: Custom TTL (uses default if not specified)
            
        Returns:
            True if successful
        """
        try:
            # Calculate expiration
            if ttl_days is None:
                ttl_days = CacheConfig.get_ttl_days(cache_type)
            expires_at = datetime.now() + timedelta(days=ttl_days)
            
            # Check if entry exists
            existing = self.db.query(DataCache).filter(
                DataCache.cache_type == cache_type,
                DataCache.cache_key == cache_key
            ).first()
            
            data_hash = self._compute_hash(data)
            
            if existing:
                # Update existing entry
                existing.data = data
                existing.data_hash = data_hash
                existing.source_api = source_api
                existing.api_version = api_version
                existing.expires_at = expires_at
                existing.is_valid = True
                existing.last_accessed_at = datetime.now()
                existing.access_count = 1
            else:
                # Create new entry
                new_entry = DataCache(
                    cache_type=cache_type,
                    cache_key=cache_key,
                    data=data,
                    data_hash=data_hash,
                    source_api=source_api,
                    api_version=api_version,
                    expires_at=expires_at
                )
                self.db.add(new_entry)
            
            self.db.commit()
            logger.debug(f"Cache set: {cache_type}/{cache_key} (expires: {expires_at.date()})")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error setting cache {cache_type}/{cache_key}: {e}")
            return False
    
    def invalidate(self, cache_type: str, cache_key: str) -> bool:
        """
        Mark cache entry as invalid.
        
        Args:
            cache_type: Cache type
            cache_key: Cache key
            
        Returns:
            True if successful
        """
        try:
            entry = self.db.query(DataCache).filter(
                DataCache.cache_type == cache_type,
                DataCache.cache_key == cache_key
            ).first()
            
            if entry:
                entry.is_valid = False
                self.db.commit()
                logger.debug(f"Cache invalidated: {cache_type}/{cache_key}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating cache {cache_type}/{cache_key}: {e}")
            return False
    
    def invalidate_by_type(self, cache_type: str) -> int:
        """
        Invalidate all entries of a specific type.
        
        Args:
            cache_type: Cache type to invalidate
            
        Returns:
            Number of entries invalidated
        """
        try:
            entries = self.db.query(DataCache).filter(
                DataCache.cache_type == cache_type,
                DataCache.is_valid == True
            ).all()
            
            count = 0
            for entry in entries:
                entry.is_valid = False
                count += 1
            
            self.db.commit()
            logger.info(f"Invalidated {count} cache entries of type {cache_type}")
            return count
            
        except Exception as e:
            logger.error(f"Error invalidating cache type {cache_type}: {e}")
            return 0
    
    def delete_expired(self) -> int:
        """
        Delete expired cache entries.
        
        Returns:
            Number of entries deleted
        """
        try:
            now = datetime.now()
            entries = self.db.query(DataCache).filter(
                DataCache.expires_at < now
            ).all()
            
            count = len(entries)
            for entry in entries:
                self.db.delete(entry)
            
            self.db.commit()
            logger.info(f"Deleted {count} expired cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Error deleting expired cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        try:
            total = self.db.query(DataCache).count()
            valid = self.db.query(DataCache).filter(DataCache.is_valid == True).count()
            expired = self.db.query(DataCache).filter(
                DataCache.is_valid == True,
                DataCache.expires_at < datetime.now()
            ).count()
            
            # Stats by type (batch query instead of loop)
            type_stats = {}
            type_counts = self.db.query(
                DataCache.cache_type,
                self.db.func.count(DataCache.id)
            ).group_by(DataCache.cache_type).all()
            for cache_type, count in type_counts:
                if cache_type != 'default':
                    type_stats[cache_type] = count
            
            return {
                'total_entries': total,
                'valid_entries': valid,
                'expired_entries': expired,
                'by_type': type_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful
        """
        try:
            self.db.query(DataCache).delete()
            self.db.commit()
            logger.info("All cache entries cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False


# Convenience functions
_cache_service = None

def get_cache_service() -> DataCacheService:
    """Get singleton cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = DataCacheService()
    return _cache_service


def cache_get(cache_type: str, cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached data (convenience function)."""
    return get_cache_service().get(cache_type, cache_key)


def cache_set(cache_type: str, cache_key: str, data: Dict[str, Any],
              source_api: str = None, ttl_days: int = None) -> bool:
    """Set cached data (convenience function)."""
    return get_cache_service().set(
        cache_type, cache_key, data,
        source_api=source_api, ttl_days=ttl_days
    )


def cache_delete(cache_type: str, cache_key: str) -> bool:
    """Delete cache entry (convenience function)."""
    return get_cache_service().invalidate(cache_type, cache_key)
