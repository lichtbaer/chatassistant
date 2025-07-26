"""
Conversation Intelligence Service.

This module provides conversation intelligence features including summarization,
topic detection, sentiment analysis, and conversation analytics, integrating
with existing conversation and AI services.
"""

import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from loguru import logger

from backend.app.core.exceptions import AIError, ConfigurationError
from backend.app.core.exceptions import ValidationError as AppValidationError
from backend.app.schemas.conversation_intelligence import (
    ConversationAnalytics,
    ConversationIntelligenceRequest,
    ConversationIntelligenceResponse,
    ConversationSummary,
    IntelligenceMetrics,
    SentimentAnalysis,
    SentimentAnalysisRequest,
    SentimentType,
    SummaryRequest,
    SummaryType,
    TopicCategory,
    TopicDetectionRequest,
    TopicInfo,
)
from backend.app.services.cache_service import cache_service


class ConversationIntelligenceService:
    """Service for conversation intelligence features."""

    def __init__(self):
        self.metrics = self._initialize_metrics()
        self._cache_enabled = True
        self._ai_models = {
            "summarization": "gpt-4",
            "topic_detection": "gpt-4",
            "sentiment_analysis": "gpt-4",
            "analytics": "gpt-4",
        }

    def _initialize_metrics(self) -> IntelligenceMetrics:
        """Initialize intelligence metrics."""
        return IntelligenceMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            avg_processing_time=0.0,
            avg_summary_length=0.0,
            avg_topic_count=0.0,
            avg_confidence_score=0.0,
            avg_quality_score=0.0,
            user_satisfaction_score=0.0,
            analysis_type_usage={},
            model_usage={},
            error_counts={},
        )

    async def initialize(self) -> None:
        """Initialize conversation intelligence service."""
        try:
            # Initialize cache if available
            if hasattr(cache_service, "initialize"):
                await cache_service.initialize()
                self._cache_enabled = True
                logger.info(
                    "Conversation intelligence service initialized with caching",
                )
            else:
                self._cache_enabled = False
                logger.info(
                    "Conversation intelligence service initialized without caching",
                )

        except Exception as e:
            logger.error(f"Failed to initialize conversation intelligence service: {e}")
            raise ConfigurationError(
                f"Conversation intelligence service initialization failed: {str(e)}",
            )

    async def analyze_conversation(
        self,
        request: ConversationIntelligenceRequest,
    ) -> ConversationIntelligenceResponse:
        """
        Perform comprehensive conversation analysis.

        Args:
            request: Intelligence analysis request

        Returns:
            Intelligence analysis response
        """
        start_time = time.time()
        request_id = str(uuid4())

        try:
            # Validate request
            self._validate_intelligence_request(request)

            # Check cache first
            cache_key = self._create_cache_key(request)
            if self._cache_enabled:
                cached_result = await self._get_cached_result(cache_key)
                if cached_result:
                    self._update_metrics(True, time.time() - start_time, cached_result)
                    return cached_result

            # Get conversation data
            conversation = await self._get_conversation_data(request.conversation_id)
            if not conversation:
                raise AppValidationError(
                    f"Conversation {request.conversation_id} not found",
                )

            # Perform analysis
            analysis_results = await self._perform_analysis(request, conversation)

            # Create response
            response = ConversationIntelligenceResponse(
                conversation_id=request.conversation_id,
                request_id=request_id,
                **analysis_results,
                processing_time=time.time() - start_time,
                models_used=list(self._ai_models.values()),
                analysis_completed=request.analysis_types
                or ["summary", "topics", "sentiment", "analytics"],
                created_at=datetime.now(UTC),
            )

            # Cache results if enabled
            if self._cache_enabled:
                await self._cache_result(cache_key, response)

            # Update metrics
            self._update_metrics(True, time.time() - start_time, response)

            logger.info(
                f"Conversation intelligence analysis completed in {response.processing_time:.2f}s",
            )
            return response

        except Exception as e:
            self._update_metrics(False, time.time() - start_time, None, str(e))
            logger.error(f"Conversation intelligence analysis failed: {e}")
            raise AIError(f"Conversation intelligence analysis failed: {str(e)}")

    async def generate_summary(self, request: SummaryRequest) -> ConversationSummary:
        """Generate conversation summary."""
        start_time = time.time()

        try:
            # Get conversation data
            conversation = await self._get_conversation_data(request.conversation_id)
            if not conversation:
                raise AppValidationError(
                    f"Conversation {request.conversation_id} not found",
                )

            # Generate summary
            summary = await self._generate_summary_content(conversation, request)

            # Update metrics
            self._update_metrics(True, time.time() - start_time, None)

            return summary

        except Exception as e:
            self._update_metrics(False, time.time() - start_time, None, str(e))
            logger.error(f"Summary generation failed: {e}")
            raise AIError(f"Summary generation failed: {str(e)}")

    async def detect_topics(self, request: TopicDetectionRequest) -> list[TopicInfo]:
        """Detect conversation topics."""
        start_time = time.time()

        try:
            # Get conversation data
            conversation = await self._get_conversation_data(request.conversation_id)
            if not conversation:
                raise AppValidationError(
                    f"Conversation {request.conversation_id} not found",
                )

            # Detect topics
            topics = await self._detect_topics_content(conversation, request)

            # Update metrics
            self._update_metrics(True, time.time() - start_time, None)

            return topics

        except Exception as e:
            self._update_metrics(False, time.time() - start_time, None, str(e))
            logger.error(f"Topic detection failed: {e}")
            raise AIError(f"Topic detection failed: {str(e)}")

    async def analyze_sentiment(
        self,
        request: SentimentAnalysisRequest,
    ) -> SentimentAnalysis:
        """Analyze sentiment."""
        start_time = time.time()

        try:
            # Get text to analyze
            text_to_analyze = await self._get_text_for_analysis(request)

            # Analyze sentiment
            sentiment = await self._analyze_sentiment_content(text_to_analyze, request)

            # Update metrics
            self._update_metrics(True, time.time() - start_time, None)

            return sentiment

        except Exception as e:
            self._update_metrics(False, time.time() - start_time, None, str(e))
            logger.error(f"Sentiment analysis failed: {e}")
            raise AIError(f"Sentiment analysis failed: {str(e)}")

    async def _perform_analysis(
        self,
        request: ConversationIntelligenceRequest,
        conversation: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform the requested analysis."""
        results = {}

        # Generate summary if requested
        if request.generate_summary:
            summary_request = SummaryRequest(
                conversation_id=request.conversation_id,
                summary_type=request.summary_type,
                max_length=request.max_summary_length,
            )
            results["summary"] = await self._generate_summary_content(
                conversation,
                summary_request,
            )

        # Detect topics if requested
        if request.detect_topics:
            topic_request = TopicDetectionRequest(
                conversation_id=request.conversation_id,
                categories=request.topic_categories,
                min_confidence=request.min_topic_confidence,
            )
            results["topics"] = await self._detect_topics_content(
                conversation,
                topic_request,
            )

        # Analyze sentiment if requested
        if request.analyze_sentiment:
            sentiment_request = SentimentAnalysisRequest(
                conversation_id=request.conversation_id,
                include_emotions=request.include_emotion_analysis,
            )
            results["sentiment"] = await self._analyze_sentiment_content(
                self._get_conversation_text(conversation),
                sentiment_request,
            )

        # Generate analytics if requested
        if request.generate_analytics:
            results["analytics"] = await self._generate_analytics(conversation, request)

        return results

    async def _generate_summary_content(
        self,
        conversation: dict[str, Any],
        request: SummaryRequest,
    ) -> ConversationSummary:
        """Generate summary content using AI."""

        # Prepare conversation text
        conversation_text = self._get_conversation_text(conversation)

        # Create summary prompt based on type
        prompt = self._create_summary_prompt(conversation_text, request)

        # Generate summary using AI (simulated for now)
        summary_text = await self._call_ai_model(
            "summarization",
            prompt,
            request.max_length,
        )

        # Extract key elements
        key_points = await self._extract_key_points(conversation_text)
        action_items = await self._extract_action_items(conversation_text)
        decisions_made = await self._extract_decisions(conversation_text)
        questions_asked = await self._extract_questions(conversation_text)

        # Calculate metrics
        word_count = len(summary_text.split())
        token_count = len(summary_text.split())  # Simplified token counting
        original_length = len(conversation_text.split())
        compression_ratio = word_count / original_length if original_length > 0 else 0.0

        return ConversationSummary(
            conversation_id=request.conversation_id,
            summary_type=request.summary_type,
            summary_text=summary_text,
            word_count=word_count,
            token_count=token_count,
            compression_ratio=compression_ratio,
            key_points=key_points,
            action_items=action_items,
            decisions_made=decisions_made,
            questions_asked=questions_asked,
            participants=self._extract_participants(conversation),
            duration_minutes=self._calculate_duration(conversation),
            message_count=len(conversation.get("messages", [])),
            model_used=self._ai_models["summarization"],
            confidence_score=0.85,  # Simulated confidence
        )

    async def _detect_topics_content(
        self,
        conversation: dict[str, Any],
        request: TopicDetectionRequest,
    ) -> list[TopicInfo]:
        """Detect topics in conversation."""

        conversation_text = self._get_conversation_text(conversation)

        # Create topic detection prompt
        prompt = self._create_topic_detection_prompt(conversation_text, request)

        # Generate topics using AI (simulated for now)
        topics_response = await self._call_ai_model("topic_detection", prompt)

        # Parse topics from AI response
        topics = self._parse_topics_from_response(topics_response, request)

        # Add temporal information
        topics = self._add_temporal_info(topics, conversation)

        return topics[: request.max_topics]

    async def _analyze_sentiment_content(
        self,
        text: str,
        request: SentimentAnalysisRequest,
    ) -> SentimentAnalysis:
        """Analyze sentiment of text."""

        # Create sentiment analysis prompt
        prompt = self._create_sentiment_prompt(text, request)

        # Generate sentiment analysis using AI (simulated for now)
        sentiment_response = await self._call_ai_model("sentiment_analysis", prompt)

        # Parse sentiment from AI response
        sentiment_data = self._parse_sentiment_from_response(sentiment_response)

        return SentimentAnalysis(
            overall_sentiment=sentiment_data["overall_sentiment"],
            sentiment_score=sentiment_data["sentiment_score"],
            confidence=sentiment_data["confidence"],
            positive_score=sentiment_data["positive_score"],
            negative_score=sentiment_data["negative_score"],
            neutral_score=sentiment_data["neutral_score"],
            emotions=sentiment_data.get("emotions", {}),
            dominant_emotion=sentiment_data.get("dominant_emotion"),
            sentiment_trend=sentiment_data.get("sentiment_trend", "stable"),
            sentiment_changes=sentiment_data.get("sentiment_changes", []),
            analyzed_text=text,
            model_used=self._ai_models["sentiment_analysis"],
        )

    async def _generate_analytics(
        self,
        conversation: dict[str, Any],
        request: ConversationIntelligenceRequest,
    ) -> ConversationAnalytics:
        """Generate comprehensive conversation analytics."""

        messages = conversation.get("messages", [])

        # Basic metrics
        total_messages = len(messages)
        total_participants = len(
            {msg.get("user_id") for msg in messages if msg.get("user_id")},
        )
        duration_minutes = self._calculate_duration(conversation)

        # Message analysis
        avg_message_length = self._calculate_avg_message_length(messages)
        message_frequency = (
            total_messages / duration_minutes if duration_minutes > 0 else 0.0
        )
        response_times = self._calculate_response_times(messages)
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        # Participant analysis
        participant_activity = self._analyze_participant_activity(messages)
        participant_sentiment = await self._analyze_participant_sentiment(messages)
        participant_engagement = self._calculate_participant_engagement(messages)

        # Content analysis
        topics_detected = await self._detect_topics_content(
            conversation,
            TopicDetectionRequest(conversation_id=request.conversation_id),
        )
        sentiment_overview = await self._analyze_sentiment_content(
            self._get_conversation_text(conversation),
            SentimentAnalysisRequest(conversation_id=request.conversation_id),
        )
        key_phrases = await self._extract_key_phrases(
            self._get_conversation_text(conversation),
        )

        # Quality metrics
        conversation_quality_score = self._calculate_quality_score(messages)
        engagement_score = self._calculate_engagement_score(messages)
        clarity_score = self._calculate_clarity_score(messages)

        # Temporal analysis
        conversation_phases = self._identify_conversation_phases(messages)
        peak_activity_time = self._find_peak_activity_time(messages)
        lull_periods = self._identify_lull_periods(messages)

        return ConversationAnalytics(
            conversation_id=request.conversation_id,
            total_messages=total_messages,
            total_participants=total_participants,
            duration_minutes=duration_minutes,
            avg_message_length=avg_message_length,
            message_frequency=message_frequency,
            response_times=response_times,
            avg_response_time=avg_response_time,
            participant_activity=participant_activity,
            participant_sentiment=participant_sentiment,
            participant_engagement=participant_engagement,
            topics_detected=topics_detected,
            sentiment_overview=sentiment_overview,
            key_phrases=key_phrases,
            conversation_quality_score=conversation_quality_score,
            engagement_score=engagement_score,
            clarity_score=clarity_score,
            conversation_phases=conversation_phases,
            peak_activity_time=peak_activity_time,
            lull_periods=lull_periods,
        )

    async def _call_ai_model(
        self,
        model_type: str,
        prompt: str,
        max_length: int | None = None,
    ) -> str:
        """Call AI model for analysis (simulated implementation)."""
        # This would integrate with existing AI service
        # For now, return simulated responses

        if model_type == "summarization":
            return f"Simulated summary for: {prompt[:100]}..."
        if model_type == "topic_detection":
            return "Simulated topics: technical, business, general"
        if model_type == "sentiment_analysis":
            return "Simulated sentiment: positive, 0.7, 0.8"
        return "Simulated AI response"

    def _create_summary_prompt(self, text: str, request: SummaryRequest) -> str:
        """Create summary generation prompt."""
        summary_type_instructions = {
            SummaryType.EXECUTIVE: "Create a concise executive summary",
            SummaryType.DETAILED: "Create a detailed summary",
            SummaryType.ACTION_ITEMS: "Focus on action items and next steps",
            SummaryType.KEY_POINTS: "Extract key points and insights",
            SummaryType.TIMELINE: "Organize information chronologically",
        }

        instruction = summary_type_instructions.get(
            request.summary_type,
            "Create a summary",
        )

        return f"""
        {instruction} of the following conversation:

        {text}

        Maximum length: {request.max_length} words
        Include action items: {request.include_action_items}
        Include key points: {request.include_key_points}
        """

    def _create_topic_detection_prompt(
        self,
        text: str,
        request: TopicDetectionRequest,
    ) -> str:
        """Create topic detection prompt."""
        categories = (
            [cat.value for cat in request.categories] if request.categories else []
        )
        category_filter = (
            f"Focus on categories: {', '.join(categories)}" if categories else ""
        )

        return f"""
        Detect topics in the following conversation:

        {text}

        {category_filter}
        Minimum confidence: {request.min_confidence}
        Maximum topics: {request.max_topics}
        Include keywords: {request.include_keywords}
        Include context: {request.include_context}
        """

    def _create_sentiment_prompt(
        self,
        text: str,
        request: SentimentAnalysisRequest,
    ) -> str:
        """Create sentiment analysis prompt."""
        return f"""
        Analyze the sentiment of the following text:

        {text}

        Include emotions: {request.include_emotions}
        Include trends: {request.include_trends}
        Granular analysis: {request.granular_analysis}
        Custom emotions: {request.custom_emotions}
        """

    def _get_conversation_data(self, conversation_id: str) -> dict[str, Any] | None:
        """Get conversation data from service."""
        # This would integrate with existing conversation service
        # For now, return simulated data
        return {
            "id": conversation_id,
            "title": "Sample Conversation",
            "messages": [
                {
                    "content": "Hello, how can I help you?",
                    "user_id": "user1",
                    "timestamp": datetime.now(UTC),
                },
                {
                    "content": "I need help with the API",
                    "user_id": "user2",
                    "timestamp": datetime.now(UTC),
                },
                {
                    "content": "Sure, what specific issue are you facing?",
                    "user_id": "user1",
                    "timestamp": datetime.now(UTC),
                },
            ],
        }

    def _get_conversation_text(self, conversation: dict[str, Any]) -> str:
        """Extract text from conversation."""
        messages = conversation.get("messages", [])
        return " ".join(msg.get("content", "") for msg in messages)

    def _extract_participants(self, conversation: dict[str, Any]) -> list[str]:
        """Extract participant IDs from conversation."""
        messages = conversation.get("messages", [])
        return list({msg.get("user_id") for msg in messages if msg.get("user_id")})

    def _calculate_duration(self, conversation: dict[str, Any]) -> float:
        """Calculate conversation duration in minutes."""
        messages = conversation.get("messages", [])
        if len(messages) < 2:
            return 0.0

        start_time = messages[0].get("timestamp", datetime.now(UTC))
        end_time = messages[-1].get("timestamp", datetime.now(UTC))

        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        duration = end_time - start_time
        return duration.total_seconds() / 60.0

    async def _extract_key_points(self, text: str) -> list[str]:
        """Extract key points from text."""
        # Simulated key points extraction
        return ["Key point 1", "Key point 2", "Key point 3"]

    async def _extract_action_items(self, text: str) -> list[str]:
        """Extract action items from text."""
        # Simulated action items extraction
        return ["Action item 1", "Action item 2"]

    async def _extract_decisions(self, text: str) -> list[str]:
        """Extract decisions from text."""
        # Simulated decisions extraction
        return ["Decision 1", "Decision 2"]

    async def _extract_questions(self, text: str) -> list[str]:
        """Extract questions from text."""
        # Simulated questions extraction
        return ["Question 1", "Question 2"]

    def _parse_topics_from_response(
        self,
        response: str,
        request: TopicDetectionRequest,
    ) -> list[TopicInfo]:
        """Parse topics from AI response."""
        # Simulated topic parsing
        topics = []
        for i, topic_name in enumerate(["Technical", "Business", "General"]):
            topic = TopicInfo(
                topic=topic_name,
                category=(
                    TopicCategory.TECHNICAL
                    if i == 0
                    else TopicCategory.BUSINESS if i == 1 else TopicCategory.GENERAL
                ),
                confidence=0.8 - i * 0.1,
                keywords=[f"keyword_{i}_{j}" for j in range(3)],
                frequency=i + 1,
                message_indices=[i * 2, i * 2 + 1],
                context_snippets=[f"Context snippet {i}"],
            )
            topics.append(topic)
        return topics

    def _parse_sentiment_from_response(self, response: str) -> dict[str, Any]:
        """Parse sentiment from AI response."""
        # Simulated sentiment parsing
        return {
            "overall_sentiment": SentimentType.POSITIVE,
            "sentiment_score": 0.7,
            "confidence": 0.85,
            "positive_score": 0.7,
            "negative_score": 0.1,
            "neutral_score": 0.2,
            "emotions": {"joy": 0.6, "confidence": 0.4},
            "dominant_emotion": "joy",
            "sentiment_trend": "stable",
            "sentiment_changes": [],
        }

    def _add_temporal_info(
        self,
        topics: list[TopicInfo],
        conversation: dict[str, Any],
    ) -> list[TopicInfo]:
        """Add temporal information to topics."""
        messages = conversation.get("messages", [])
        if not messages:
            return topics

        start_time = messages[0].get("timestamp", datetime.now(UTC))
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)

        for topic in topics:
            if topic.message_indices:
                first_index = min(topic.message_indices)
                last_index = max(topic.message_indices)

                if first_index < len(messages):
                    topic.first_mentioned = messages[first_index].get(
                        "timestamp",
                        start_time,
                    )
                if last_index < len(messages):
                    topic.last_mentioned = messages[last_index].get(
                        "timestamp",
                        start_time,
                    )

        return topics

    async def _get_text_for_analysis(self, request: SentimentAnalysisRequest) -> str:
        """Get text for sentiment analysis."""
        if request.text:
            return request.text
        if request.message_id:
            # Get specific message
            return "Sample message content"
        if request.conversation_id:
            # Get conversation text
            conversation = self._get_conversation_data(request.conversation_id)
            return self._get_conversation_text(conversation) if conversation else ""
        raise AppValidationError("No text source provided for analysis")

    def _calculate_avg_message_length(self, messages: list[dict[str, Any]]) -> float:
        """Calculate average message length."""
        if not messages:
            return 0.0
        total_length = sum(len(msg.get("content", "")) for msg in messages)
        return total_length / len(messages)

    def _calculate_response_times(self, messages: list[dict[str, Any]]) -> list[float]:
        """Calculate response times between messages."""
        response_times = []
        for i in range(1, len(messages)):
            prev_time = messages[i - 1].get("timestamp", datetime.now(UTC))
            curr_time = messages[i].get("timestamp", datetime.now(UTC))

            if isinstance(prev_time, str):
                prev_time = datetime.fromisoformat(prev_time)
            if isinstance(curr_time, str):
                curr_time = datetime.fromisoformat(curr_time)

            response_time = (curr_time - prev_time).total_seconds()
            response_times.append(response_time)

        return response_times

    def _analyze_participant_activity(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Analyze participant activity."""
        activity = {}
        for msg in messages:
            user_id = msg.get("user_id", "unknown")
            activity[user_id] = activity.get(user_id, 0) + 1
        return activity

    async def _analyze_participant_sentiment(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, SentimentType]:
        """Analyze sentiment per participant."""
        # Simulated participant sentiment analysis
        participants = {msg.get("user_id") for msg in messages if msg.get("user_id")}
        return dict.fromkeys(participants, SentimentType.POSITIVE)

    def _calculate_participant_engagement(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Calculate engagement scores per participant."""
        # Simulated engagement calculation
        participants = {msg.get("user_id") for msg in messages if msg.get("user_id")}
        return dict.fromkeys(participants, 0.8)

    async def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract key phrases from text."""
        # Simulated key phrase extraction
        return ["key phrase 1", "key phrase 2", "key phrase 3"]

    def _calculate_quality_score(self, messages: list[dict[str, Any]]) -> float:
        """Calculate conversation quality score."""
        if not messages:
            return 0.0

        # Simple quality scoring based on message length and variety
        avg_length = self._calculate_avg_message_length(messages)
        participant_variety = len({msg.get("user_id") for msg in messages})

        length_score = min(1.0, avg_length / 100.0)
        variety_score = min(1.0, participant_variety / 5.0)

        return (length_score + variety_score) / 2.0

    def _calculate_engagement_score(self, messages: list[dict[str, Any]]) -> float:
        """Calculate engagement score."""
        if not messages:
            return 0.0

        # Simple engagement scoring based on response times and message frequency
        response_times = self._calculate_response_times(messages)
        if not response_times:
            return 0.5

        avg_response_time = sum(response_times) / len(response_times)
        # Lower response time = higher engagement
        return max(0.0, 1.0 - (avg_response_time / 300.0))  # 5 minutes max

    def _calculate_clarity_score(self, messages: list[dict[str, Any]]) -> float:
        """Calculate conversation clarity score."""
        if not messages:
            return 0.0

        # Simple clarity scoring based on message length consistency
        lengths = [len(msg.get("content", "")) for msg in messages]
        if not lengths:
            return 0.0

        avg_length = sum(lengths) / len(lengths)
        variance = sum((length - avg_length) ** 2 for length in lengths) / len(lengths)

        # Lower variance = higher clarity
        return max(0.0, 1.0 - (variance / 10000.0))

    def _identify_conversation_phases(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify conversation phases."""
        # Simulated phase identification
        return [
            {"phase": "introduction", "start": 0, "end": 2},
            {"phase": "discussion", "start": 3, "end": len(messages) - 1},
        ]

    def _find_peak_activity_time(
        self,
        messages: list[dict[str, Any]],
    ) -> datetime | None:
        """Find peak activity time."""
        if not messages:
            return None

        # Return middle message timestamp as peak
        middle_index = len(messages) // 2
        peak_time = messages[middle_index].get("timestamp", datetime.now(UTC))

        if isinstance(peak_time, str):
            peak_time = datetime.fromisoformat(peak_time)

        return peak_time

    def _identify_lull_periods(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify periods of low activity."""
        # Simulated lull period identification
        return [
            {
                "start": datetime.now(UTC),
                "end": datetime.now(UTC),
                "duration_minutes": 5.0,
            },
        ]

    def _validate_intelligence_request(
        self,
        request: ConversationIntelligenceRequest,
    ) -> None:
        """Validate intelligence request."""
        if not request.conversation_id:
            raise AppValidationError("Conversation ID is required")

        if not request.analysis_types and not any(
            [
                request.generate_summary,
                request.detect_topics,
                request.analyze_sentiment,
                request.generate_analytics,
            ],
        ):
            raise AppValidationError("At least one analysis type must be requested")

    def _create_cache_key(self, request: ConversationIntelligenceRequest) -> str:
        """Create cache key for request."""
        import hashlib
        import json

        key_data = {
            "conversation_id": request.conversation_id,
            "analysis_types": request.analysis_types,
            "summary_type": (
                request.summary_type.value if request.summary_type else None
            ),
            "max_summary_length": request.max_summary_length,
            "min_topic_confidence": request.min_topic_confidence,
        }

        return hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode(), usedforsecurity=False
        ).hexdigest()

    async def _get_cached_result(
        self,
        cache_key: str,
    ) -> ConversationIntelligenceResponse | None:
        """Get cached intelligence result."""
        try:
            cached_data = await cache_service.get(
                cache_key=cache_key,
                namespace="intelligence_results",
            )
            if cached_data:
                return ConversationIntelligenceResponse(**cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached intelligence result: {e}")
        return None

    async def _cache_result(
        self,
        cache_key: str,
        response: ConversationIntelligenceResponse,
    ) -> None:
        """Cache intelligence result."""
        try:
            await cache_service.set(
                cache_key=cache_key,
                data=response.dict(),
                namespace="intelligence_results",
                ttl=1800,  # 30 minutes
            )
        except Exception as e:
            logger.warning(f"Failed to cache intelligence result: {e}")

    def _update_metrics(
        self,
        success: bool,
        processing_time: float,
        response: ConversationIntelligenceResponse | None = None,
        error: str | None = None,
    ) -> None:
        """Update intelligence metrics."""
        self.metrics.total_requests += 1

        if success:
            self.metrics.successful_requests += 1
            self.metrics.avg_processing_time = (
                self.metrics.avg_processing_time
                * (self.metrics.successful_requests - 1)
                + processing_time
            ) / self.metrics.successful_requests

            if response:
                # Update analysis type usage
                for analysis_type in response.analysis_completed:
                    self.metrics.analysis_type_usage[analysis_type] = (
                        self.metrics.analysis_type_usage.get(analysis_type, 0) + 1
                    )

                # Update model usage
                for model in response.models_used:
                    self.metrics.model_usage[model] = (
                        self.metrics.model_usage.get(model, 0) + 1
                    )

                # Update quality metrics
                if response.summary:
                    self.metrics.avg_summary_length = (
                        self.metrics.avg_summary_length
                        * (self.metrics.successful_requests - 1)
                        + response.summary.word_count
                    ) / self.metrics.successful_requests

                if response.topics:
                    self.metrics.avg_topic_count = (
                        self.metrics.avg_topic_count
                        * (self.metrics.successful_requests - 1)
                        + len(response.topics)
                    ) / self.metrics.successful_requests
        else:
            self.metrics.failed_requests += 1
            if error:
                self.metrics.error_counts[error] = (
                    self.metrics.error_counts.get(error, 0) + 1
                )

    async def get_metrics(self) -> IntelligenceMetrics:
        """Get current intelligence metrics."""
        return self.metrics


# Global conversation intelligence service instance
conversation_intelligence_service = ConversationIntelligenceService()
