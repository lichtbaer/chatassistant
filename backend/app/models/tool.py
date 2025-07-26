"""
Tool model for managing available tools and their configurations.

This module defines the Tool model for managing the extensive tool ecosystem
that can be used by AI assistants.
"""

import uuid
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class ToolCategory(str, Enum):
    """Tool category enumeration."""

    SEARCH = "search"
    FILE = "file"
    API = "api"
    DATABASE = "database"
    CUSTOM = "custom"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    AUTOMATION = "automation"


class Tool(Base):
    """Tool model for managing available tools."""

    __tablename__ = "tools"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic information
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), default="1.0.0")

    # Tool configuration
    category = Column(SQLEnum(ToolCategory), nullable=False)
    function_name = Column(String(200), nullable=False, unique=True)
    parameters_schema = Column(JSON, nullable=True)  # JSON Schema for parameters

    # Implementation details
    implementation_path = Column(String(500), nullable=True)  # Path to implementation
    is_builtin = Column(Boolean, default=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Security and permissions
    requires_auth = Column(Boolean, default=False, nullable=False)
    required_permissions = Column(JSON, default=list)  # List of required permissions
    rate_limit = Column(String(50), nullable=True)  # Rate limiting configuration

    # Metadata
    tags = Column(JSON, default=list)  # List of tags
    tool_metadata = Column(JSON, default=dict)  # Additional metadata

    # Relationships
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    creator = relationship("User", back_populates="created_tools")

    def __repr__(self) -> str:
        """String representation of the tool."""
        return f"<Tool(id={self.id}, name='{self.name}', category='{self.category}')>"

    @property
    def is_available(self) -> bool:
        """Check if tool is available for use."""
        return self.is_enabled and self.is_builtin

    def validate_parameters(self, parameters: dict[str, Any]) -> bool:
        """Validate tool parameters against schema."""
        if not self.parameters_schema:
            return True

        try:
            from jsonschema import ValidationError, validate

            # Validate parameters against JSON schema
            validate(instance=parameters, schema=self.parameters_schema)
            return True

        except ImportError:
            logger.exception(
                "jsonschema not installed. Install with: pip install jsonschema",
            )
            return False
        except ValidationError as e:
            logger.exception(f"Parameter validation failed: {e}")
            return False
        except Exception as e:
            logger.exception(f"Schema validation error: {e}")
            return False

    def get_parameter_description(self, param_name: str) -> str | None:
        """Get description for a specific parameter."""
        if not self.parameters_schema:
            return None

        properties = self.parameters_schema.get("properties", {})
        param_schema = properties.get(param_name, {})
        return param_schema.get("description")

    def to_dict(self) -> dict[str, Any]:
        """Convert tool to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category.value,
            "function_name": self.function_name,
            "parameters_schema": self.parameters_schema,
            "implementation_path": self.implementation_path,
            "is_builtin": self.is_builtin,
            "is_enabled": self.is_enabled,
            "requires_auth": self.requires_auth,
            "required_permissions": self.required_permissions,
            "rate_limit": self.rate_limit,
            "tags": self.tags,
            "metadata": self.tool_metadata,
            "creator_id": str(self.creator_id) if self.creator_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
