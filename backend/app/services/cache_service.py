"""
Redis-based caching service for performance optimization.

This module provides comprehensive caching for conversations,
AI responses, tool results, and other frequently accessed data.
"""

import json
import pickle
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as redis
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import settings
from backend.app.core.exceptions import ConfigurationError


class CacheConfig(BaseModel):
    """Cache configuration with validation."""

    redis_url: str = Field(..., description="Redis connection URL")
    default_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default TTL in seconds",
    )
    max_connections: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum Redis connections",
    )
    connection_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Connection timeout",
    )
    retry_attempts: int = Field(default=3, ge=1, le=10, description="Retry attempts")
    enable_compression: bool = Field(
        default=True,
        description="Enable data compression",
    )
    cache_prefix: str = Field(default="convosphere", description="Cache key prefix")

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL."""
        if not v or not v.strip():
            raise ValueError("Redis URL cannot be empty")
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v.strip()

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class CacheKey(BaseModel):
    """Cache key with namespace and validation."""

    namespace: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Cache namespace",
    )
    key: str = Field(..., min_length=1, max_length=200, description="Cache key")
    version: str = Field(default="v1", description="Cache version")

    def to_string(self) -> str:
        """Convert to Redis key string."""
        return f"{self.namespace}:{self.version}:{self.key}"

    @classmethod
    def from_string(cls, key_string: str) -> "CacheKey":
        """Create from Redis key string."""
        parts = key_string.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid cache key format: {key_string}")
        return cls(namespace=parts[0], version=parts[1], key=parts[2])

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class CacheEntry(BaseModel):
    """Cache entry with metadata."""

    data: Any = Field(..., description="Cached data")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Creation timestamp",
    )
    expires_at: datetime | None = Field(None, description="Expiration timestamp")
    access_count: int = Field(default=0, ge=0, description="Access count")
    last_accessed: datetime = Field(
        default_factory=datetime.now,
        description="Last access timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def increment_access(self) -> None:
        """Increment access count and update last accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now(UTC)

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class CacheService:
    """Redis-based caching service with comprehensive features."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.redis_client: redis.Redis | None = None
        self.connection_pool: redis.ConnectionPool | None = None
        self._initialized = False

        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }

    async def initialize(self) -> None:
        """Initialize Redis connection with graceful degradation."""
        try:
            # Use the global Redis client if available
            from backend.app.core.redis_client import get_redis, is_redis_available

            if is_redis_available():
                self.redis_client = await get_redis()
                if self.redis_client is not None:
                    self._initialized = True
                    logger.info("Cache service initialized with global Redis client")
                    return

            # Fallback to creating our own connection if global client is not available
            logger.warning(
                "Global Redis client not available, creating fallback connection",
            )

            # Create connection pool
            self.connection_pool = redis.ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.max_connections,
                socket_connect_timeout=self.config.connection_timeout,
                socket_timeout=self.config.connection_timeout,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Create Redis client
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)

            # Test connection
            await self.redis_client.ping()

            self._initialized = True
            logger.info("Cache service initialized with fallback connection")

        except Exception as e:
            logger.warning(f"Failed to initialize cache service: {e}")
            self._initialized = False
            # Don't raise exception - allow application to continue without caching

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()
        logger.info("Cache service closed")

    def _ensure_initialized(self) -> None:
        """Ensure cache service is initialized."""
        if not self._initialized:
            raise ConfigurationError("Cache service not initialized")

    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for storage."""
        try:
            if self.config.enable_compression:
                # Use pickle for complex objects with compression
                return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            # Use JSON for simple objects
            if isinstance(data, dict | list | str | int | float | bool | type(None)):
                return json.dumps(data, default=str).encode("utf-8")
            return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            logger.error(f"Failed to serialize data: {e}")
            raise

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data from storage."""
        try:
            if self.config.enable_compression:
                # Try pickle first (safe for internal cache data)
                try:
                    return pickle.loads(data)
                except (
                    pickle.UnpicklingError,
                    AttributeError,
                    EOFError,
                    ImportError,
                    IndexError,
                ):
                    # Fallback to JSON if pickle fails
                    return json.loads(data.decode("utf-8"))
            # Try JSON first, fallback to pickle
            try:
                return json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fallback to pickle (safe for internal cache data)
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize data: {e}")
            raise

    async def get(self, cache_key: CacheKey) -> Any | None:
        """
        Get data from cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        self._ensure_initialized()

        try:
            key_string = cache_key.to_string()
            data = await self.redis_client.get(key_string)

            if data is None:
                self.stats["misses"] += 1
                return None

            # Deserialize data
            cached_entry = self._deserialize_data(data)

            # Check if expired
            if isinstance(cached_entry, dict) and "expires_at" in cached_entry:
                expires_at = datetime.fromisoformat(cached_entry["expires_at"])
                if datetime.now(UTC) > expires_at:
                    await self.delete(cache_key)
                    self.stats["misses"] += 1
                    return None

            # Update access statistics
            if isinstance(cached_entry, dict):
                cached_entry["access_count"] = cached_entry.get("access_count", 0) + 1
                cached_entry["last_accessed"] = datetime.now(UTC).isoformat()
                # Update in cache
                await self.redis_client.setex(
                    key_string,
                    self.config.default_ttl,
                    self._serialize_data(cached_entry),
                )

            self.stats["hits"] += 1
            return (
                cached_entry.get("data")
                if isinstance(cached_entry, dict)
                else cached_entry
            )

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        cache_key: CacheKey,
        data: Any,
        ttl: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Set data in cache.

        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time to live in seconds
            metadata: Additional metadata

        Returns:
            True if successful
        """
        self._ensure_initialized()

        try:
            key_string = cache_key.to_string()
            ttl = ttl or self.config.default_ttl

            # Create cache entry
            entry = CacheEntry(
                data=data,
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
                metadata=metadata or {},
            )

            # Serialize and store
            serialized_data = self._serialize_data(entry.dict())
            await self.redis_client.setex(key_string, ttl, serialized_data)

            self.stats["sets"] += 1
            return True

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, cache_key: CacheKey) -> bool:
        """
        Delete data from cache.

        Args:
            cache_key: Cache key

        Returns:
            True if successful
        """
        self._ensure_initialized()

        try:
            key_string = cache_key.to_string()
            result = await self.redis_client.delete(key_string)

            self.stats["deletes"] += 1
            return result > 0

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache delete error: {e}")
            return False

    async def exists(self, cache_key: CacheKey) -> bool:
        """Check if key exists in cache."""
        self._ensure_initialized()

        try:
            key_string = cache_key.to_string()
            return await self.redis_client.exists(key_string) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

    async def expire(self, cache_key: CacheKey, ttl: int) -> bool:
        """Set expiration for existing key."""
        self._ensure_initialized()

        try:
            key_string = cache_key.to_string()
            return await self.redis_client.expire(key_string, ttl)
        except Exception as e:
            logger.error(f"Cache expire error: {e}")
            return False

    async def clear_namespace(self, namespace: str) -> int:
        """
        Clear all keys in a namespace.

        Args:
            namespace: Namespace to clear

        Returns:
            Number of keys deleted
        """
        self._ensure_initialized()

        try:
            pattern = f"{namespace}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} keys from namespace {namespace}")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache clear namespace error: {e}")
            return 0

    async def get_keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        self._ensure_initialized()

        try:
            keys = await self.redis_client.keys(pattern)
            return [key.decode("utf-8") for key in keys]
        except Exception as e:
            logger.error(f"Cache get keys error: {e}")
            return []

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        self._ensure_initialized()

        try:
            # Get Redis info
            info = await self.redis_client.info()

            # Calculate hit rate
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = (
                (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            )

            return {
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "sets": self.stats["sets"],
                "deletes": self.stats["deletes"],
                "errors": self.stats["errors"],
                "hit_rate": round(hit_rate, 2),
                "total_requests": total_requests,
                "redis_info": {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                },
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return self.stats.copy()


class ConversationCache:
    """Specialized cache for conversation data."""

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.namespace = "conversation"
        self.default_ttl = 3600  # 1 hour

    def _create_key(self, conversation_id: str, key_type: str) -> CacheKey:
        """Create cache key for conversation data."""
        return CacheKey(
            namespace=self.namespace,
            key=f"{conversation_id}:{key_type}",
        )

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Get cached conversation."""
        cache_key = self._create_key(conversation_id, "data")
        return await self.cache_service.get(cache_key)

    async def set_conversation(
        self,
        conversation_id: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """Cache conversation data."""
        cache_key = self._create_key(conversation_id, "data")
        return await self.cache_service.set(cache_key, data, ttl or self.default_ttl)

    async def get_messages(self, conversation_id: str) -> list[dict[str, Any]] | None:
        """Get cached messages."""
        cache_key = self._create_key(conversation_id, "messages")
        return await self.cache_service.get(cache_key)

    async def set_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> bool:
        """Cache conversation messages."""
        cache_key = self._create_key(conversation_id, "messages")
        return await self.cache_service.set(
            cache_key,
            messages,
            ttl or self.default_ttl,
        )

    async def invalidate_conversation(self, conversation_id: str) -> bool:
        """Invalidate all conversation cache entries."""
        try:
            # Delete conversation data
            data_key = self._create_key(conversation_id, "data")
            messages_key = self._create_key(conversation_id, "messages")

            await self.cache_service.delete(data_key)
            await self.cache_service.delete(messages_key)

            return True
        except Exception as e:
            logger.error(f"Failed to invalidate conversation cache: {e}")
            return False


class AIResponseCache:
    """Specialized cache for AI responses."""

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.namespace = "ai_response"
        self.default_ttl = 1800  # 30 minutes

    def _create_key(self, user_id: str, message_hash: str) -> CacheKey:
        """Create cache key for AI response."""
        return CacheKey(
            namespace=self.namespace,
            key=f"{user_id}:{message_hash}",
        )

    def _hash_message(self, message: str, context: str | None = None) -> str:
        """Create hash for message and context."""
        import hashlib

        content = f"{message}:{context or ''}"
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    async def get_response(
        self,
        user_id: str,
        message: str,
        context: str | None = None,
    ) -> dict[str, Any] | None:
        """Get cached AI response."""
        message_hash = self._hash_message(message, context)
        cache_key = self._create_key(user_id, message_hash)
        return await self.cache_service.get(cache_key)

    async def set_response(
        self,
        user_id: str,
        message: str,
        response: dict[str, Any],
        context: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Cache AI response."""
        message_hash = self._hash_message(message, context)
        cache_key = self._create_key(user_id, message_hash)
        return await self.cache_service.set(
            cache_key,
            response,
            ttl or self.default_ttl,
        )


class ToolResultCache:
    """Specialized cache for tool execution results."""

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.namespace = "tool_result"
        self.default_ttl = 7200  # 2 hours

    def _create_key(self, tool_name: str, arguments_hash: str) -> CacheKey:
        """Create cache key for tool result."""
        return CacheKey(
            namespace=self.namespace,
            key=f"{tool_name}:{arguments_hash}",
        )

    def _hash_arguments(self, arguments: dict[str, Any]) -> str:
        """Create hash for tool arguments."""
        import hashlib

        args_str = json.dumps(arguments, sort_keys=True)
        return hashlib.md5(args_str.encode(), usedforsecurity=False).hexdigest()

    async def get_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any | None:
        """Get cached tool result."""
        arguments_hash = self._hash_arguments(arguments)
        cache_key = self._create_key(tool_name, arguments_hash)
        return await self.cache_service.get(cache_key)

    async def set_result(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        ttl: int | None = None,
    ) -> bool:
        """Cache tool result."""
        arguments_hash = self._hash_arguments(arguments)
        cache_key = self._create_key(tool_name, arguments_hash)
        return await self.cache_service.set(cache_key, result, ttl or self.default_ttl)


# Global cache service instance
cache_config = CacheConfig(
    redis_url=settings.redis_url or "redis://localhost:6379",
    default_ttl=3600,
    max_connections=10,
    enable_compression=True,
    cache_prefix="convosphere",
)

cache_service = CacheService(cache_config)
conversation_cache = ConversationCache(cache_service)
ai_response_cache = AIResponseCache(cache_service)
tool_result_cache = ToolResultCache(cache_service)
