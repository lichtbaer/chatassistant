"""
Enhanced RAG (Retrieval-Augmented Generation) service.

This module provides advanced RAG functionality with integration to existing
Weaviate service, knowledge base, and caching systems.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from loguru import logger

from backend.app.core.exceptions import AIError, ConfigurationError
from backend.app.core.exceptions import ValidationError as AppValidationError
from backend.app.schemas.rag import (
    ContextRankingMethod,
    EmbeddingModel,
    RAGConfig,
    RAGMetrics,
    RAGRequest,
    RAGResponse,
    RAGResult,
    RAGStrategy,
)
from backend.app.services.cache_service import cache_service
from backend.app.services.weaviate_service import WeaviateService


class RAGService:
    """Enhanced RAG service with advanced features."""

    def __init__(self):
        self.weaviate_service = WeaviateService()
        self.default_config = self._create_default_config()
        self.metrics = self._initialize_metrics()
        self._configs: dict[str, RAGConfig] = {}
        self._cache_enabled = True

    def _create_default_config(self) -> RAGConfig:
        """Create default RAG configuration."""
        return RAGConfig(
            name="Default RAG Config",
            description="Standard semantic search configuration",
            strategy=RAGStrategy.SEMANTIC,
            max_context_length=4000,
            max_results=5,
            similarity_threshold=0.7,
            embedding_model=EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL,
            ranking_method=ContextRankingMethod.RELEVANCE,
            cache_results=True,
        )

    def _initialize_metrics(self) -> RAGMetrics:
        """Initialize RAG metrics."""
        return RAGMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            avg_retrieval_time=0.0,
            avg_processing_time=0.0,
            avg_total_time=0.0,
            avg_similarity_score=0.0,
            avg_relevance_score=0.0,
            cache_hit_rate=0.0,
            source_usage={},
            strategy_usage={},
            error_counts={},
        )

    async def initialize(self) -> None:
        """Initialize RAG service."""
        try:
            # Test Weaviate connection
            if not self.weaviate_service.health():
                logger.warning(
                    "Weaviate service not available, RAG features may be limited",
                )

            # Initialize cache if available
            if hasattr(cache_service, "initialize"):
                await cache_service.initialize()
                self._cache_enabled = True
                logger.info("RAG service initialized with caching")
            else:
                self._cache_enabled = False
                logger.info("RAG service initialized without caching")

        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise ConfigurationError(f"RAG service initialization failed: {str(e)}")

    async def retrieve(
        self,
        request: RAGRequest,
        config: RAGConfig | None = None,
    ) -> RAGResponse:
        """
        Perform RAG retrieval with advanced features.

        Args:
            request: RAG retrieval request
            config: RAG configuration (uses default if not provided)

        Returns:
            RAG response with retrieved results
        """
        start_time = time.time()
        request_id = str(uuid4())

        try:
            # Validate and prepare configuration
            config = (
                config or self._get_config(request.config_id) or self.default_config
            )
            self._validate_request(request, config)

            # Check cache first
            cache_key = self._create_cache_key(request, config)
            if config.cache_results and self._cache_enabled:
                cached_result = await self._get_cached_result(cache_key)
                if cached_result:
                    self._update_metrics(True, time.time() - start_time, cached_result)
                    return cached_result

            # Perform retrieval
            retrieval_start = time.time()
            results = await self._perform_retrieval(request, config)
            retrieval_time = time.time() - retrieval_start

            # Process and rank results
            processing_start = time.time()
            processed_results = await self._process_results(results, request, config)
            processing_time = time.time() - processing_start

            # Create response
            response = RAGResponse(
                query=request.query,
                results=processed_results,
                config_used=config,
                total_results=len(processed_results),
                retrieval_time=retrieval_time,
                processing_time=processing_time,
                context_length=self._calculate_context_length(processed_results),
                sources_queried=self._get_sources_queried(processed_results),
                cached=False,
                cache_hit=False,
                metadata={"request_id": request_id},
            )

            # Cache results if enabled
            if config.cache_results and self._cache_enabled:
                await self._cache_result(cache_key, response)

            # Update metrics
            total_time = time.time() - start_time
            self._update_metrics(True, total_time, response)

            logger.info(
                f"RAG retrieval completed in {total_time:.2f}s for query: {request.query[:50]}...",
            )
            return response

        except Exception as e:
            self._update_metrics(False, time.time() - start_time, None, str(e))
            logger.error(f"RAG retrieval failed: {e}")
            raise AIError(f"RAG retrieval failed: {str(e)}")

    async def _perform_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
    ) -> list[dict[str, Any]]:
        """Perform the actual retrieval based on strategy."""

        results = []

        # Get conversation history if requested
        conversation_history = []
        if config.include_conversation_history and request.conversation_id:
            conversation_history = await self._get_conversation_history(
                request.conversation_id,
                config.conversation_history_limit,
            )

        # Perform retrieval based on strategy
        if config.strategy == RAGStrategy.SEMANTIC:
            results = await self._semantic_retrieval(
                request,
                config,
                conversation_history,
            )
        elif config.strategy == RAGStrategy.HYBRID:
            results = await self._hybrid_retrieval(
                request,
                config,
                conversation_history,
            )
        elif config.strategy == RAGStrategy.KEYWORD:
            results = await self._keyword_retrieval(
                request,
                config,
                conversation_history,
            )
        elif config.strategy == RAGStrategy.CONTEXTUAL:
            results = await self._contextual_retrieval(
                request,
                config,
                conversation_history,
            )
        elif config.strategy == RAGStrategy.ADAPTIVE:
            results = await self._adaptive_retrieval(
                request,
                config,
                conversation_history,
            )

        return results

    async def _semantic_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
        conversation_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform semantic retrieval using Weaviate."""

        results = []

        # Search knowledge base
        if config.knowledge_sources or not config.knowledge_sources:
            knowledge_results = self.weaviate_service.semantic_search_knowledge(
                query=request.query,
                limit=config.max_results,
            )
            results.extend(self._format_knowledge_results(knowledge_results))

        # Search conversation history if available
        if conversation_history:
            conversation_results = self.weaviate_service.semantic_search_messages(
                query=request.query,
                conversation_id=request.conversation_id,
                limit=min(config.max_results, 3),  # Limit conversation results
            )
            results.extend(self._format_conversation_results(conversation_results))

        return results

    async def _hybrid_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
        conversation_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform hybrid retrieval combining semantic and keyword search."""

        # Perform both semantic and keyword searches
        semantic_results = await self._semantic_retrieval(
            request,
            config,
            conversation_history,
        )
        keyword_results = await self._keyword_retrieval(
            request,
            config,
            conversation_history,
        )

        # Combine and deduplicate results
        return self._combine_results(semantic_results, keyword_results)

    async def _keyword_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
        conversation_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform keyword-based retrieval."""

        # Extract keywords from query
        keywords = self._extract_keywords(request.query)

        # Search using keywords (simplified implementation)
        results = []
        for keyword in keywords[:5]:  # Limit to top 5 keywords
            keyword_results = self.weaviate_service.semantic_search_knowledge(
                query=keyword,
                limit=config.max_results // 2,
            )
            results.extend(self._format_knowledge_results(keyword_results))

        return results

    async def _contextual_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
        conversation_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform contextual retrieval using conversation history."""

        if not conversation_history:
            # Fallback to semantic retrieval
            return await self._semantic_retrieval(request, config, conversation_history)

        # Build contextual query
        context_query = self._build_contextual_query(
            request.query,
            conversation_history,
        )

        # Perform semantic search with contextual query
        results = self.weaviate_service.semantic_search_knowledge(
            query=context_query,
            limit=config.max_results,
        )

        return self._format_knowledge_results(results)

    async def _adaptive_retrieval(
        self,
        request: RAGRequest,
        config: RAGConfig,
        conversation_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Perform adaptive retrieval based on query characteristics."""

        # Analyze query characteristics
        query_analysis = self._analyze_query(request.query)

        # Choose strategy based on analysis
        if query_analysis["is_technical"]:
            # Use semantic retrieval for technical queries
            return await self._semantic_retrieval(request, config, conversation_history)
        if query_analysis["is_conversational"]:
            # Use contextual retrieval for conversational queries
            return await self._contextual_retrieval(
                request,
                config,
                conversation_history,
            )
        if query_analysis["has_specific_terms"]:
            # Use hybrid retrieval for specific term queries
            return await self._hybrid_retrieval(request, config, conversation_history)
        # Default to semantic retrieval
        return await self._semantic_retrieval(request, config, conversation_history)

    async def _process_results(
        self,
        results: list[dict[str, Any]],
        request: RAGRequest,
        config: RAGConfig,
    ) -> list[RAGResult]:
        """Process and rank retrieval results."""

        # Convert to RAGResult objects
        rag_results = []
        for result in results:
            try:
                rag_result = RAGResult(
                    content=result.get("content", ""),
                    source=result.get("source", "unknown"),
                    source_type=result.get("source_type", "document"),
                    source_id=result.get("source_id", ""),
                    similarity_score=result.get("similarity_score", 0.0),
                    relevance_score=self._calculate_relevance_score(result, request),
                    ranking_score=0.0,  # Will be calculated below
                    chunk_index=result.get("chunk_index"),
                    token_count=len(result.get("content", "").split()),
                    created_at=result.get("created_at"),
                    metadata=result.get("metadata", {}),
                )
                rag_results.append(rag_result)
            except Exception as e:
                logger.warning(f"Failed to process result: {e}")
                continue

        # Apply similarity threshold
        rag_results = [
            result
            for result in rag_results
            if result.similarity_score >= config.similarity_threshold
        ]

        # Rank results
        rag_results = await self._rank_results(rag_results, config)

        # Limit results
        return rag_results[: config.max_results]

    async def _rank_results(
        self,
        results: list[RAGResult],
        config: RAGConfig,
    ) -> list[RAGResult]:
        """Rank results based on configuration."""

        for result in results:
            ranking_score = 0.0

            # Base score from similarity
            ranking_score += result.similarity_score * 0.4

            # Relevance score
            ranking_score += result.relevance_score * 0.3

            # Freshness bonus
            if result.created_at:
                freshness_score = self._calculate_freshness_score(result.created_at)
                ranking_score += freshness_score * config.freshness_weight

            # Authority bonus
            authority_score = self._calculate_authority_score(result.source)
            ranking_score += authority_score * config.authority_weight

            # Diversity penalty (simplified)
            if config.ranking_method == ContextRankingMethod.DIVERSITY:
                diversity_penalty = self._calculate_diversity_penalty(result, results)
                ranking_score -= diversity_penalty * config.diversity_penalty

            result.ranking_score = min(1.0, max(0.0, ranking_score))

        # Sort by ranking score
        results.sort(key=lambda x: x.ranking_score, reverse=True)

        return results

    def _calculate_relevance_score(
        self,
        result: dict[str, Any],
        request: RAGRequest,
    ) -> float:
        """Calculate relevance score for a result."""
        # Simple relevance calculation based on query overlap
        query_terms = set(request.query.lower().split())
        content_terms = set(result.get("content", "").lower().split())

        if not query_terms:
            return 0.0

        overlap = len(query_terms.intersection(content_terms))
        return min(1.0, overlap / len(query_terms))

    def _calculate_freshness_score(self, created_at: datetime) -> float:
        """Calculate freshness score based on creation time."""
        age_days = (datetime.now(UTC) - created_at).days
        if age_days <= 1:
            return 1.0
        if age_days <= 7:
            return 0.8
        if age_days <= 30:
            return 0.6
        if age_days <= 90:
            return 0.4
        return 0.2

    def _calculate_authority_score(self, source: str) -> float:
        """Calculate authority score for a source."""
        # Simple authority scoring (could be enhanced with source metadata)
        authority_sources = {
            "official_documentation": 1.0,
            "technical_specification": 0.9,
            "research_paper": 0.8,
            "expert_opinion": 0.7,
            "user_generated": 0.5,
            "unknown": 0.3,
        }

        return authority_sources.get(source.lower(), 0.5)

    def _calculate_diversity_penalty(
        self,
        result: RAGResult,
        all_results: list[RAGResult],
    ) -> float:
        """Calculate diversity penalty for result."""
        # Simplified diversity penalty
        similar_results = 0
        for other_result in all_results:
            if other_result != result:
                # Check for content similarity
                content_similarity = self._calculate_content_similarity(
                    result.content,
                    other_result.content,
                )
                if content_similarity > 0.7:
                    similar_results += 1

        return min(1.0, similar_results * 0.1)

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content pieces."""
        # Simple Jaccard similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _format_knowledge_results(
        self,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format knowledge base results."""
        formatted_results = []
        for result in results:
            formatted_result = {
                "content": result.get("content", ""),
                "source": "knowledge_base",
                "source_type": "document",
                "source_id": result.get("id", ""),
                "similarity_score": result.get("score", 0.0),
                "chunk_index": result.get("chunk_index"),
                "created_at": result.get("created_at"),
                "metadata": result.get("metadata", {}),
            }
            formatted_results.append(formatted_result)
        return formatted_results

    def _format_conversation_results(
        self,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format conversation results."""
        formatted_results = []
        for result in results:
            formatted_result = {
                "content": result.get("content", ""),
                "source": "conversation",
                "source_type": "message",
                "source_id": result.get("message_id", ""),
                "similarity_score": result.get("score", 0.0),
                "created_at": result.get("created_at"),
                "metadata": result.get("metadata", {}),
            }
            formatted_results.append(formatted_result)
        return formatted_results

    async def _get_conversation_history(
        self,
        conversation_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Get conversation history for context."""
        # This would integrate with existing conversation service
        # For now, return empty list
        return []

    def _create_cache_key(self, request: RAGRequest, config: RAGConfig) -> str:
        """Create cache key for request."""
        key_data = {
            "query": request.query,
            "conversation_id": request.conversation_id,
            "config_hash": hashlib.md5(
                config.json().encode(), usedforsecurity=False
            ).hexdigest()[:8],
        }
        return hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode(), usedforsecurity=False
        ).hexdigest()

    async def _get_cached_result(self, cache_key: str) -> RAGResponse | None:
        """Get cached RAG result."""
        try:
            cached_data = await cache_service.get(
                cache_key=cache_key,
                namespace="rag_results",
            )
            if cached_data:
                return RAGResponse(**cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached result: {e}")
        return None

    async def _cache_result(self, cache_key: str, response: RAGResponse) -> None:
        """Cache RAG result."""
        try:
            await cache_service.set(
                cache_key=cache_key,
                data=response.dict(),
                namespace="rag_results",
                ttl=3600,  # 1 hour
            )
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    def _validate_request(self, request: RAGRequest, config: RAGConfig) -> None:
        """Validate RAG request."""
        if not request.query.strip():
            raise AppValidationError("Query cannot be empty")

        if len(request.query) < 3:
            raise AppValidationError("Query too short, minimum 3 characters")

    def _get_config(self, config_id: str | None) -> RAGConfig | None:
        """Get RAG configuration by ID."""
        if not config_id:
            return None
        return self._configs.get(config_id)

    def _update_metrics(
        self,
        success: bool,
        processing_time: float,
        response: RAGResponse | None = None,
        error: str | None = None,
    ) -> None:
        """Update RAG metrics."""
        self.metrics.total_requests += 1

        if success:
            self.metrics.successful_requests += 1
            if response:
                self.metrics.avg_total_time = (
                    self.metrics.avg_total_time * (self.metrics.successful_requests - 1)
                    + processing_time
                ) / self.metrics.successful_requests
                self.metrics.avg_retrieval_time = (
                    self.metrics.avg_retrieval_time
                    * (self.metrics.successful_requests - 1)
                    + response.retrieval_time
                ) / self.metrics.successful_requests
                self.metrics.avg_processing_time = (
                    self.metrics.avg_processing_time
                    * (self.metrics.successful_requests - 1)
                    + response.processing_time
                ) / self.metrics.successful_requests

                # Update quality metrics
                if response.results:
                    avg_similarity = sum(
                        r.similarity_score for r in response.results
                    ) / len(response.results)
                    avg_relevance = sum(
                        r.relevance_score for r in response.results
                    ) / len(response.results)

                    self.metrics.avg_similarity_score = (
                        self.metrics.avg_similarity_score
                        * (self.metrics.successful_requests - 1)
                        + avg_similarity
                    ) / self.metrics.successful_requests
                    self.metrics.avg_relevance_score = (
                        self.metrics.avg_relevance_score
                        * (self.metrics.successful_requests - 1)
                        + avg_relevance
                    ) / self.metrics.successful_requests
        else:
            self.metrics.failed_requests += 1
            if error:
                self.metrics.error_counts[error] = (
                    self.metrics.error_counts.get(error, 0) + 1
                )

    def _calculate_context_length(self, results: list[RAGResult]) -> int:
        """Calculate total context length in tokens."""
        return sum(result.token_count for result in results)

    def _get_sources_queried(self, results: list[RAGResult]) -> list[str]:
        """Get list of sources that were queried."""
        return list({result.source for result in results})

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract keywords from query."""
        # Simple keyword extraction (could be enhanced with NLP)
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        words = query.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords[:10]  # Limit to top 10 keywords

    def _build_contextual_query(self, query: str, history: list[dict[str, Any]]) -> str:
        """Build contextual query using conversation history."""
        # Simple contextual query building
        context_terms = []
        for message in history[-3:]:  # Use last 3 messages
            content = message.get("content", "")
            context_terms.extend(self._extract_keywords(content))

        # Combine with original query
        return f"{query} {' '.join(set(context_terms))}"

    def _analyze_query(self, query: str) -> dict[str, Any]:
        """Analyze query characteristics."""
        query_lower = query.lower()

        # Technical terms
        technical_terms = [
            "api",
            "function",
            "method",
            "class",
            "database",
            "server",
            "config",
            "error",
        ]
        is_technical = any(term in query_lower for term in technical_terms)

        # Conversational indicators
        conversational_terms = [
            "how",
            "what",
            "why",
            "when",
            "where",
            "can you",
            "please",
            "help",
        ]
        is_conversational = any(term in query_lower for term in conversational_terms)

        # Specific terms
        has_specific_terms = len(self._extract_keywords(query)) > 3

        return {
            "is_technical": is_technical,
            "is_conversational": is_conversational,
            "has_specific_terms": has_specific_terms,
        }

    def _combine_results(
        self,
        results1: list[dict[str, Any]],
        results2: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Combine and deduplicate results from different retrieval methods."""
        combined = results1 + results2

        # Simple deduplication based on content similarity
        deduplicated = []
        for result in combined:
            is_duplicate = False
            for existing in deduplicated:
                if (
                    self._calculate_content_similarity(
                        result.get("content", ""),
                        existing.get("content", ""),
                    )
                    > 0.8
                ):
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduplicated.append(result)

        return deduplicated

    async def get_metrics(self) -> RAGMetrics:
        """Get current RAG metrics."""
        return self.metrics

    async def create_config(self, config: RAGConfig) -> str:
        """Create new RAG configuration."""
        config_id = str(uuid4())
        self._configs[config_id] = config
        return config_id

    async def update_config(self, config_id: str, config: RAGConfig) -> bool:
        """Update existing RAG configuration."""
        if config_id in self._configs:
            self._configs[config_id] = config
            return True
        return False

    async def delete_config(self, config_id: str) -> bool:
        """Delete RAG configuration."""
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    async def list_configs(self) -> list[tuple[str, RAGConfig]]:
        """List all RAG configurations."""
        return list(self._configs.items())


# Global RAG service instance
rag_service = RAGService()
