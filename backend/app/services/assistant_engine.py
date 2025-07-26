"""
Assistant Engine for processing user messages with hybrid mode support.

This module provides the main assistant engine with hybrid chat/agent mode
capabilities, structured output, and integration with the HybridModeManager.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from backend.app.core.config import get_settings
from backend.app.schemas.hybrid_mode import (
    ConversationMode,
    HybridModeConfig,
    ModeChangeRequest,
    StructuredResponse,
)
from backend.app.services.ai_service import ai_service
from backend.app.services.conversation_service import conversation_service
from backend.app.services.hybrid_mode_manager import hybrid_mode_manager
from backend.app.services.knowledge_service import knowledge_service
from backend.app.services.tool_executor_v2 import tool_executor


@dataclass
class ProcessingRequest:
    """Request for message processing."""

    request_id: str
    user_id: str
    conversation_id: str
    message: str
    assistant_id: str | None = None
    use_knowledge_base: bool = True
    use_tools: bool = True
    max_context_chunks: int = 5
    temperature: float = 0.7
    max_tokens: int | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None
    force_mode: ConversationMode | None = None


@dataclass
class ProcessingResult:
    """Result of message processing."""

    request_id: str
    success: bool
    content: str
    tool_calls: list[dict[str, Any]]
    metadata: dict[str, Any]
    model_used: str
    tokens_used: int
    processing_time: float
    error_message: str | None = None
    structured_response: StructuredResponse | None = None


@dataclass
class AIResponse:
    """AI response with structured output."""

    content: str
    tool_calls: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    message_type: str = "text"


class AssistantEngine:
    """Main assistant engine for processing user messages with hybrid mode support."""

    def __init__(self):
        """Initialize the assistant engine."""
        self.processing_requests: dict[str, ProcessingRequest] = {}
        self.processing_results: dict[str, ProcessingResult] = {}
        self.max_concurrent_requests = 5
        self.default_model = get_settings().default_ai_model
        self.default_max_tokens = 2048

        # Processing semaphore to limit concurrent requests
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_requests)

    async def process_message(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        assistant_id: str | None = None,
        use_knowledge_base: bool = True,
        use_tools: bool = True,
        max_context_chunks: int = 5,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
        force_mode: ConversationMode | None = None,
    ) -> ProcessingResult:
        """
        Process a user message and generate a response with hybrid mode support.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message: User message
            assistant_id: Assistant ID (optional)
            use_knowledge_base: Whether to use knowledge base
            use_tools: Whether to use tools
            max_context_chunks: Maximum knowledge chunks to include
            temperature: AI model temperature
            max_tokens: Maximum tokens for response
            model: AI model to use
            metadata: Additional metadata
            force_mode: Force specific conversation mode

        Returns:
            Processing result with structured response
        """
        # Create processing request
        request_id = (
            f"req_{len(self.processing_requests)}_{datetime.now(UTC).timestamp()}"
        )

        request = ProcessingRequest(
            request_id=request_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message=message,
            assistant_id=assistant_id,
            use_knowledge_base=use_knowledge_base,
            use_tools=use_tools,
            max_context_chunks=max_context_chunks,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            metadata=metadata,
            force_mode=force_mode,
        )

        self.processing_requests[request_id] = request

        try:
            async with self.processing_semaphore:
                return await self._process_request(request)
        except Exception as e:
            logger.error(f"Error processing request {request_id}: {e}")
            return ProcessingResult(
                request_id=request_id,
                success=False,
                content=f"Entschuldigung, es gab einen Fehler bei der Verarbeitung: {str(e)}",
                tool_calls=[],
                metadata={},
                model_used="",
                tokens_used=0,
                processing_time=0.0,
                error_message=str(e),
            )
        finally:
            # Clean up request
            if request_id in self.processing_requests:
                del self.processing_requests[request_id]

    async def _process_request(self, request: ProcessingRequest) -> ProcessingResult:
        """Process a single request with hybrid mode support."""
        start_time = datetime.now(UTC)

        try:
            # Initialize hybrid mode if not already done
            await self._ensure_hybrid_mode_initialized(request)

            # Get conversation context
            context = await self._get_conversation_context(request)

            # Decide mode using hybrid mode manager
            mode_decision = await hybrid_mode_manager.decide_mode(
                conversation_id=request.conversation_id,
                user_message=request.message,
                context=context,
                force_mode=request.force_mode,
            )

            # Update conversation mode if needed
            if mode_decision.recommended_mode != mode_decision.current_mode:
                await self._update_conversation_mode(
                    request, mode_decision.recommended_mode
                )

            # Prepare knowledge base context if enabled
            knowledge_context = ""
            if (
                request.use_knowledge_base
                and mode_decision.recommended_mode == ConversationMode.AGENT
            ):
                knowledge_context = await self._prepare_knowledge_context(request)

            # Prepare tools based on mode
            tools = []
            if (
                request.use_tools
                and mode_decision.recommended_mode == ConversationMode.AGENT
            ):
                tools = await self._prepare_tools(request.message)

            # Generate AI response with structured output
            ai_response = await self._generate_structured_response(
                request, context, knowledge_context, tools, mode_decision
            )

            # Execute tool calls if in agent mode
            tool_results = []
            if (
                mode_decision.recommended_mode == ConversationMode.AGENT
                and ai_response.tool_calls
            ):
                tool_results = await self._execute_tools(ai_response.tool_calls)

            # Create structured response
            structured_response = StructuredResponse(
                content=ai_response.content,
                mode_decision=mode_decision,
                tool_calls=tool_results,
                memory_updates=[],  # TODO: Implement memory updates
                reasoning_process=mode_decision.reasoning_steps,
                metadata=ai_response.metadata or {},
                model_used=request.model or self.default_model,
                tokens_used=(
                    ai_response.metadata.get("total_tokens", 0)
                    if ai_response.metadata
                    else 0
                ),
                processing_time=(datetime.now(UTC) - start_time).total_seconds(),
            )

            # Save response to conversation
            await self._save_response_to_conversation(request, structured_response)

            processing_time = (datetime.now(UTC) - start_time).total_seconds()

            return ProcessingResult(
                request_id=request.request_id,
                success=True,
                content=structured_response.content,
                tool_calls=tool_results,
                metadata=structured_response.metadata,
                model_used=structured_response.model_used,
                tokens_used=structured_response.tokens_used,
                processing_time=processing_time,
                structured_response=structured_response,
            )

        except Exception as e:
            logger.error(f"Error in _process_request: {e}")
            raise

    async def _ensure_hybrid_mode_initialized(self, request: ProcessingRequest):
        """Ensure hybrid mode is initialized for the conversation."""
        state = hybrid_mode_manager.get_state(request.conversation_id)
        if not state:
            # Initialize with default config
            config = HybridModeConfig(
                auto_mode_enabled=True,
                complexity_threshold=0.7,
                confidence_threshold=0.8,
            )
            hybrid_mode_manager.initialize_conversation(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                initial_mode=ConversationMode.AUTO,
                config=config,
            )

    async def _get_conversation_context(
        self, request: ProcessingRequest
    ) -> dict[str, Any]:
        """Get conversation context for mode decision."""
        try:
            # Get recent messages
            messages = await conversation_service.get_conversation_messages(
                conversation_id=request.conversation_id,
                limit=20,  # Last 20 messages for context
            )

            # Get conversation metadata
            conversation = await conversation_service.get_conversation(
                request.conversation_id
            )

            return {
                "messages": [
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                        "timestamp": msg.created_at.isoformat(),
                    }
                    for msg in messages
                ],
                "conversation_metadata": conversation.conversation_metadata or {},
                "message_count": len(messages),
                "assistant_id": request.assistant_id,
            }

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return {"messages": [], "conversation_metadata": {}, "message_count": 0}

    async def _update_conversation_mode(
        self, request: ProcessingRequest, new_mode: ConversationMode
    ):
        """Update conversation mode."""
        try:
            mode_change_request = ModeChangeRequest(
                conversation_id=uuid.UUID(request.conversation_id),
                user_id=uuid.UUID(request.user_id),
                target_mode=new_mode,
                reason="Automatic mode decision",
            )

            await hybrid_mode_manager.change_mode(mode_change_request)
            logger.info(
                f"Updated conversation {request.conversation_id} to mode {new_mode}"
            )

        except Exception as e:
            logger.error(f"Error updating conversation mode: {e}")

    async def _prepare_knowledge_context(self, request: ProcessingRequest) -> str:
        """Prepare knowledge base context for agent mode."""
        try:
            # Search knowledge base for relevant content
            search_results = await knowledge_service.search_documents(
                query=request.message,
                user_id=request.user_id,
                limit=request.max_context_chunks,
            )

            if not search_results:
                return ""

            # Format knowledge context
            context_parts = []
            for result in search_results:
                context_parts.append(f"Document: {result.get('title', 'Unknown')}")
                context_parts.append(f"Content: {result.get('content', '')}")
                context_parts.append("---")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error preparing knowledge context: {e}")
            return ""

    async def _prepare_tools(self, user_message: str) -> list[dict[str, Any]]:
        """Prepare tools for AI completion."""
        try:
            available_tools = tool_executor.get_available_tools()
            tools = []

            for tool_def in available_tools:
                if tool_def.get("enabled", True):
                    schema = tool_executor.get_tool_schema(tool_def.get("name", ""))
                    if schema:
                        tools.append(schema)

            return tools

        except Exception as e:
            logger.error(f"Error preparing tools: {e}")
            return []

    async def _generate_structured_response(
        self,
        request: ProcessingRequest,
        context: dict[str, Any],
        knowledge_context: str,
        tools: list[dict[str, Any]],
        mode_decision,
    ) -> AIResponse:
        """Generate AI response with structured output."""
        try:
            # Prepare messages for AI
            messages = self._prepare_messages_for_ai(
                request, context, knowledge_context, mode_decision
            )

            # Prepare completion parameters
            completion_params = {
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens or self.default_max_tokens,
                "model": request.model or self.default_model,
            }

            # Add tools if available and in agent mode
            if tools and mode_decision.recommended_mode == ConversationMode.AGENT:
                completion_params["tools"] = tools
                completion_params["tool_choice"] = "auto"

            # Generate completion
            response = await ai_service.chat_completion(**completion_params)

            # Parse response
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            tool_calls = (
                response.get("choices", [{}])[0].get("message", {}).get("tool_calls")
            )

            return AIResponse(
                content=content,
                tool_calls=tool_calls,
                metadata=response.get("usage", {}),
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return AIResponse(
                content=f"Entschuldigung, es gab einen Fehler bei der Verarbeitung: {str(e)}",
                message_type="error",
            )

    def _prepare_messages_for_ai(
        self,
        request: ProcessingRequest,
        context: dict[str, Any],
        knowledge_context: str,
        mode_decision,
    ) -> list[dict[str, str]]:
        """Prepare messages for AI completion."""
        messages = []

        # Add system message with mode information
        system_message = self._create_system_message(mode_decision, knowledge_context)
        messages.append({"role": "system", "content": system_message})

        # Add conversation history
        for msg in context.get("messages", [])[-10:]:  # Last 10 messages
            messages.append(
                {
                    "role": msg["role"],
                    "content": msg["content"],
                }
            )

        # Add current user message
        messages.append({"role": "user", "content": request.message})

        return messages

    def _create_system_message(self, mode_decision, knowledge_context: str) -> str:
        """Create system message based on mode decision."""
        base_message = f"""You are an AI assistant operating in {mode_decision.recommended_mode.value} mode.

