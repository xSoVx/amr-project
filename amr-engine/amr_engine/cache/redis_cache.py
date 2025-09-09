"""
Redis-based caching system for AMR classification results

This module provides high-performance caching for frequently accessed
antibiogram lookup tables and classification results to reduce database
load and improve response times.
"""

import json
import hashlib
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, List, Union
from dataclasses import asdict
from functools import wraps

try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # Mock redis for development without Redis
    class redis:
        class Redis:
            def __init__(self, *args, **kwargs): pass
            def get(self, key): return None
            def set(self, key, value, ex=None): return True
            def delete(self, key): return True
            def exists(self, key): return False
            def flushdb(self): return True
            def ping(self): return True
        class RedisError(Exception): pass
        ConnectionError = RedisConnectionError = RedisError


logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis-based caching implementation for AMR classification system
    
    Features:
    - Rule lookup result caching
    - Classification result caching with TTL
    - Cache invalidation patterns
    - Connection pooling and retry logic
    - Graceful fallback when Redis unavailable
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600,  # 1 hour default TTL
        max_connections: int = 20,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5
    ):
        """
        Initialize Redis cache connection
        
        Args:
            host: Redis server hostname
            port: Redis server port
            db: Redis database number
            password: Redis authentication password
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum connection pool size
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Connection timeout in seconds
        """
        self.default_ttl = default_ttl
        self.enabled = REDIS_AVAILABLE
        
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - caching disabled")
            self._redis = None
            return
        
        try:
            # Create connection pool
            self._pool = redis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=True
            )
            
            self._redis = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            self._redis.ping()
            logger.info(f"Redis cache connected to {host}:{port}")
            
        except (RedisConnectionError, RedisError) as e:
            logger.warning(f"Redis connection failed: {e} - running without cache")
            self.enabled = False
            self._redis = None
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate consistent cache key from parameters"""
        # Sort keys for consistent hashing
        key_data = sorted(kwargs.items())
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:12]
        return f"amr:{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled or not self._redis:
            return None
        
        try:
            cached_value = self._redis.get(key)
            if cached_value:
                return json.loads(cached_value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        if not self.enabled or not self._redis:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            json_value = json.dumps(value, default=str)
            result = self._redis.set(key, json_value, ex=ttl)
            return bool(result)
        except (RedisError, TypeError) as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled or not self._redis:
            return False
        
        try:
            result = self._redis.delete(key)
            return bool(result)
        except RedisError as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.enabled or not self._redis:
            return False
        
        try:
            return bool(self._redis.exists(key))
        except RedisError as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return False
    
    def flush_all(self) -> bool:
        """Flush all cache data (use with caution)"""
        if not self.enabled or not self._redis:
            return False
        
        try:
            self._redis.flushdb()
            logger.info("Cache flushed successfully")
            return True
        except RedisError as e:
            logger.error(f"Cache flush failed: {e}")
            return False
    
    def get_rule_cache_key(self, organism: str, antibiotic: str, method: str) -> str:
        """Generate cache key for rule lookup"""
        return self._generate_key(
            "rule",
            organism=organism.lower(),
            antibiotic=antibiotic.lower(), 
            method=method.upper()
        )
    
    def get_classification_cache_key(
        self,
        organism: str,
        antibiotic: str,
        method: str,
        value: Union[float, int],
        rule_version: str
    ) -> str:
        """Generate cache key for classification result"""
        return self._generate_key(
            "classification",
            organism=organism.lower(),
            antibiotic=antibiotic.lower(),
            method=method.upper(),
            value=value,
            rule_version=rule_version
        )
    
    def cache_rule_lookup(
        self,
        organism: str,
        antibiotic: str,
        method: str,
        rule_data: Optional[Dict[str, Any]],
        ttl: int = 7200  # 2 hours for rules
    ) -> bool:
        """Cache rule lookup result"""
        key = self.get_rule_cache_key(organism, antibiotic, method)
        return self.set(key, rule_data, ttl)
    
    def get_cached_rule(
        self,
        organism: str,
        antibiotic: str,
        method: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached rule lookup result"""
        key = self.get_rule_cache_key(organism, antibiotic, method)
        return self.get(key)
    
    def cache_classification_result(
        self,
        organism: str,
        antibiotic: str,
        method: str,
        value: Union[float, int],
        rule_version: str,
        result: Dict[str, Any],
        ttl: int = 3600  # 1 hour for classifications
    ) -> bool:
        """Cache classification result"""
        key = self.get_classification_cache_key(
            organism, antibiotic, method, value, rule_version
        )
        return self.set(key, result, ttl)
    
    def get_cached_classification(
        self,
        organism: str,
        antibiotic: str,
        method: str,
        value: Union[float, int],
        rule_version: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached classification result"""
        key = self.get_classification_cache_key(
            organism, antibiotic, method, value, rule_version
        )
        return self.get(key)
    
    def invalidate_organism_cache(self, organism: str) -> int:
        """Invalidate all cache entries for specific organism"""
        if not self.enabled or not self._redis:
            return 0
        
        try:
            pattern = f"amr:*organism*{organism.lower()}*"
            keys = self._redis.keys(pattern)
            if keys:
                deleted = self._redis.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries for organism {organism}")
                return deleted
            return 0
        except RedisError as e:
            logger.warning(f"Cache invalidation failed for organism {organism}: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and health info"""
        if not self.enabled or not self._redis:
            return {"enabled": False, "status": "disabled"}
        
        try:
            info = self._redis.info()
            return {
                "enabled": True,
                "status": "connected",
                "memory_used": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except RedisError as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"enabled": True, "status": "error", "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """Calculate cache hit rate percentage"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)


class CacheManager:
    """
    High-level cache manager with decorator support
    
    Provides easy-to-use caching decorators and cache management
    utilities for the AMR classification system.
    """
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        """Initialize cache manager with Redis backend"""
        self.cache = redis_cache or RedisCache()
        self._enabled = self.cache.enabled
        logger.info(f"Cache manager initialized (enabled: {self._enabled})")
    
    def cached_rule_lookup(self, ttl: int = 7200):
        """
        Decorator for caching rule lookup functions
        
        Args:
            ttl: Time-to-live in seconds (default: 2 hours)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(organism: str, antibiotic: str, method: str, *args, **kwargs):
                if not self._enabled:
                    return func(organism, antibiotic, method, *args, **kwargs)
                
                # Try cache first
                cached_result = self.cache.get_cached_rule(organism, antibiotic, method)
                if cached_result is not None:
                    logger.debug(f"Cache hit for rule lookup: {organism}/{antibiotic}/{method}")
                    return cached_result
                
                # Cache miss - call original function
                logger.debug(f"Cache miss for rule lookup: {organism}/{antibiotic}/{method}")
                result = func(organism, antibiotic, method, *args, **kwargs)
                
                # Cache the result
                self.cache.cache_rule_lookup(organism, antibiotic, method, result, ttl)
                return result
            
            return wrapper
        return decorator
    
    def cached_classification(self, ttl: int = 3600):
        """
        Decorator for caching classification results
        
        Args:
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(classification_input, *args, **kwargs):
                if not self._enabled:
                    return func(classification_input, *args, **kwargs)
                
                # Extract cache key parameters
                organism = getattr(classification_input, 'organism', '')
                antibiotic = getattr(classification_input, 'antibiotic', '')
                method = getattr(classification_input, 'method', '')
                
                # Get measurement value
                if method == 'MIC':
                    value = getattr(classification_input, 'mic_mg_L', 0)
                else:
                    value = getattr(classification_input, 'disc_zone_mm', 0)
                
                # Assume rule version from kwargs or default
                rule_version = kwargs.get('rule_version', 'EUCAST-2025.1')
                
                # Try cache first
                cached_result = self.cache.get_cached_classification(
                    organism, antibiotic, method, value, rule_version
                )
                if cached_result is not None:
                    logger.debug(f"Cache hit for classification: {organism}/{antibiotic}")
                    return cached_result
                
                # Cache miss - call original function
                logger.debug(f"Cache miss for classification: {organism}/{antibiotic}")
                result = func(classification_input, *args, **kwargs)
                
                # Cache the result if it's a dict
                if isinstance(result, dict):
                    self.cache.cache_classification_result(
                        organism, antibiotic, method, value, rule_version, result, ttl
                    )
                elif hasattr(result, '__dict__'):
                    # Handle dataclass or object result
                    result_dict = asdict(result) if hasattr(result, '__dataclass_fields__') else result.__dict__
                    self.cache.cache_classification_result(
                        organism, antibiotic, method, value, rule_version, result_dict, ttl
                    )
                
                return result
            
            return wrapper
        return decorator
    
    def warm_cache_for_common_combinations(self, combinations: List[Dict[str, Any]]):
        """
        Pre-warm cache for common organism/antibiotic combinations
        
        Args:
            combinations: List of dicts with organism, antibiotic, method keys
        """
        if not self._enabled:
            logger.info("Cache warming skipped - cache disabled")
            return
        
        logger.info(f"Starting cache warm-up for {len(combinations)} combinations")
        warmed = 0
        
        for combo in combinations:
            try:
                organism = combo.get('organism')
                antibiotic = combo.get('antibiotic')
                method = combo.get('method')
                
                if not all([organism, antibiotic, method]):
                    continue
                
                # Check if already cached
                if not self.cache.get_cached_rule(organism, antibiotic, method):
                    # This would need to be integrated with actual rule lookup
                    # For now, just mark the attempt
                    warmed += 1
                    
            except Exception as e:
                logger.warning(f"Cache warm-up failed for {combo}: {e}")
        
        logger.info(f"Cache warm-up completed - {warmed} entries processed")
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Get comprehensive cache health information"""
        return {
            "cache_enabled": self._enabled,
            "redis_stats": self.cache.get_cache_stats(),
            "recommendations": self._get_cache_recommendations()
        }
    
    def _get_cache_recommendations(self) -> List[str]:
        """Generate cache optimization recommendations"""
        recommendations = []
        
        if not self._enabled:
            recommendations.append("Enable Redis caching for better performance")
            return recommendations
        
        stats = self.cache.get_cache_stats()
        
        if stats.get("status") != "connected":
            recommendations.append("Fix Redis connection issues")
        
        hit_rate = stats.get("hit_rate", 0)
        if hit_rate < 50:
            recommendations.append("Consider cache warm-up for common queries")
        elif hit_rate > 95:
            recommendations.append("Consider increasing cache TTL")
        
        return recommendations


# Global cache instance
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    return _global_cache_manager


def init_cache(
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None,
    **kwargs
) -> CacheManager:
    """
    Initialize global cache manager with Redis configuration
    
    Args:
        host: Redis host
        port: Redis port
        password: Redis password
        **kwargs: Additional Redis configuration
        
    Returns:
        Configured CacheManager instance
    """
    global _global_cache_manager
    redis_cache = RedisCache(host=host, port=port, password=password, **kwargs)
    _global_cache_manager = CacheManager(redis_cache)
    return _global_cache_manager