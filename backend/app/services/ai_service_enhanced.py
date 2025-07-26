"""
Enhanced AI Service with Performance Integration.

This module extends the existing AI service with caching, async processing,
and performance monitoring from Phase 3.
"""

import time
from typing import Any

from loguru import logger

from backend.app.services.ai_service import ai_service
from backend.app.services.performance_integration import performance_integration


class EnhancedAIService:
    """Enhanced AI service with performance optimization."""

    def __init__(self):
        """Initialize enhanced AI service."""
        self.ai_service = ai_service
        self.cache_enabled = True
        self.async_processing_enabled = True
        self.monitoring_enabled = True

        # Performance tracking
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    async def initialize(self) -> None:
        """Initialize the enhanced AI service."""
        try:
            # Initialize performance integration if not already done
            if not performance_integration.initialized:
                await performance_integration.initialize()

            logger.info("Enhanced AI service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced AI service: {e}")
            raise

    async def chat_completion_with_caching(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        conversation_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_knowledge_base: bool = True,
        use_tools: bool = True,
        max_context_chunks: int = 5,
        cache_ttl: int = 1800,  # 30 minutes
        **kwargs,
    ) -> dict[str, Any]:
        """
        Enhanced chat completion with caching and performance monitoring.

        Args:
            messages: List of conversation messages
            user_id: User ID for caching and monitoring
            conversation_id: Conversation ID for context
            model: AI model to use
            temperature: Model temperature
            max_tokens: Maximum tokens for response
            use_knowledge_base: Whether to use knowledge base
            use_tools: Whether to use tools
            max_context_chunks: Maximum context chunks
            cache_ttl: Cache TTL in seconds
            **kwargs: Additional arguments

        Returns:
            Enhanced AI response with performance metrics
        """
        start_time = time.time()

        try:
            # Create cache key
            cache_key = self._create_cache_key(
                messages,
                user_id,
                model,
                temperature,
                max_tokens,
                use_knowledge_base,
                use_tools,
                max_context_chunks,
            )

            # Try to get cached response
            if self.cache_enabled:
                cached_response = await performance_integration.get_cached_ai_response(
                    user_id,
                    cache_key,
                    context=str(conversation_id),
                )

                if cached_response:
                    self.cache_hits += 1
                    response_time = time.time() - start_time

                    # Record cache hit metric
                    if self.monitoring_enabled:
                        performance_integration.record_performance_metric(
                            "ai_cache_hit",
                            1,
                            metric_type="counter",
                            tags={"user_id": user_id, "model": model or "default"},
                        )

                    logger.info(f"AI response cache hit for user {user_id}")
                    return {
                        **cached_response,
                        "cached": True,
                        "response_time": response_time,
                        "cache_hit": True,
                    }

            self.cache_misses += 1

            # Generate new response using existing AI service
            response = await self.ai_service.chat_completion_with_rag(
                messages=messages,
                user_id=user_id,
                conversation_id=conversation_id,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                use_knowledge_base=use_knowledge_base,
                use_tools=use_tools,
                max_context_chunks=max_context_chunks,
                **kwargs,
            )

            response_time = time.time() - start_time

            # Cache the response
            if self.cache_enabled:
                await performance_integration.cache_ai_response(
                    user_id,
                    cache_key,
                    response,
                    context=str(conversation_id),
                    ttl=cache_ttl,
                )

            # Record performance metrics
            if self.monitoring_enabled:
                performance_integration.record_api_request(
                    endpoint="/api/ai/chat",
                    method="POST",
                    status_code=200,
                    response_time=response_time,
                    user_id=user_id,
                )

                performance_integration.record_performance_metric(
                    "ai_response_time",
                    response_time,
                    metric_type="histogram",
                    unit="seconds",
                    tags={"user_id": user_id, "model": model or "default"},
                )

                performance_integration.record_performance_metric(
                    "ai_tokens_used",
                    response.get("usage", {}).get("total_tokens", 0),
                    metric_type="counter",
                    tags={"user_id": user_id, "model": model or "default"},
                )

            self.request_count += 1

            return {
                **response,
                "cached": False,
                "response_time": response_time,
                "cache_hit": False,
                "performance_metrics": {
                    "total_requests": self.request_count,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "cache_hit_rate": (self.cache_hits / max(1, self.request_count))
                    * 100,
                },
            }

        except Exception as e:
            response_time = time.time() - start_time

            # Record error metrics
            if self.monitoring_enabled:
                performance_integration.record_api_request(
                    endpoint="/api/ai/chat",
                    method="POST",
                    status_code=500,
                    response_time=response_time,
                    user_id=user_id,
                    error=str(e),
                )

            logger.error(f"AI chat completion failed: {e}")
            raise

    async def generate_response_async(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
        assistant_id: str | None = None,
        use_rag: bool = True,
        use_tools: bool = True,
        max_context_chunks: int = 5,
        priority: str = "normal",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Generate AI response asynchronously with task queuing.

        Args:
            conversation_id: Conversation ID
            user_message: User message
            user_id: User ID
            assistant_id: Assistant ID
            use_rag: Whether to use RAG
            use_tools: Whether to use tools
            max_context_chunks: Maximum context chunks
            priority: Task priority (low, normal, high, urgent, critical)
            **kwargs: Additional arguments

        Returns:
            Task submission result
        """
        if not self.async_processing_enabled:
            # Fallback to synchronous processing
            return await self._generate_response_sync(
                conversation_id,
                user_message,
                user_id,
                assistant_id,
                use_rag,
                use_tools,
                max_context_chunks,
                **kwargs,
            )

        try:
            # Submit async task
            task_id = await performance_integration.submit_ai_response_task(
                message=user_message,
                user_id=user_id,
                conversation_id=conversation_id,
                model=kwargs.get("model", "gpt-4"),
                priority=self._map_priority(priority),
            )

            return {
                "task_id": task_id,
                "status": "processing",
                "message": "AI response generation started",
                "estimated_time": "10-30 seconds",
            }

        except Exception as e:
            logger.error(f"Failed to submit async AI task: {e}")
            # Fallback to synchronous processing
            return await self._generate_response_sync(
                conversation_id,
                user_message,
                user_id,
                assistant_id,
                use_rag,
                use_tools,
                max_context_chunks,
                **kwargs,
            )

    async def get_response_status(self, task_id: str) -> dict[str, Any] | None:
        """Get status of async response generation task."""
        if not self.async_processing_enabled:
            return None

        try:
            return await performance_integration.get_task_status(task_id)
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None

    async def _generate_response_sync(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
        assistant_id: str | None = None,
        use_rag: bool = True,
        use_tools: bool = True,
        max_context_chunks: int = 5,
        **kwargs,
    ) -> dict[str, Any]:
        """Generate response synchronously (fallback method)."""
        start_time = time.time()

        try:
            # Use existing AI service
            response = await self.ai_service.get_response(
                conversation_id=conversation_id,
                user_message=user_message,
                user_id=user_id,
                use_rag=use_rag,
                use_tools=use_tools,
                max_context_chunks=max_context_chunks,
                **kwargs,
            )

            response_time = time.time() - start_time

            return {
                "status": "completed",
                "response": response,
                "response_time": response_time,
                "processing_mode": "synchronous",
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Synchronous AI response generation failed: {e}")

            return {
                "status": "failed",
                "error": str(e),
                "response_time": response_time,
                "processing_mode": "synchronous",
            }

    def _create_cache_key(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        use_knowledge_base: bool,
        use_tools: bool,
        max_context_chunks: int,
    ) -> str:
        """Create cache key for AI response."""
        import hashlib
        import json

        # Create a deterministic key
        key_data = {
            "messages": messages,
            "user_id": user_id,
            "model": model or "default",
            "temperature": round(temperature, 2),
            "max_tokens": max_tokens,
            "use_knowledge_base": use_knowledge_base,
            "use_tools": use_tools,
            "max_context_chunks": max_context_chunks,
        }

        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    def _map_priority(self, priority: str) -> str:
        """Map string priority to TaskPriority enum."""
        priority_map = {
            "low": "LOW",
            "normal": "NORMAL",
            "high": "HIGH",
            "urgent": "URGENT",
            "critical": "CRITICAL",
        }
        return priority_map.get(priority.lower(), "NORMAL")

    async def get_embeddings_with_caching(
        self,
        text: str,
        user_id: str,
        model: str = "text-embedding-ada-002",
        cache_ttl: int = 86400,  # 24 hours
    ) -> list[float]:
        """
        Get embeddings with caching.

        Args:
            text: Text to embed
            user_id: User ID for caching
            model: Embedding model
            cache_ttl: Cache TTL in seconds

        Returns:
            Embedding vector
        """
        start_time = time.time()

        try:
            # Create cache key for embeddings
            f"embedding:{model}:{hash(text)}"

            # Try to get cached embedding
            if self.cache_enabled:
                cached_embedding = await performance_integration.get_cached_tool_result(
                    "embedding_service",
                    {"text": text, "model": model},
                )

                if cached_embedding:
                    response_time = time.time() - start_time

                    if self.monitoring_enabled:
                        performance_integration.record_performance_metric(
                            "embedding_cache_hit",
                            1,
                            metric_type="counter",
                            tags={"user_id": user_id, "model": model},
                        )

                    return cached_embedding

            # Generate new embedding
            embedding = await self.ai_service.get_embeddings(text, model)

            # Cache the embedding
            if self.cache_enabled:
                await performance_integration.cache_tool_result(
                    "embedding_service",
                    {"text": text, "model": model},
                    embedding,
                    cache_ttl,
                )

            response_time = time.time() - start_time

            # Record performance metrics
            if self.monitoring_enabled:
                performance_integration.record_performance_metric(
                    "embedding_generation_time",
                    response_time,
                    metric_type="histogram",
                    unit="seconds",
                    tags={"user_id": user_id, "model": model},
                )

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def get_embeddings_batch_with_caching(
        self,
        texts: list[str],
        user_id: str,
        model: str = "text-embedding-ada-002",
        cache_ttl: int = 86400,  # 24 hours
    ) -> list[list[float]]:
        """
        Get embeddings for multiple texts with caching.

        Args:
            texts: List of texts to embed
            user_id: User ID for caching
            model: Embedding model
            cache_ttl: Cache TTL in seconds

        Returns:
            List of embedding vectors
        """
        start_time = time.time()

        try:
            embeddings = []
            cache_hits = 0

            for text in texts:
                # Try to get cached embedding for each text
                if self.cache_enabled:
                    cached_embedding = (
                        await performance_integration.get_cached_tool_result(
                            "embedding_service",
                            {"text": text, "model": model},
                        )
                    )

                    if cached_embedding:
                        embeddings.append(cached_embedding)
                        cache_hits += 1
                        continue

                # Generate new embedding
                embedding = await self.ai_service.get_embeddings(text, model)
                embeddings.append(embedding)

                # Cache the embedding
                if self.cache_enabled:
                    await performance_integration.cache_tool_result(
                        "embedding_service",
                        {"text": text, "model": model},
                        embedding,
                        cache_ttl,
                    )

            response_time = time.time() - start_time

            # Record performance metrics
            if self.monitoring_enabled:
                performance_integration.record_performance_metric(
                    "batch_embedding_time",
                    response_time,
                    metric_type="histogram",
                    unit="seconds",
                    tags={"user_id": user_id, "model": model, "batch_size": len(texts)},
                )

                performance_integration.record_performance_metric(
                    "batch_embedding_cache_hit_rate",
                    (cache_hits / len(texts)) * 100,
                    metric_type="gauge",
                    unit="percent",
                    tags={"user_id": user_id, "model": model},
                )

            return embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    def get_performance_stats(self) -> dict[str, Any]:
        """Get AI service performance statistics."""
        total_requests = max(1, self.request_count)
        cache_hit_rate = (self.cache_hits / total_requests) * 100

        return {
            "total_requests": self.request_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(cache_hit_rate, 2),
            "ai_service_enabled": self.ai_service.is_enabled(),
            "cache_enabled": self.cache_enabled,
            "async_processing_enabled": self.async_processing_enabled,
            "monitoring_enabled": self.monitoring_enabled,
        }

    def get_health_status(self) -> dict[str, Any]:
        """Get AI service health status."""
        ai_health = self.ai_service.health_check()

        return {
            "status": (
                "healthy" if ai_health.get("status") == "healthy" else "unhealthy"
            ),
            "ai_service": ai_health,
            "performance_stats": self.get_performance_stats(),
            "cache_status": "enabled" if self.cache_enabled else "disabled",
            "async_status": "enabled" if self.async_processing_enabled else "disabled",
            "monitoring_status": "enabled" if self.monitoring_enabled else "disabled",
        }

    # Delegate other methods to the underlying AI service
    def get_available_models(self) -> dict[str, dict]:
        """Get available AI models."""
        return self.ai_service.get_available_models()

    def get_available_providers(self) -> dict[str, dict]:
        """Get available AI providers."""
        return self.ai_service.get_available_providers()

    def get_cost_summary(self) -> dict[str, Any]:
        """Get AI cost summary."""
        return self.ai_service.get_cost_summary()

    def is_enabled(self) -> bool:
        """Check if AI service is enabled."""
        return self.ai_service.is_enabled()


# Global enhanced AI service instance
enhanced_ai_service = EnhancedAIService()