Current mode: {mode_decision.recommended_mode.value}
Mode reason: {mode_decision.reason.value}
Confidence: {mode_decision.confidence:.2f}

"""

        if mode_decision.recommended_mode == ConversationMode.AGENT:
            base_message += """In AGENT mode:
- You can use tools to perform actions
- You should think step by step
- You can access external resources
- You should provide detailed reasoning

"""
        else:
            base_message += """In CHAT mode:
- Provide direct, conversational responses
- Keep responses concise and friendly
- Focus on immediate user needs
- No tool usage required

"""

        if knowledge_context:
            base_message += f"Knowledge Context:\n{knowledge_context}\n\n"

        base_message += "Please respond appropriately for the current mode."

        return base_message

    async def _execute_tools(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []

        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("function", {}).get("name", "")
                arguments = tool_call.get("function", {}).get("arguments", {})

                if tool_name:
                    result = await tool_executor.execute_tool(tool_name, arguments)
                    results.append(
                        {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "result": result,
                            "success": True,
                        }
                    )
                else:
                    results.append(
                        {
                            "tool_name": "unknown",
                            "arguments": arguments,
                            "result": "Tool name not found",
                            "success": False,
                        }
                    )

            except Exception as e:
                logger.error(f"Error executing tool {tool_call}: {e}")
                results.append(
                    {
                        "tool_name": tool_call.get("function", {}).get(
                            "name", "unknown"
                        ),
                        "arguments": tool_call.get("function", {}).get("arguments", {}),
                        "result": f"Error: {str(e)}",
                        "success": False,
                    }
                )

        return results

    async def _save_response_to_conversation(
        self, request: ProcessingRequest, structured_response: StructuredResponse
    ):
        """Save the structured response to the conversation."""
        try:
            # Save assistant message
            await conversation_service.add_message(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                content=structured_response.content,
                role="assistant",
                metadata={
                    "mode_decision": structured_response.mode_decision.dict(),
                    "tool_calls": structured_response.tool_calls,
                    "reasoning_process": [
                        step.dict() for step in structured_response.reasoning_process
                    ],
                    "model_used": structured_response.model_used,
                    "tokens_used": structured_response.tokens_used,
                },
            )

        except Exception as e:
            logger.error(f"Error saving response to conversation: {e}")

    def get_processing_status(self, request_id: str) -> dict[str, Any] | None:
        """Get processing status for a request."""
        if request_id in self.processing_requests:
            return {
                "status": "processing",
                "request": self.processing_requests[request_id],
            }
        if request_id in self.processing_results:
            return {
                "status": "completed",
                "result": self.processing_results[request_id],
            }
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get assistant engine statistics."""
        return {
            "active_requests": len(self.processing_requests),
            "completed_requests": len(self.processing_results),
            "max_concurrent_requests": self.max_concurrent_requests,
            "default_model": self.default_model,
        }


# Global assistant engine instance
assistant_engine = AssistantEngine()
