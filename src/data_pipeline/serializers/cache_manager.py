# src/data_pipeline/serializers/cache_manager.py

import os
import pickle
import json
import hashlib
import time
from typing import Dict, Any, Optional, Union, List, Tuple
from datetime import datetime
from .base import BaseSerializer

class CacheManager(BaseSerializer):
    """Manager for caching pipeline data"""
    
    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._parameters = parameters or {
            'cache_dir': 'cache',
            'cache_ttl': 3600,  # Time-to-live in seconds (1 hour)
            'use_hash': True,   # Use hash for cache keys
            'compression': True # Use compression for cache files
        }
        
        # Create cache directory if it doesn't exist
        cache_dir = self._parameters.get('cache_dir')
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def serialize(self, data: Any, context: Dict[str, Any]) -> Any:
        """Cache data or retrieve from cache
        
        Args:
            data: Input data to cache
            context: Pipeline context with parameters:
                - cache_key: Custom cache key
                - cache_ttl: Custom TTL for this cache entry
                - cache_operation: 'save', 'load', or 'check'
                
        Returns:
            Cached data if loading, original data if saving or checking
        """
        # Get cache parameters
        cache_dir = context.get('cache_dir', self._parameters.get('cache_dir'))
        cache_ttl = context.get('cache_ttl', self._parameters.get('cache_ttl'))
        operation = context.get('cache_operation', 'save')
        
        # Generate or use provided cache key
        if 'cache_key' in context:
            cache_key = context['cache_key']
        else:
            cache_key = self._generate_cache_key(context)
        
        # Store cache key in context
        context['cached_key'] = cache_key
        
        # Handle different operations
        if operation == 'save':
            # Save data to cache
            self._save_to_cache(data, cache_key, cache_dir)
            return data
            
        elif operation == 'load':
            # Try to load data from cache
            cached_data = self._load_from_cache(cache_key, cache_dir, cache_ttl)
            if cached_data is not None:
                context['cache_hit'] = True
                return cached_data
            else:
                context['cache_hit'] = False
                return data
                
        elif operation == 'check':
            # Check if data exists in cache
            exists = self._check_cache(cache_key, cache_dir, cache_ttl)
            context['cache_exists'] = exists
            return data
            
        else:
            self.logger.warning(f"Unknown cache operation: {operation}")
            return data
    
    def _generate_cache_key(self, context: Dict[str, Any]) -> str:
        """Generate a cache key from context
        
        Args:
            context: Pipeline context
            
        Returns:
            Cache key string
        """
        # Extract key elements from context
        key_elements = {}
        
        # Include data type
        if 'data_type' in context:
            key_elements['data_type'] = context['data_type']
        
        # Include pairs
        if 'pairs' in context:
            key_elements['pairs'] = sorted(context['pairs'])
        
        # Include date range
        if 'start_date' in context:
            key_elements['start_date'] = context['start_date']
        if 'end_date' in context:
            key_elements['end_date'] = context['end_date']
        
        # Include indicators
        if 'indicators' in context:
            key_elements['indicators'] = sorted(context['indicators'])
        
        # Include other relevant parameters
        for param in ['timeframe', 'target_timeframe', 'resample_method']:
            if param in context:
                key_elements[param] = context[param]
        
        # Convert to string and hash if configured
        if self._parameters.get('use_hash', True):
            # Convert to JSON and hash
            key_str = json.dumps(key_elements, sort_keys=True)
            return hashlib.md5(key_str.encode()).hexdigest()
        else:
            # Create a filename-friendly string
            components = []
            
            # Add data type
            if 'data_type' in key_elements:
                components.append(f"{key_elements['data_type']}")
            
            # Add pairs
            if 'pairs' in key_elements:
                components.append(f"pairs-{'-'.join(key_elements['pairs'])}")
            
            # Add date range
            date_component = ""
            if 'start_date' in key_elements:
                date_component += f"from-{key_elements['start_date']}"
            if 'end_date' in key_elements:
                date_component += f"to-{key_elements['end_date']}"
            
            if date_component:
                components.append(date_component)
            
            # Create key from components
            return "_".join(components)
    
    def _get_cache_path(self, cache_key: str, cache_dir: str) -> str:
        """Get the cache file path
        
        Args:
            cache_key: Cache key
            cache_dir: Cache directory
            
        Returns:
            Cache file path
        """
        return os.path.join(cache_dir, f"{cache_key}.cache")
    
    def _save_to_cache(self, data: Any, cache_key: str, cache_dir: str) -> bool:
        """Save data to cache
        
        Args:
            data: Data to cache
            cache_key: Cache key
            cache_dir: Cache directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_path = self._get_cache_path(cache_key, cache_dir)
            
            # Create metadata
            metadata = {
                'timestamp': time.time(),
                'key': cache_key,
                'created': datetime.now().isoformat()
            }
            
            # Create cache entry with data and metadata
            cache_entry = {
                'metadata': metadata,
                'data': data
            }
            
            # Save to file
            with open(cache_path, 'wb') as f:
                # Use pickle with highest protocol for better compression
                pickle.dump(cache_entry, f, protocol=pickle.HIGHEST_PROTOCOL)
                
            self.logger.info(f"Saved data to cache: {cache_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving to cache: {str(e)}")
            return False
    
    def _load_from_cache(self, cache_key: str, cache_dir: str, ttl: int) -> Optional[Any]:
        """Load data from cache
        
        Args:
            cache_key: Cache key
            cache_dir: Cache directory
            ttl: Time-to-live in seconds
            
        Returns:
            Cached data if valid, None otherwise
        """
        cache_path = self._get_cache_path(cache_key, cache_dir)
        
        # Check if cache file exists
        if not os.path.exists(cache_path):
            self.logger.debug(f"Cache file not found: {cache_path}")
            return None
        
        try:
            # Load cache entry
            with open(cache_path, 'rb') as f:
                cache_entry = pickle.load(f)
            
            # Get metadata and data
            metadata = cache_entry.get('metadata', {})
            data = cache_entry.get('data')
            
            # Check TTL
            timestamp = metadata.get('timestamp', 0)
            age = time.time() - timestamp
            
            if age > ttl:
                self.logger.debug(f"Cache expired: {cache_path} (age: {age:.1f}s, ttl: {ttl}s)")
                return None
            
            self.logger.info(f"Loaded data from cache: {cache_path}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error loading from cache: {str(e)}")
            return None
    
    def _check_cache(self, cache_key: str, cache_dir: str, ttl: int) -> bool:
        """Check if valid cache entry exists
        
        Args:
            cache_key: Cache key
            cache_dir: Cache directory
            ttl: Time-to-live in seconds
            
        Returns:
            True if valid cache entry exists, False otherwise
        """
        cache_path = self._get_cache_path(cache_key, cache_dir)
        
        # Check if cache file exists
        if not os.path.exists(cache_path):
            return False
        
        try:
            # Load metadata only
            with open(cache_path, 'rb') as f:
                # Read just the first part to get metadata
                cache_entry = pickle.load(f)
            
            # Get timestamp
            metadata = cache_entry.get('metadata', {})
            timestamp = metadata.get('timestamp', 0)
            
            # Check TTL
            age = time.time() - timestamp
            return age <= ttl
            
        except Exception as e:
            self.logger.error(f"Error checking cache: {str(e)}")
            return False
    
    def clear_cache(self, older_than: Optional[int] = None) -> int:
        """Clear cache files
        
        Args:
            older_than: Only clear files older than this many seconds
            
        Returns:
            Number of files cleared
        """
        cache_dir = self._parameters.get('cache_dir')
        if not cache_dir or not os.path.exists(cache_dir):
            return 0
        
        count = 0
        current_time = time.time()
        
        for filename in os.listdir(cache_dir):
            if filename.endswith('.cache'):
                filepath = os.path.join(cache_dir, filename)
                
                # Check file age if specified
                if older_than is not None:
                    file_mtime = os.path.getmtime(filepath)
                    age = current_time - file_mtime
                    
                    if age <= older_than:
                        continue
                
                # Remove file
                try:
                    os.remove(filepath)
                    count += 1
                except Exception as e:
                    self.logger.error(f"Error removing cache file: {str(e)}")
        
        self.logger.info(f"Cleared {count} cache files from {cache_dir}")
        return count