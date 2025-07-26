"""
AI Service for the AI Assistant Platform.

This module provides AI integration using LiteLLM for multiple providers,
cost tracking, embedding generation, and RAG (Retrieval-Augmented Generation).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

try:
    import litellm
    from litellm import acompletion, completion

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("LiteLLM not available. AI features will be disabled.")

from backend.app.core.config import get_settings
from backend.app.services.tool_service import tool_service
from backend.app.services.weaviate_service import weaviate_service
from backend.app.tools.mcp_tool import mcp_manager


@dataclass
class CostInfo:
    """Cost information for AI usage."""

    model: str
    tokens_used: int
    cost_usd: float
    timestamp: datetime
    user_id: str | None = None
    conversation_id: str | None = None


class CostTracker:
    """Track AI usage costs."""

    def __init__(self):
        """Initialize cost tracker."""
        self.costs: list[CostInfo] = []
        self.total_cost = 0.0
        self.total_tokens = 0

    def add_cost(self, cost_info: CostInfo):
        """Add cost information."""
        self.costs.append(cost_info)
        self.total_cost += cost_info.cost_usd
        self.total_tokens += cost_info.tokens_used

        logger.info(
            f"AI Cost: ${cost_info.cost_usd:.4f} for {cost_info.tokens_used} tokens "
            f"using {cost_info.model}",
        )

    def get_total_cost(self) -> float:
        """Get total cost."""
        return self.total_cost

    def get_total_tokens(self) -> int:
        """Get total tokens used."""
        return self.total_tokens

    def get_costs_by_user(self, user_id: str) -> list[CostInfo]:
        """Get costs for specific user."""
        return [cost for cost in self.costs if cost.user_id == user_id]

    def get_costs_by_conversation(self, conversation_id: str) -> list[CostInfo]:
        """Get costs for specific conversation."""
        return [cost for cost in self.costs if cost.conversation_id == conversation_id]


@dataclass
class AIResponse:
    """AI response data structure."""

    content: str
    message_type: str = "text"
    metadata: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    context_used: list[dict[str, Any]] | None = None


class AIService:
    """AI service for managing multiple providers and models."""

    def __init__(self):
        """Initialize AI service."""
        if not LITELLM_AVAILABLE:
            logger.error("LiteLLM not available. AI service will be disabled.")
            self.enabled = False
            return

        self.enabled = True
        self.providers = {}
        self.models = {}
        self.cost_tracker = CostTracker()

        # Initialize LiteLLM
        self._setup_litellm()
        self._load_providers()
        self._load_models()

    def _setup_litellm(self):
        """Setup LiteLLM configuration."""
        try:
            # Configure LiteLLM
            litellm.set_verbose = get_settings().debug

            # Set default model
            litellm.default_model = get_settings().default_ai_model

            # Configure proxy host if provided
            if get_settings().litellm_proxy_host:
                import os

                os.environ["LITELLM_PROXY_HOST"] = get_settings().litellm_proxy_host
                logger.info(
                    f"LiteLLM proxy host configured: {get_settings().litellm_proxy_host}",
                )

            logger.info("LiteLLM configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure LiteLLM: {e}")
            self.enabled = False

    def _load_providers(self):
        """Load AI providers from configuration."""
        self.providers = {
            "openai": {
                "name": "OpenAI",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                "enabled": bool(get_settings().openai_api_key),
                "api_key": get_settings().openai_api_key,
            },
            "anthropic": {
                "name": "Anthropic",
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "enabled": bool(get_settings().anthropic_api_key),
                "api_key": get_settings().anthropic_api_key,
            },
            "google": {
                "name": "Google",
                "models": ["gemini-pro", "gemini-pro-vision"],
                "enabled": bool(get_settings().google_api_key),
                "api_key": get_settings().google_api_key,
            },
        }

        # Set environment variables for LiteLLM
        if get_settings().openai_api_key:
            import os

            os.environ["OPENAI_API_KEY"] = get_settings().openai_api_key

        if get_settings().anthropic_api_key:
            import os

            os.environ["ANTHROPIC_API_KEY"] = get_settings().anthropic_api_key

        if get_settings().google_api_key:
            import os

            os.environ["GOOGLE_API_KEY"] = get_settings().google_api_key

    def _load_models(self):
        """Load available models."""
        self.models = {
            "gpt-4": {
                "provider": "openai",
                "max_tokens": 8192,
                "cost_per_1k_tokens": 0.03,
                "supports_tools": True,
            },
            "gpt-4-turbo": {
                "provider": "openai",
                "max_tokens": 128000,
                "cost_per_1k_tokens": 0.01,
                "supports_tools": True,
            },
            "gpt-3.5-turbo": {
                "provider": "openai",
                "max_tokens": 4096,
                "cost_per_1k_tokens": 0.002,
                "supports_tools": True,
            },
            "claude-3-opus": {
                "provider": "anthropic",
                "max_tokens": 200000,
                "cost_per_1k_tokens": 0.015,
                "supports_tools": True,
            },
            "claude-3-sonnet": {
                "provider": "anthropic",
                "max_tokens": 200000,
                "cost_per_1k_tokens": 0.003,
                "supports_tools": True,
            },
            "claude-3-haiku": {
                "provider": "anthropic",
                "max_tokens": 200000,
                "cost_per_1k_tokens": 0.00025,
                "supports_tools": True,
            },
            "gemini-pro": {
                "provider": "google",
                "max_tokens": 32768,
                "cost_per_1k_tokens": 0.0005,
                "supports_tools": False,
            },
        }

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        user_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs,
    ):
        """
        Stream chat completion responses.

        Yields:
            dict: Streaming response chunks
        """
        if not self.enabled:
            logger.error("AI service is disabled")
            return

        try:
            # Get default model if none specified
            if not model:
                model = self.default_model

            # Prepare completion parameters
            completion_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,  # Enable streaming
            }

            if max_tokens:
                completion_params["max_tokens"] = max_tokens

            if tools:
                completion_params["tools"] = tools
                completion_params["tool_choice"] = tool_choice

            # Add any additional parameters
            completion_params.update(kwargs)

            logger.info(f"Starting streaming completion with model: {model}")

            # Stream the response
            async for chunk in acompletion(**completion_params):
                if chunk and chunk.choices:
                    choice = chunk.choices[0]

                    # Track cost if available
                    if hasattr(chunk, "usage") and chunk.usage:
                        self._track_cost(
                            {"usage": chunk.usage},
                            model,
                            user_id,
                            conversation_id,
                        )

                    yield {
                        "id": chunk.id if hasattr(chunk, "id") else None,
                        "object": chunk.object if hasattr(chunk, "object") else None,
                        "created": chunk.created if hasattr(chunk, "created") else None,
                        "model": chunk.model if hasattr(chunk, "model") else model,
                        "choices": [
                            {
                                "index": choice.index,
                                "delta": {
                                    "content": (
                                        choice.delta.content
                                        if hasattr(choice.delta, "content")
                                        else None
                                    ),
                                    "role": (
                                        choice.delta.role
                                        if hasattr(choice.delta, "role")
                                        else None
                                    ),
                                    "tool_calls": (
                                        choice.delta.tool_calls
                                        if hasattr(choice.delta, "tool_calls")
                                        else None
                                    ),
                                },
                                "finish_reason": (
                                    choice.finish_reason
                                    if hasattr(choice, "finish_reason")
                                    else None
                                ),
                            }
                        ],
                        "usage": chunk.usage if hasattr(chunk, "usage") else None,
                    }

        except Exception as e:
            logger.error(f"Streaming completion error: {e}")
            yield {
                "error": str(e),
                "choices": [
                    {
                        "delta": {"content": f"Error: {str(e)}"},
                        "finish_reason": "error",
                    }
                ],
            }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        user_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Generate chat completion using LiteLLM.

        Args:
            messages: List of message dictionaries
            model: AI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools for function calling
            tool_choice: Tool choice strategy
            user_id: User ID for cost tracking
            conversation_id: Conversation ID for cost tracking
            **kwargs: Additional parameters

        Returns:
            Completion response
        """
        if not self.enabled:
            raise RuntimeError("AI service is disabled")

        # Use default model if none specified
        if not model:
            model = get_settings().default_ai_model

        # Validate model
        if model not in self.models:
            raise ValueError(f"Model {model} not supported")

        # Get model info
        model_info = self.models[model]

        # Set max_tokens if not provided
        if not max_tokens:
            max_tokens = model_info["max_tokens"]

        # Prepare completion parameters
        completion_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Add tools if supported
        if tools and model_info["supports_tools"]:
            completion_params["tools"] = tools
            completion_params["tool_choice"] = tool_choice

        try:
            # Generate completion
            logger.info(f"Generating completion with model {model}")
            response = await acompletion(**completion_params)

            # Track cost
            self._track_cost(response, model, user_id, conversation_id)

            return response

        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            raise

    def _track_cost(
        self,
        response: dict,
        model: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ):
        """Track cost for AI usage."""
        try:
            # Extract usage information
            usage = response.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            # Calculate cost
            model_info = self.models.get(model, {})
            cost_per_1k = model_info.get("cost_per_1k_tokens", 0)
            cost_usd = (tokens_used / 1000) * cost_per_1k

            # Create cost info
            cost_info = CostInfo(
                model=model,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                timestamp=datetime.utcnow(),
                user_id=user_id,
                conversation_id=conversation_id,
            )

            # Add to tracker
            self.cost_tracker.add_cost(cost_info)

        except Exception as e:
            logger.warning(f"Failed to track cost: {e}")

    async def get_embeddings(
        self,
        text: str,
        model: str = "text-embedding-ada-002",
    ) -> list[float]:
        """
        Generate embeddings for text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            List of embedding values
        """
        if not self.enabled:
            raise RuntimeError("AI service is disabled")

        try:
            # Use LiteLLM for embeddings
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": text}],
                max_tokens=1,  # We only need embeddings, not completion
            )

            # Extract embeddings from response
            # Note: This is a simplified approach. In practice, you'd use
            # the embeddings endpoint directly
            return response.get("embeddings", [])

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def get_available_models(self) -> dict[str, dict]:
        """Get list of available models."""
        return self.models

    def get_available_providers(self) -> dict[str, dict]:
        """Get list of available providers."""
        return self.providers

    def get_cost_summary(self) -> dict[str, Any]:
        """Get cost summary."""
        return {
            "total_cost": self.cost_tracker.get_total_cost(),
            "total_tokens": self.cost_tracker.get_total_tokens(),
            "costs": self.cost_tracker.costs,
        }

    def is_enabled(self) -> bool:
        """Check if AI service is enabled."""
        return self.enabled

    def health_check(self) -> dict[str, Any]:
        """Health check for AI service."""
        return {
            "status": "healthy" if self.enabled else "disabled",
            "enabled": self.enabled,
            "litellm_available": LITELLM_AVAILABLE,
            "providers_count": len(
                [p for p in self.providers.values() if p.get("enabled", True)]
            ),
            "models_count": len(self.models),
            "total_cost": self.cost_tracker.get_total_cost(),
        }

    async def chat_completion_with_rag_stream(
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
        **kwargs,
    ):
        """
        Stream chat completion with RAG (Retrieval-Augmented Generation).

        Yields:
            dict: Streaming response chunks with context
        """
        if not self.enabled:
            logger.error("AI service is disabled")
            return

        try:
            # Get the last user message for context search
            last_user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            context_chunks = []
            if use_knowledge_base and last_user_message:
                # Search knowledge base for relevant context
                context_chunks = await self._search_knowledge_for_context(
                    last_user_message,
                    user_id,
                    max_context_chunks,
                )

            # Prepare tools if enabled
            tools = None
            if use_tools and last_user_message:
                tools = await self._prepare_tools_for_completion(last_user_message)

            # Create enhanced messages with context
            enhanced_messages = messages.copy()
            if context_chunks:
                # Add system context message
                system_context = self._create_system_context(context_chunks)
                enhanced_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_context,
                    },
                )

            # Stream the response
            async for chunk in self.chat_completion_stream(
                messages=enhanced_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                user_id=user_id,
                conversation_id=conversation_id,
                **kwargs,
            ):
                # Add context information to the chunk
                if context_chunks:
                    chunk["context_chunks"] = context_chunks
                    chunk["context_count"] = len(context_chunks)

                yield chunk

        except Exception as e:
            logger.error(f"RAG streaming error: {e}")
            yield {
                "error": str(e),
                "choices": [
                    {
                        "delta": {"content": f"Error: {str(e)}"},
                        "finish_reason": "error",
                    }
                ],
            }

    async def chat_completion_with_rag(
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
        **kwargs,
    ) -> dict[str, Any]:
        """
        Generate chat completion with RAG (Retrieval-Augmented Generation).

        Args:
            messages: List of message dictionaries
            user_id: User ID for context retrieval
            conversation_id: Conversation ID for context
            model: AI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            use_knowledge_base: Whether to use knowledge base for context
            use_tools: Whether to enable tool usage
            max_context_chunks: Maximum number of context chunks to include
            **kwargs: Additional parameters

        Returns:
            Completion response with RAG context
        """
        if not self.enabled:
            raise RuntimeError("AI service is disabled")

        # Get the latest user message for context retrieval
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message:
            return await self.chat_completion(
                messages,
                model,
                temperature,
                max_tokens,
                **kwargs,
            )

        # Prepare enhanced messages with context
        enhanced_messages = messages.copy()

        # Add knowledge base context if enabled
        if use_knowledge_base:
            context = await self._search_knowledge_for_context(
                user_message,
                user_id,
                max_context_chunks,
            )
            if context:
                system_context = self._create_system_context(context)
                # Insert system context after the first system message or at the beginning
                if enhanced_messages and enhanced_messages[0].get("role") == "system":
                    enhanced_messages.insert(
                        1,
                        {"role": "system", "content": system_context},
                    )
                else:
                    enhanced_messages.insert(
                        0,
                        {"role": "system", "content": system_context},
                    )

        # Prepare tools if enabled
        tools = None
        if use_tools:
            tools = await self._prepare_tools_for_completion(user_message)

        # Generate completion with enhanced context
        return await self.chat_completion(
            messages=enhanced_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            user_id=user_id,
            conversation_id=conversation_id,
            **kwargs,
        )

    async def _search_knowledge_for_context(
        self,
        query: str,
        user_id: str,
        max_chunks: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge base for relevant context.

        Args:
            query: Search query
            user_id: User ID for filtering
            max_chunks: Maximum number of chunks to return

        Returns:
            List of relevant context chunks
        """
        try:
            # Search in knowledge base
            knowledge_results = weaviate_service.semantic_search_knowledge(
                query=query,
                limit=max_chunks,
            )

            # Search in conversation history
            conversation_results = weaviate_service.semantic_search_messages(
                query=query,
                conversation_id=None,  # Search across all conversations
                limit=max_chunks,
            )

            # Combine and rank results
            all_results = []

            # Add knowledge base results
            for result in knowledge_results:
                all_results.append(
                    {
                        "content": result.get("content", ""),
                        "source": "knowledge_base",
                        "metadata": result.get("metadata", {}),
                        "relevance_score": result.get("score", 0.0),
                    },
                )

            # Add conversation results
            for result in conversation_results:
                all_results.append(
                    {
                        "content": result.get("content", ""),
                        "source": "conversation",
                        "metadata": result.get("metadata", {}),
                        "relevance_score": result.get("score", 0.0),
                    },
                )

            # Sort by relevance and take top results
            all_results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

            return all_results[:max_chunks]

        except Exception as e:
            logger.error(f"Error searching knowledge for context: {e}")
            return []

    def _create_system_context(self, context_chunks: list[dict[str, Any]]) -> str:
        """
        Create system context from knowledge chunks.

        Args:
            context_chunks: List of context chunks

        Returns:
            Formatted system context
        """
        if not context_chunks:
            return ""

        context_parts = ["Relevante Informationen aus der Knowledge Base:"]

        for i, chunk in enumerate(context_chunks, 1):
            content = chunk.get("content", "").strip()
            source = chunk.get("source", "unknown")
            metadata = chunk.get("metadata", {})

            if content:
                context_parts.append(f"\n{i}. {content}")
                if source == "knowledge_base" and metadata.get("title"):
                    context_parts.append(f"   Quelle: {metadata.get('title')}")

        context_parts.append(
            "\nVerwende diese Informationen, um präzise und hilfreiche Antworten zu geben.",
        )

        return "\n".join(context_parts)

    async def _prepare_tools_for_completion(
        self,
        user_message: str,
    ) -> list[dict[str, Any]]:
        """
        Prepare available tools for AI completion.

        Args:
            user_message: User message to determine relevant tools

        Returns:
            List of tool definitions for AI
        """
        try:
            # Get all available tools
            all_tools = tool_service.get_all_tools()
            mcp_tools = mcp_manager.get_all_tools()

            # Combine tools
            combined_tools = []

            # Add regular tools
            for tool in all_tools:
                if tool.get("status") == "active":
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                    combined_tools.append(tool_def)

            # Add MCP tools
            for tool in mcp_tools:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
                combined_tools.append(tool_def)

            return combined_tools

        except Exception as e:
            logger.error(f"Error preparing tools for completion: {e}")
            return []

    async def execute_tool_call(
        self,
        tool_call: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """
        Execute a tool call from AI response.

        Args:
            tool_call: Tool call from AI response
            user_id: User ID for execution context

        Returns:
            Tool execution result
        """
        try:
            tool_name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", {})

            if not tool_name:
                return {"error": "No tool name provided"}

            # Try to execute as regular tool first
            try:
                result = await tool_service.execute_tool(
                    tool_name,
                    user_id,
                    **arguments,
                )
                return {
                    "success": True,
                    "result": result,
                    "tool_type": "regular",
                }
            except Exception as e:
                logger.warning(f"Regular tool execution failed for {tool_name}: {e}")

            # Try to execute as MCP tool
            try:
                mcp_result = await mcp_manager.execute_tool(tool_name, **arguments)
                return {
                    "success": True,
                    "result": mcp_result,
                    "tool_type": "mcp",
                }
            except Exception as e:
                logger.warning(f"MCP tool execution failed for {tool_name}: {e}")

            return {"error": f"Tool {tool_name} not found or execution failed"}

        except Exception as e:
            logger.error(f"Error executing tool call: {e}")
            return {"error": str(e)}

    async def get_embeddings_batch(
        self,
        texts: list[str],
        model: str = "text-embedding-ada-002",
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding lists
        """
        if not self.enabled:
            raise RuntimeError("AI service is disabled")

        try:
            embeddings = []
            for text in texts:
                embedding = await self.get_embeddings(text, model)
                embeddings.append(embedding)
            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> AIResponse:
        """Generate AI response from messages."""
        try:
            response = await self.chat_completion(messages, model=model)
            return AIResponse(
                content=response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", ""),
                metadata=response,
            )
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return AIResponse(content="Sorry, I encountered an error.")

    async def generate_response_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        model: str | None = None,
    ) -> AIResponse:
        """Generate AI response with tool calls."""
        try:
            response = await self.chat_completion(messages, tools=tools, model=model)
            return AIResponse(
                content=response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", ""),
                tool_calls=response.get("choices", [{}])[0]
                .get("message", {})
                .get("tool_calls"),
                metadata=response,
            )
        except Exception as e:
            logger.error(f"Error generating response with tools: {e}")
            return AIResponse(content="Sorry, I encountered an error.")

    async def embed_text(
        self,
        text: str,
        model: str = "text-embedding-ada-002",
    ) -> list[float]:
        """Generate embeddings for text."""
        try:
            return await self.get_embeddings(text, model)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    async def get_response(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
        db=None,
        use_rag: bool = True,
        use_tools: bool = True,
        max_context_chunks: int = 5,
    ) -> AIResponse:
        """
        Get AI response for a user message with RAG and tool integration.

        Args:
            conversation_id: Conversation ID
            user_message: User message content
            user_id: User ID
            db: Database session
            use_rag: Whether to use RAG
            use_tools: Whether to enable tools
            max_context_chunks: Maximum context chunks

        Returns:
            AIResponse: Structured AI response
        """
        if not self.enabled:
            return AIResponse(
                content="AI service is currently unavailable.",
                message_type="text",
                metadata={"error": "ai_service_disabled"},
            )

        try:
            # Get conversation history
            conversation_history = []
            if db:
                from backend.app.services.conversation_service import (
                    ConversationService,
                )

                conv_service = ConversationService(db)
                conversation_history = conv_service.get_conversation_history(
                    conversation_id,
                )

            # Prepare messages for AI
            messages = conversation_history + [
                {"role": "user", "content": user_message},
            ]

            # Use RAG-enhanced completion if enabled
            if use_rag:
                response = await self.chat_completion_with_rag(
                    messages=messages,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    use_knowledge_base=True,
                    use_tools=use_tools,
                    max_context_chunks=max_context_chunks,
                )
            else:
                # Use regular completion
                tools = None
                if use_tools:
                    tools = await self._prepare_tools_for_completion(user_message)

                response = await self.chat_completion(
                    messages=messages,
                    tools=tools,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )

            # Extract response content
            content = ""
            tool_calls = []

            if "choices" in response and response["choices"]:
                choice = response["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")

                # Check for tool calls
                if "tool_calls" in message:
                    tool_calls = message["tool_calls"]

                    # Execute tool calls
                    for tool_call in tool_calls:
                        tool_result = await self.execute_tool_call(tool_call, user_id)

                        # Add tool result to content
                        if tool_result.get("success"):
                            content += f"\n\nTool-Ausführung ({tool_result.get('tool_type', 'unknown')}):\n"
                            content += str(tool_result.get("result", ""))
                        else:
                            content += f"\n\nTool-Fehler: {tool_result.get('error', 'Unknown error')}"

            # Prepare metadata
            metadata = {
                "model_used": response.get("model", "unknown"),
                "tokens_used": response.get("usage", {}).get("total_tokens", 0),
                "has_tool_calls": len(tool_calls) > 0,
                "tool_calls_count": len(tool_calls),
            }

            return AIResponse(
                content=content,
                message_type="text",
                metadata=metadata,
                tool_calls=tool_calls if tool_calls else None,
            )

        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            return AIResponse(
                content=f"Entschuldigung, es gab einen Fehler bei der Verarbeitung Ihrer Anfrage: {str(e)}",
                message_type="text",
                metadata={"error": str(e)},
            )


# Global AI service instance
ai_service = AIService()
