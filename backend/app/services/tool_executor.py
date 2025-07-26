"""
Tool Executor for MCP (Model Context Protocol) tool execution.

This module provides a comprehensive tool execution framework for
MCP tools with validation, error handling, and result processing.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

from backend.app.services.tool_service import tool_service

if TYPE_CHECKING:
    from collections.abc import Callable


class ToolExecutionStatus(Enum):
    """Tool execution status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolType(Enum):
    """Tool type enumeration."""

    MCP = "mcp"
    FUNCTION = "function"
    API = "api"
    CUSTOM = "custom"


@dataclass
class ToolParameter:
    """Tool parameter definition."""

    name: str
    type: str
    description: str
    required: bool = False
    default: Any | None = None
    enum: list[str] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None


@dataclass
class ToolDefinition:
    """Tool definition."""

    id: str
    name: str
    description: str
    type: ToolType
    parameters: list[ToolParameter] = field(default_factory=list)
    returns: str | None = None
    timeout: int = 30
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecution:
    """Tool execution instance."""

    id: str
    tool_id: str
    user_id: str
    conversation_id: str | None
    parameters: dict[str, Any]
    status: ToolExecutionStatus
    result: Any | None = None
    error: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """MCP tool execution framework."""

    def __init__(self):
        """Initialize the tool executor."""
        self.executions: dict[str, ToolExecution] = {}
        self.tools: dict[str, ToolDefinition] = {}
        self.execution_handlers: dict[str, Callable] = {}
        self.max_concurrent_executions = 10
        self.default_timeout = 30

        # Load available tools
        self._load_tools()

    def _load_tools(self):
        """Load available tools from tool service."""
        try:
            # Get tools from tool service
            available_tools = tool_service.get_available_tools()

            for tool_data in available_tools:
                tool_def = self._create_tool_definition(tool_data)
                self.tools[tool_def.id] = tool_def

                # Register execution handler
                if tool_def.type == ToolType.MCP:
                    self.execution_handlers[tool_def.id] = self._execute_mcp_tool
                elif tool_def.type == ToolType.FUNCTION:
                    self.execution_handlers[tool_def.id] = self._execute_function_tool
                elif tool_def.type == ToolType.API:
                    self.execution_handlers[tool_def.id] = self._execute_api_tool
                else:
                    self.execution_handlers[tool_def.id] = self._execute_custom_tool

            logger.info(f"Loaded {len(self.tools)} tools")

        except Exception as e:
            logger.error(f"Error loading tools: {e}")

    def _create_tool_definition(self, tool_data: dict[str, Any]) -> ToolDefinition:
        """Create tool definition from tool data."""
        parameters = []
        for param_data in tool_data.get("parameters", []):
            param = ToolParameter(
                name=param_data["name"],
                type=param_data["type"],
                description=param_data.get("description", ""),
                required=param_data.get("required", False),
                default=param_data.get("default"),
                enum=param_data.get("enum"),
                min_value=param_data.get("min_value"),
                max_value=param_data.get("max_value"),
            )
            parameters.append(param)

        return ToolDefinition(
            id=tool_data["id"],
            name=tool_data["name"],
            description=tool_data.get("description", ""),
            type=ToolType(tool_data.get("type", "mcp")),
            parameters=parameters,
            returns=tool_data.get("returns"),
            timeout=tool_data.get("timeout", self.default_timeout),
            enabled=tool_data.get("enabled", True),
            metadata=tool_data.get("metadata", {}),
        )

    async def execute_tool(
        self,
        tool_id: str,
        parameters: dict[str, Any],
        user_id: str,
        conversation_id: str | None = None,
        timeout: int | None = None,
    ) -> ToolExecution:
        """
        Execute a tool with given parameters.

        Args:
            tool_id: ID of the tool to execute
            parameters: Tool parameters
            user_id: User ID
            conversation_id: Conversation ID (optional)
            timeout: Execution timeout (optional)

        Returns:
            Tool execution instance
        """
        # Validate tool exists
        if tool_id not in self.tools:
            raise ValueError(f"Tool {tool_id} not found")

        tool_def = self.tools[tool_id]

        if not tool_def.enabled:
            raise ValueError(f"Tool {tool_id} is disabled")

        # Validate parameters
        validation_result = self._validate_parameters(tool_def, parameters)
        if not validation_result["valid"]:
            raise ValueError(
                f"Parameter validation failed: {validation_result['errors']}",
            )

        # Create execution instance
        execution_id = f"exec_{len(self.executions)}_{datetime.now(UTC).timestamp()}"
        execution = ToolExecution(
            id=execution_id,
            tool_id=tool_id,
            user_id=user_id,
            conversation_id=conversation_id,
            parameters=parameters,
            status=ToolExecutionStatus.PENDING,
            start_time=datetime.now(UTC),
        )

        self.executions[execution_id] = execution

        # Execute tool
        try:
            execution.status = ToolExecutionStatus.RUNNING

            # Get execution handler
            handler = self.execution_handlers.get(tool_id)
            if not handler:
                raise ValueError(f"No execution handler for tool {tool_id}")

            # Set timeout
            exec_timeout = timeout or tool_def.timeout

            # Execute with timeout
            result = await asyncio.wait_for(
                handler(tool_def, parameters, user_id),
                timeout=exec_timeout,
            )

            execution.result = result
            execution.status = ToolExecutionStatus.COMPLETED

        except TimeoutError:
            execution.status = ToolExecutionStatus.TIMEOUT
            execution.error = f"Tool execution timed out after {exec_timeout} seconds"

        except Exception as e:
            execution.status = ToolExecutionStatus.FAILED
            execution.error = str(e)
            logger.error(f"Tool execution failed: {e}")

        finally:
            execution.end_time = datetime.now(UTC)
            if execution.start_time and execution.end_time:
                execution.execution_time = (
                    execution.end_time - execution.start_time
                ).total_seconds()

        return execution

    async def _execute_mcp_tool(
        self,
        tool_def: ToolDefinition,
        parameters: dict[str, Any],
        user_id: str,
    ) -> Any:
        """Execute MCP tool."""
        try:
            # Get MCP tool from tool service
            mcp_tool = tool_service.get_mcp_tool(tool_def.id)
            if not mcp_tool:
                raise ValueError(f"MCP tool {tool_def.id} not found")

            # Execute MCP tool
            return await mcp_tool.execute(parameters)

        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_def.id}: {e}")
            raise

    async def _execute_function_tool(
        self,
        tool_def: ToolDefinition,
        parameters: dict[str, Any],
        user_id: str,
    ) -> Any:
        """Execute function tool."""
        try:
            # Get function from tool service
            func = tool_service.get_function_tool(tool_def.id)
            if not func:
                raise ValueError(f"Function tool {tool_def.id} not found")

            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(**parameters)
            else:
                result = func(**parameters)

            return result

        except Exception as e:
            logger.error(f"Error executing function tool {tool_def.id}: {e}")
            raise

    async def _execute_api_tool(
        self,
        tool_def: ToolDefinition,
        parameters: dict[str, Any],
        user_id: str,
    ) -> Any:
        """Execute API tool."""
        try:
            # Get API tool from tool service
            api_tool = tool_service.get_api_tool(tool_def.id)
            if not api_tool:
                raise ValueError(f"API tool {tool_def.id} not found")

            # Execute API call
            return await api_tool.call(parameters)

        except Exception as e:
            logger.error(f"Error executing API tool {tool_def.id}: {e}")
            raise

    async def _execute_custom_tool(
        self,
        tool_def: ToolDefinition,
        parameters: dict[str, Any],
        user_id: str,
    ) -> Any:
        """Execute custom tool."""
        try:
            # Get custom tool from tool service
            custom_tool = tool_service.get_custom_tool(tool_def.id)
            if not custom_tool:
                raise ValueError(f"Custom tool {tool_def.id} not found")

            # Execute custom tool
            return await custom_tool.execute(parameters, user_id)

        except Exception as e:
            logger.error(f"Error executing custom tool {tool_def.id}: {e}")
            raise

    def _validate_parameters(
        self,
        tool_def: ToolDefinition,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate tool parameters.

        Args:
            tool_def: Tool definition
            parameters: Parameters to validate

        Returns:
            Validation result
        """
        errors = []

        for param in tool_def.parameters:
            param_name = param.name
            param_value = parameters.get(param_name)

            # Check required parameters
            if param.required and param_value is None:
                errors.append(f"Required parameter '{param_name}' is missing")
                continue

            # Use default value if not provided
            if param_value is None and param.default is not None:
                param_value = param.default

            # Skip validation if value is None and not required
            if param_value is None:
                continue

            # Type validation
            if param.type == "string":
                if not isinstance(param_value, str):
                    errors.append(f"Parameter '{param_name}' must be a string")
            elif param.type == "integer":
                if not isinstance(param_value, int):
                    errors.append(f"Parameter '{param_name}' must be an integer")
            elif param.type == "number":
                if not isinstance(param_value, int | float):
                    errors.append(f"Parameter '{param_name}' must be a number")
            elif param.type == "boolean":
                if not isinstance(param_value, bool):
                    errors.append(f"Parameter '{param_name}' must be a boolean")
            elif param.type == "array":
                if not isinstance(param_value, list):
                    errors.append(f"Parameter '{param_name}' must be an array")

            # Enum validation
            if param.enum and param_value not in param.enum:
                errors.append(f"Parameter '{param_name}' must be one of: {param.enum}")

            # Range validation
            if param.min_value is not None and param_value < param.min_value:
                errors.append(f"Parameter '{param_name}' must be >= {param.min_value}")

            if param.max_value is not None and param_value > param.max_value:
                errors.append(f"Parameter '{param_name}' must be <= {param.max_value}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def get_tool_definition(self, tool_id: str) -> ToolDefinition | None:
        """Get tool definition by ID."""
        return self.tools.get(tool_id)

    def get_available_tools(self) -> list[ToolDefinition]:
        """Get list of available tools."""
        return list(self.tools.values())

    def get_tool_schema(self, tool_id: str) -> dict[str, Any] | None:
        """Get tool schema for AI completion."""
        tool_def = self.get_tool_definition(tool_id)
        if not tool_def:
            return None

        schema = {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }

        for param in tool_def.parameters:
            schema["function"]["parameters"]["properties"][param.name] = {
                "type": param.type,
                "description": param.description,
            }

            if param.enum:
                schema["function"]["parameters"]["properties"][param.name][
                    "enum"
                ] = param.enum

            if param.min_value is not None:
                schema["function"]["parameters"]["properties"][param.name][
                    "minimum"
                ] = param.min_value

            if param.max_value is not None:
                schema["function"]["parameters"]["properties"][param.name][
                    "maximum"
                ] = param.max_value

            if param.required:
                schema["function"]["parameters"]["required"].append(param.name)

        return schema

    def get_execution(self, execution_id: str) -> ToolExecution | None:
        """Get execution by ID."""
        return self.executions.get(execution_id)

    def get_user_executions(
        self,
        user_id: str,
        limit: int = 100,
    ) -> list[ToolExecution]:
        """Get executions for a user."""
        user_executions = [
            exec for exec in self.executions.values() if exec.user_id == user_id
        ]

        # Sort by start time (newest first)
        user_executions.sort(key=lambda x: x.start_time, reverse=True)

        return user_executions[:limit]

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution."""
        execution = self.executions.get(execution_id)
        if not execution:
            return False

        if execution.status == ToolExecutionStatus.RUNNING:
            execution.status = ToolExecutionStatus.CANCELLED
            execution.end_time = datetime.now(UTC)
            return True

        return False

    def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        total_executions = len(self.executions)
        completed = len(
            [
                e
                for e in self.executions.values()
                if e.status == ToolExecutionStatus.COMPLETED
            ],
        )
        failed = len(
            [
                e
                for e in self.executions.values()
                if e.status == ToolExecutionStatus.FAILED
            ],
        )
        timeout = len(
            [
                e
                for e in self.executions.values()
                if e.status == ToolExecutionStatus.TIMEOUT
            ],
        )

        avg_execution_time = 0
        if completed > 0:
            execution_times = [
                e.execution_time for e in self.executions.values() if e.execution_time
            ]
            if execution_times:
                avg_execution_time = sum(execution_times) / len(execution_times)

        return {
            "total_executions": total_executions,
            "completed": completed,
            "failed": failed,
            "timeout": timeout,
            "success_rate": (
                (completed / total_executions * 100) if total_executions > 0 else 0
            ),
            "average_execution_time": avg_execution_time,
            "available_tools": len(self.tools),
        }


# Global tool executor instance
tool_executor = ToolExecutor()
