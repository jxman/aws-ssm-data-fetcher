"""Intelligent multi-tier caching system supporting local, Lambda, and S3 caching."""

import os
import pickle
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path


class CacheManager:
    """Multi-tier caching manager with Lambda and S3 support."""
    
    def __init__(self, config):
        """Initialize cache manager from Config object.
        
        Args:
            config: Config object with cache settings
        """
        from .config import Config  # Avoid circular imports
        
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.cache_hours = config.cache_hours
        self.cache_enabled = config.cache_enabled and config.cache_hours > 0
        
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
        # Initialize in-memory cache
        self._memory_cache = {}
        
        # Initialize S3 client for Lambda caching if configured
        self.s3_client = None
        if hasattr(config, 's3_cache_bucket') and config.s3_cache_bucket:
            try:
                import boto3
                self.s3_client = boto3.client('s3')
            except ImportError:
                pass  # boto3 not available
        
        self.logger = logging.getLogger(__name__)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        safe_key = key.replace('/', '_').replace(':', '_')
        return self.cache_dir / f"{safe_key}.pkl"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid based on TTL."""
        if not cache_path.exists():
            return False
        
        # Get file modification time
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = mtime + timedelta(hours=self.cache_hours)
        
        return datetime.now() < expiry_time
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache with multi-tier fallback.
        
        Cache hierarchy:
        1. Memory cache (fastest)
        2. Local file cache
        3. S3 cache (for Lambda cross-invocation)
        
        Args:
            key: Cache key
            
        Returns:
            Cached data if valid, None otherwise
        """
        if not self.cache_enabled:
            return None
            
        # Tier 1: Memory cache (fastest)
        if key in self._memory_cache:
            self.logger.debug(f"Cache hit (memory): {key}")
            return self._memory_cache[key]
        
        # Tier 2: Local file cache
        local_data = self._get_from_local(key)
        if local_data is not None:
            self._memory_cache[key] = local_data  # Promote to memory
            self.logger.debug(f"Cache hit (local): {key}")
            return local_data
            
        # Tier 3: S3 cache (for Lambda cross-invocation)
        if self.s3_client:
            s3_data = self._get_from_s3(key)
            if s3_data is not None:
                self._set_to_local(key, s3_data)  # Cache locally
                self._memory_cache[key] = s3_data  # Cache in memory
                self.logger.debug(f"Cache hit (S3): {key}")
                return s3_data
        
        return None
    
    def set(self, key: str, data: Any) -> bool:
        """Set data in cache across all tiers.
        
        Args:
            key: Cache key
            data: Data to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.cache_enabled:
            return False
            
        # Always cache in memory
        self._memory_cache[key] = data
        
        # Cache locally
        success = self._set_to_local(key, data)
        
        # Cache in S3 if available
        if self.s3_client:
            self._set_to_s3(key, data)
            
        return success
    
    def _get_from_local(self, key: str) -> Optional[Any]:
        """Get from local file system."""
        cache_path = self._get_cache_path(key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load local cache {key}: {e}")
                cache_path.unlink(missing_ok=True)
        
        return None
    
    def _set_to_local(self, key: str, data: Any) -> bool:
        """Set to local file system."""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug(f"Saved to local cache: {key}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save local cache {key}: {e}")
            return False
    
    def _get_from_s3(self, key: str) -> Optional[Any]:
        """Get from S3 cache."""
        if not self.s3_client or not self.config.s3_cache_bucket:
            return None
            
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.s3_cache_bucket,
                Key=f"cache/{key}.json"
            )
            
            # Check TTL
            last_modified = response['LastModified'].replace(tzinfo=None)
            if datetime.utcnow() - last_modified > timedelta(hours=self.cache_hours):
                return None
            
            return json.loads(response['Body'].read())
        except Exception as e:
            self.logger.debug(f"Failed to get S3 cache {key}: {e}")
            return None
    
    def _set_to_s3(self, key: str, data: Any) -> bool:
        """Set to S3 cache."""
        if not self.s3_client or not self.config.s3_cache_bucket:
            return False
            
        try:
            self.s3_client.put_object(
                Bucket=self.config.s3_cache_bucket,
                Key=f"cache/{key}.json",
                Body=json.dumps(data, default=str),
                Metadata={'cached_at': datetime.utcnow().isoformat()}
            )
            self.logger.debug(f"Saved to S3 cache: {key}")
            return True
        except Exception as e:
            self.logger.debug(f"Failed to save S3 cache {key}: {e}")
            return False
    
    def clear(self, key: Optional[str] = None) -> int:
        """Clear cache entries. If key is None, clear all cache."""
        if key:
            # Clear specific cache entry
            cleared = 0
            
            # Clear from memory
            if key in self._memory_cache:
                del self._memory_cache[key]
                cleared += 1
            
            # Clear from local
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                    cleared += 1
                except Exception as e:
                    self.logger.error(f"Failed to clear local cache {key}: {e}")
            
            # Clear from S3 (optional, as it will expire naturally)
            if self.s3_client and self.config.s3_cache_bucket:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.config.s3_cache_bucket,
                        Key=f"cache/{key}.json"
                    )
                    cleared += 1
                except Exception:
                    pass  # S3 deletion is optional
                    
            return cleared
        else:
            # Clear all caches
            return self.clear_all()
    
    def clear_all(self) -> int:
        """Clear all caches across all tiers.
        
        Returns:
            Number of items cleared
        """
        cleared = 0
        
        # Clear memory cache
        cleared += len(self._memory_cache)
        self._memory_cache.clear()
        
        # Clear local cache
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                    cleared += 1
                except Exception as e:
                    self.logger.error(f"Failed to clear cache file {cache_file}: {e}")
        
        self.logger.info(f"Cleared {cleared} cache entries")
        return cleared
    
    def get_info(self) -> Dict[str, Any]:
        """Get cache information and statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.cache_dir.exists():
            return {
                'cache_dir': str(self.cache_dir),
                'ttl_hours': self.cache_hours,
                'total_files': 0,
                'total_size_kb': 0.0,
                'files': []
            }
        
        files = []
        total_size = 0
        
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                stat = cache_file.stat()
                size_kb = stat.st_size / 1024
                created = datetime.fromtimestamp(stat.st_mtime)
                expires = created + timedelta(hours=self.cache_hours)
                valid = self._is_cache_valid(cache_file)
                
                files.append({
                    'file': cache_file.name,
                    'size_kb': f'{size_kb:.2f}',
                    'created': created.isoformat(),
                    'expires': expires.isoformat(),
                    'valid': valid
                })
                
                total_size += size_kb
                
            except Exception as e:
                self.logger.error(f"Error getting info for {cache_file}: {e}")
        
        return {
            'cache_dir': str(self.cache_dir),
            'ttl_hours': self.cache_hours,
            'total_files': len(files),
            'total_size_kb': f'{total_size:.2f}',
            'files': files
        }
    
    # Backward compatibility methods to match original script API
    def _load_from_cache(self, key: str) -> Optional[Any]:
        """Legacy method name - use get() instead."""
        return self.get(key)
    
    def _save_to_cache(self, key: str, data: Any) -> None:
        """Legacy method name - use set() instead."""
        self.set(key, data)
    
    def clear_cache(self, key: Optional[str] = None) -> int:
        """Legacy method name - use clear() instead."""
        return self.clear(key)
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Legacy method name - use get_info() instead."""
        return self.get_info()