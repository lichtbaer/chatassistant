"""
Embedding service for generating vector embeddings.

This module provides functionality for generating embeddings from text chunks
using various embedding models and managing embedding operations.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
from litellm import completion

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingModel(Enum):
    """Embedding model enumeration."""

    OPENAI_TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    OPENAI_TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    OPENAI_TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    COHERE_EMBED_ENGLISH_V3 = "embed-english-v3.0"
    COHERE_EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"
    HUGGINGFACE_ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"
    HUGGINGFACE_ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"


class SimilarityMetric(Enum):
    """Similarity metric enumeration."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"


@dataclass
class EmbeddingResult:
    """Embedding result with metadata."""

    text: str
    embedding: list[float]
    model: str
    dimension: int
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_score: float | None = None


@dataclass
class SimilarityResult:
    """Similarity search result."""

    text: str
    similarity_score: float
    rank: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingBatch:
    """Batch of embeddings for processing."""

    texts: list[str]
    embeddings: list[list[float]]
    model: str
    batch_id: str
    created_at: datetime
    processing_time: float | None = None
    success_count: int = 0
    error_count: int = 0


class EmbeddingService:
    """Service for generating and managing embeddings."""

    def __init__(self):
        self.model = get_settings().default_embedding_model
        self.batch_size = 10  # Process embeddings in batches
        self.max_retries = 3
        self.retry_delay = 1.0

        # Model configurations
        self.model_configs = {
            EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL: {
                "dimension": 1536,
                "max_tokens": 8192,
                "provider": "openai",
            },
            EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_LARGE: {
                "dimension": 3072,
                "max_tokens": 8192,
                "provider": "openai",
            },
            EmbeddingModel.OPENAI_TEXT_EMBEDDING_ADA_002: {
                "dimension": 1536,
                "max_tokens": 8192,
                "provider": "openai",
            },
            EmbeddingModel.COHERE_EMBED_ENGLISH_V3: {
                "dimension": 1024,
                "max_tokens": 512,
                "provider": "cohere",
            },
            EmbeddingModel.COHERE_EMBED_MULTILINGUAL_V3: {
                "dimension": 1024,
                "max_tokens": 512,
                "provider": "cohere",
            },
            EmbeddingModel.HUGGINGFACE_ALL_MINILM_L6_V2: {
                "dimension": 384,
                "max_tokens": 256,
                "provider": "huggingface",
            },
            EmbeddingModel.HUGGINGFACE_ALL_MPNET_BASE_V2: {
                "dimension": 768,
                "max_tokens": 384,
                "provider": "huggingface",
            },
        }

        # Embedding cache
        self.embedding_cache = {}
        self.cache_size_limit = 10000

        # Performance tracking
        self.embedding_stats = {
            "total_embeddings": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
        use_cache: bool = True,
        batch_size: int | None = None,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for a list of texts with enhanced features.

        Args:
            texts: List of text strings to embed
            model: Embedding model to use
            use_cache: Whether to use embedding cache
            batch_size: Override default batch size

        Returns:
            List of embedding results with metadata
        """
        start_time = datetime.now(UTC)

        try:
            if not texts:
                return []

            model_name = model or self.model
            batch_size = batch_size or self.batch_size

            # Check cache first
            cached_results = []
            uncached_texts = []
            uncached_indices = []

            if use_cache:
                for i, text in enumerate(texts):
                    cache_key = self._get_cache_key(text, model_name)
                    if cache_key in self.embedding_cache:
                        cached_results.append(self.embedding_cache[cache_key])
                        self.embedding_stats["cache_hits"] += 1
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(i)
                        self.embedding_stats["cache_misses"] += 1
            else:
                uncached_texts = texts
                uncached_indices = list(range(len(texts)))

            # Generate embeddings for uncached texts
            new_embeddings = []
            if uncached_texts:
                new_embeddings = await self._generate_embeddings_with_retry(
                    uncached_texts,
                    model_name,
                    batch_size,
                )

                # Cache new embeddings
                if use_cache:
                    for i, embedding in enumerate(new_embeddings):
                        if embedding:
                            cache_key = self._get_cache_key(
                                uncached_texts[i],
                                model_name,
                            )
                            self._cache_embedding(cache_key, embedding)

            # Combine cached and new results
            all_results = []
            cached_idx = 0
            new_idx = 0

            for i in range(len(texts)):
                if i in uncached_indices:
                    # Use new embedding
                    if new_idx < len(new_embeddings) and new_embeddings[new_idx]:
                        result = EmbeddingResult(
                            text=texts[i],
                            embedding=new_embeddings[new_idx],
                            model=model_name,
                            dimension=len(new_embeddings[new_idx]),
                            timestamp=datetime.now(UTC),
                            quality_score=self._calculate_quality_score(
                                new_embeddings[new_idx],
                            ),
                        )
                        all_results.append(result)
                    else:
                        all_results.append(None)
                    new_idx += 1
                else:
                    # Use cached embedding
                    all_results.append(cached_results[cached_idx])
                    cached_idx += 1

            # Update statistics
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            self.embedding_stats["total_embeddings"] += len(texts)
            self.embedding_stats["total_processing_time"] += processing_time
            self.embedding_stats["average_processing_time"] = (
                self.embedding_stats["total_processing_time"]
                / self.embedding_stats["total_embeddings"]
            )

            # Record performance metrics
            # Performance monitoring disabled for now

            return all_results

        except Exception as e:
            logger.exception(f"Error generating embeddings: {e}")
            # Error recording disabled for now
            return []

    async def _generate_embeddings_with_retry(
        self,
        texts: list[str],
        model: str,
        batch_size: int,
    ) -> list[list[float]]:
        """Generate embeddings with retry logic."""
        for attempt in range(self.max_retries):
            try:
                embeddings = []

                # Process in batches
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]

                    # Generate embeddings for batch
                    batch_embeddings = await self._generate_batch_embeddings(
                        batch,
                        model,
                    )
                    embeddings.extend(batch_embeddings)

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)

                return embeddings

            except Exception as e:
                logger.warning(
                    f"Embedding generation attempt {attempt + 1} failed: {e}",
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
        return None

    async def _generate_batch_embeddings(
        self,
        texts: list[str],
        model: str = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed
            model: Model to use for embedding generation

        Returns:
            List of embedding vectors
        """
        try:
            model_name = model or self.model

            # Use LiteLLM for embedding generation
            response = await completion(
                model=model_name,
                messages=[{"role": "user", "content": text} for text in texts],
                temperature=0,
                max_tokens=1,  # We only need embeddings, not completions
                embedding=True,
            )

            if hasattr(response, "embeddings") and response.embeddings:
                return response.embeddings
            logger.warning("No embeddings returned from model")
            return []

        except Exception as e:
            logger.exception(f"Error generating batch embeddings: {e}")
            return []

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model."""
        import hashlib

        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
        return f"{model}:{text_hash}"

    def _cache_embedding(self, cache_key: str, embedding: list[float]):
        """Cache an embedding."""
        if len(self.embedding_cache) >= self.cache_size_limit:
            # Remove oldest entries (simple LRU)
            oldest_keys = list(self.embedding_cache.keys())[:1000]
            for key in oldest_keys:
                del self.embedding_cache[key]

        self.embedding_cache[cache_key] = embedding

    def _calculate_quality_score(self, embedding: list[float]) -> float:
        """Calculate quality score for embedding."""
        try:
            # Convert to numpy array
            emb_array = np.array(embedding)

            # Calculate various quality metrics
            magnitude = np.linalg.norm(emb_array)
            variance = np.var(emb_array)
            entropy = -np.sum(emb_array * np.log(np.abs(emb_array) + 1e-10))

            # Normalize and combine metrics
            quality_score = (
                0.4 * (magnitude / len(embedding))
                + 0.3 * min(variance, 1.0)
                + 0.3 * min(entropy / len(embedding), 1.0)
            )

            return min(quality_score, 1.0)

        except Exception as e:
            logger.exception(f"Error calculating quality score: {e}")
            return 0.5  # Default score

    async def generate_single_embedding(self, text: str) -> list[float] | None:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector or None
        """
        try:
            embeddings = await self.generate_embeddings([text])
            return embeddings[0] if embeddings else None

        except Exception as e:
            logger.exception(f"Error generating single embedding: {e}")
            return None

    def calculate_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
        metric: SimilarityMetric = SimilarityMetric.COSINE,
    ) -> float:
        """
        Calculate similarity between two embeddings using specified metric.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            metric: Similarity metric to use

        Returns:
            Similarity score
        """
        try:
            if not embedding1 or not embedding2:
                return 0.0

            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            if metric == SimilarityMetric.COSINE:
                return self._cosine_similarity(vec1, vec2)
            if metric == SimilarityMetric.EUCLIDEAN:
                return self._euclidean_similarity(vec1, vec2)
            if metric == SimilarityMetric.DOT_PRODUCT:
                return self._dot_product_similarity(vec1, vec2)
            if metric == SimilarityMetric.MANHATTAN:
                return self._manhattan_similarity(vec1, vec2)
            logger.warning(f"Unknown similarity metric: {metric}")
            return self._cosine_similarity(vec1, vec2)

        except Exception as e:
            logger.exception(f"Error calculating similarity: {e}")
            return 0.0

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _euclidean_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Euclidean distance-based similarity."""
        distance = np.linalg.norm(vec1 - vec2)
        # Convert distance to similarity (inverse relationship)
        return float(1.0 / (1.0 + distance))

    def _dot_product_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate dot product similarity."""
        return float(np.dot(vec1, vec2))

    def _manhattan_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Manhattan distance-based similarity."""
        distance = np.sum(np.abs(vec1 - vec2))
        # Convert distance to similarity (inverse relationship)
        return float(1.0 / (1.0 + distance))

    def calculate_batch_similarity(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        metric: SimilarityMetric = SimilarityMetric.COSINE,
    ) -> list[float]:
        """
        Calculate similarity between query and multiple candidates efficiently.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            metric: Similarity metric to use

        Returns:
            List of similarity scores
        """
        try:
            if not query_embedding or not candidate_embeddings:
                return []

            query_vec = np.array(query_embedding)
            candidate_matrix = np.array(candidate_embeddings)

            if metric == SimilarityMetric.COSINE:
                # Manual cosine similarity calculation for batch
                similarities = []
                for candidate in candidate_matrix:
                    sim = self._cosine_similarity(query_vec, candidate)
                    similarities.append(sim)
                return similarities
            # Calculate individually for other metrics
            similarities = []
            for candidate in candidate_embeddings:
                sim = self.calculate_similarity(query_embedding, candidate, metric)
                similarities.append(sim)
            return similarities

        except Exception as e:
            logger.exception(f"Error calculating batch similarity: {e}")
            return []

    def find_most_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find most similar embeddings to query embedding.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            top_k: Number of top results to return

        Returns:
            List of results with index and similarity score
        """
        try:
            similarities = []

            for i, candidate in enumerate(candidate_embeddings):
                similarity = self.calculate_similarity(query_embedding, candidate)
                similarities.append(
                    {
                        "index": i,
                        "similarity": similarity,
                    },
                )

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            # Return top_k results
            return similarities[:top_k]

        except Exception as e:
            logger.exception(f"Error finding most similar embeddings: {e}")
            return []

    async def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Generate embeddings for text chunks.

        Args:
            chunks: List of text chunks with content

        Returns:
            List of chunks with embeddings added
        """
        try:
            if not chunks:
                return []

            # Extract text content
            texts = [chunk["content"] for chunk in chunks]

            # Generate embeddings
            embeddings = await self.generate_embeddings(texts)

            # Add embeddings to chunks
            for i, chunk in enumerate(chunks):
                if i < len(embeddings):
                    chunk["embedding"] = embeddings[i]
                else:
                    chunk["embedding"] = None

            return chunks

        except Exception as e:
            logger.exception(f"Error embedding chunks: {e}")
            return chunks

    def validate_embedding(self, embedding: list[float]) -> bool:
        """
        Validate embedding vector.

        Args:
            embedding: Embedding vector to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            if not embedding:
                return False

            # Check if it's a list of numbers
            if not all(isinstance(x, int | float) for x in embedding):
                return False

            # Check if it's not all zeros
            return not all(x == 0 for x in embedding)

        except Exception as e:
            logger.exception(f"Error validating embedding: {e}")
            return False

    def get_embedding_dimension(self, embedding: list[float]) -> int:
        """
        Get dimension of embedding vector.

        Args:
            embedding: Embedding vector

        Returns:
            Dimension of the embedding
        """
        try:
            return len(embedding) if embedding else 0
        except Exception as e:
            logger.exception(f"Error getting embedding dimension: {e}")
            return 0

    def reduce_embeddings_dimension(
        self,
        embeddings: list[list[float]],
        target_dimension: int = 2,
        method: str = "tsne",
    ) -> list[list[float]]:
        """
        Reduce embedding dimensions for visualization or analysis.

        NOTE: ML libraries (UMAP, scikit-learn) have been removed for performance.
        This method now returns the original embeddings truncated to target dimension.

        Args:
            embeddings: List of embedding vectors
            target_dimension: Target dimension (usually 2 or 3)
            method: Dimensionality reduction method (ignored, kept for compatibility)

        Returns:
            List of reduced embedding vectors (truncated)
        """
        try:
            if not embeddings:
                return []

            # Simple truncation instead of ML-based reduction
            reduced_embeddings = []
            for embedding in embeddings:
                if len(embedding) > target_dimension:
                    reduced_embeddings.append(embedding[:target_dimension])
                else:
                    reduced_embeddings.append(embedding)

            return reduced_embeddings

        except Exception as e:
            logger.exception(f"Error reducing embedding dimensions: {e}")
            return embeddings

    def cluster_embeddings(
        self,
        embeddings: list[list[float]],
        n_clusters: int = 5,
        method: str = "kmeans",
    ) -> dict[str, Any]:
        """
        Cluster embeddings to find similar groups.

        NOTE: ML libraries (scikit-learn) have been removed for performance.
        This method now returns a simple grouping based on first dimension.

        Args:
            embeddings: List of embedding vectors
            n_clusters: Number of clusters
            method: Clustering method (ignored, kept for compatibility)

        Returns:
            Clustering results with labels and metadata
        """
        try:
            if not embeddings:
                return {"labels": [], "centroids": [], "silhouette_score": 0.0}

            # Simple grouping based on first dimension instead of ML clustering
            labels = []
            for _i, embedding in enumerate(embeddings):
                if embedding:
                    # Simple grouping: assign to cluster based on first dimension value
                    cluster_id = int(abs(embedding[0]) * n_clusters) % n_clusters
                    labels.append(cluster_id)
                else:
                    labels.append(0)

            # Calculate simple centroids (average of each cluster)
            centroids = []
            for cluster_id in range(n_clusters):
                cluster_embeddings = [
                    emb for i, emb in enumerate(embeddings) if labels[i] == cluster_id
                ]
                if cluster_embeddings:
                    centroid = [
                        sum(dim) / len(cluster_embeddings)
                        for dim in zip(*cluster_embeddings, strict=False)
                    ]
                    centroids.append(centroid)
                else:
                    centroids.append(
                        [0.0] * len(embeddings[0]) if embeddings else [0.0],
                    )

            return {
                "labels": labels,
                "centroids": centroids,
                "silhouette_score": 0.5,  # Placeholder score
                "n_clusters": n_clusters,
                "method": "simple_grouping",
            }

        except Exception as e:
            logger.exception(f"Error clustering embeddings: {e}")
            return {"labels": [], "centroids": [], "silhouette_score": 0.0}

    def analyze_embedding_quality(
        self,
        embeddings: list[list[float]],
    ) -> dict[str, Any]:
        """
        Analyze the quality of embeddings.

        Args:
            embeddings: List of embedding vectors

        Returns:
            Quality analysis results
        """
        try:
            if not embeddings:
                return {}

            emb_array = np.array(embeddings)

            # Calculate various quality metrics
            magnitudes = np.linalg.norm(emb_array, axis=1)
            variances = np.var(emb_array, axis=1)

            # Calculate pairwise distances manually (no sklearn dependency)
            distances = []
            for i in range(len(emb_array)):
                for j in range(i + 1, len(emb_array)):
                    distance = np.linalg.norm(emb_array[i] - emb_array[j])
                    distances.append(distance)

            distances_no_diag = np.array(distances) if distances else np.array([])

            return {
                "n_embeddings": len(embeddings),
                "dimension": emb_array.shape[1],
                "magnitude_stats": {
                    "mean": float(np.mean(magnitudes)),
                    "std": float(np.std(magnitudes)),
                    "min": float(np.min(magnitudes)),
                    "max": float(np.max(magnitudes)),
                },
                "variance_stats": {
                    "mean": float(np.mean(variances)),
                    "std": float(np.std(variances)),
                    "min": float(np.min(variances)),
                    "max": float(np.max(variances)),
                },
                "distance_stats": {
                    "mean": float(np.mean(distances_no_diag)),
                    "std": float(np.std(distances_no_diag)),
                    "min": float(np.min(distances_no_diag)),
                    "max": float(np.max(distances_no_diag)),
                },
                "quality_score": float(np.mean(magnitudes) * np.mean(variances)),
            }

        except Exception as e:
            logger.exception(f"Error analyzing embedding quality: {e}")
            return {}

    def get_embedding_statistics(self) -> dict[str, Any]:
        """Get embedding service statistics."""
        return {
            "total_embeddings": self.embedding_stats["total_embeddings"],
            "total_processing_time": self.embedding_stats["total_processing_time"],
            "average_processing_time": self.embedding_stats["average_processing_time"],
            "cache_hits": self.embedding_stats["cache_hits"],
            "cache_misses": self.embedding_stats["cache_misses"],
            "cache_hit_rate": (
                self.embedding_stats["cache_hits"]
                / (
                    self.embedding_stats["cache_hits"]
                    + self.embedding_stats["cache_misses"]
                )
                if (
                    self.embedding_stats["cache_hits"]
                    + self.embedding_stats["cache_misses"]
                )
                > 0
                else 0.0
            ),
            "cache_size": len(self.embedding_cache),
            "available_models": list(self.model_configs.keys()),
        }

    def clear_cache(self):
        """Clear the embedding cache."""
        self.embedding_cache.clear()
        logger.info("Embedding cache cleared")

    def export_embeddings(
        self,
        embeddings: list[EmbeddingResult],
        format: str = "json",
    ) -> str:
        """
        Export embeddings to various formats.

        Args:
            embeddings: List of embedding results
            format: Export format ("json", "csv", "numpy")

        Returns:
            Exported data as string
        """
        try:
            if format == "json":
                data = []
                for emb in embeddings:
                    data.append(
                        {
                            "text": emb.text,
                            "embedding": emb.embedding,
                            "model": emb.model,
                            "dimension": emb.dimension,
                            "timestamp": emb.timestamp.isoformat(),
                            "metadata": emb.metadata,
                            "quality_score": emb.quality_score,
                        },
                    )
                return json.dumps(data, indent=2)

            if format == "csv":
                import csv
                import io

                output = io.StringIO()
                writer = csv.writer(output)

                # Write header
                if embeddings:
                    dimension = len(embeddings[0].embedding)
                    header = [
                        "text",
                        "model",
                        "dimension",
                        "timestamp",
                        "quality_score",
                    ]
                    header.extend([f"dim_{i}" for i in range(dimension)])
                    writer.writerow(header)

                # Write data
                for emb in embeddings:
                    row = [
                        emb.text,
                        emb.model,
                        emb.dimension,
                        emb.timestamp.isoformat(),
                        emb.quality_score or 0.0,
                    ]
                    row.extend(emb.embedding)
                    writer.writerow(row)

                return output.getvalue()

            if format == "numpy":
                # Export as numpy array
                emb_array = np.array([emb.embedding for emb in embeddings])
                return emb_array.tobytes().hex()

            raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            logger.exception(f"Error exporting embeddings: {e}")
            return ""

    async def create_embedding(
        self,
        text: str,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Create embedding for a single text."""
        try:
            embeddings = await self.generate_embeddings([text], model=model)
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.exception(f"Error creating embedding: {e}")
            return None

    async def search_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        top_k: int = 5,
    ) -> list[SimilarityResult]:
        """Search for similar embeddings."""
        try:
            similarities = self.find_most_similar(
                query_embedding,
                candidate_embeddings,
                top_k,
            )
            return [
                SimilarityResult(
                    text=item.get("text", ""),
                    similarity_score=item.get("similarity", 0.0),
                    rank=item.get("rank", 0),
                    metadata=item.get("metadata", {}),
                )
                for item in similarities
            ]
        except Exception as e:
            logger.exception(f"Error searching similar embeddings: {e}")
            return []

    async def store_embedding(self, embedding_data: dict) -> bool:
        """Store embedding data."""
        try:
            # This would typically store to a vector database
            # For now, just log the operation
            logger.info(
                f"Storing embedding: {embedding_data.get('content', '')[:50]}...",
            )
            return True
        except Exception as e:
            logger.exception(f"Error storing embedding: {e}")
            return False

    @property
    def weaviate_client(self):
        """Get weaviate client for testing."""
        from backend.app.core.weaviate_client import get_weaviate_client

        return get_weaviate_client()


# Global embedding service instance
embedding_service = EmbeddingService()
