"""
Assistant model for AI assistants with personality profiles.

This module defines the Assistant model with personality configurations,
tool assignments, and status management.
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


class AssistantStatus(str, Enum):
    """Assistant status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    MAINTENANCE = "maintenance"


class Assistant(Base):
    """Assistant model for AI assistants with personality profiles."""

    __tablename__ = "assistants"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic information
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), default="1.0.0")

    # Personality and behavior
    personality = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)

    # Configuration
    model = Column(String(100), default="gpt-4", nullable=False)
    temperature = Column(String(10), default="0.7")  # Store as string for flexibility
    max_tokens = Column(String(10), default="4096")

    # Status and visibility
    status = Column(
        SQLEnum(AssistantStatus),
        default=AssistantStatus.DRAFT,
        nullable=False,
    )
    is_public = Column(Boolean, default=False, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)

    # Tool configuration
    tools_config = Column(JSON, default=list)  # List of tool IDs and configurations
    tools_enabled = Column(Boolean, default=True, nullable=False)

    # Metadata
    category = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, default=list)  # List of tags
    assistant_metadata = Column(JSON, default=dict)  # Additional metadata

    # Relationships
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="assistants")

    conversations = relationship("Conversation", back_populates="assistant")

    def __repr__(self) -> str:
        """String representation of the assistant."""
        return f"<Assistant(id={self.id}, name='{self.name}', status='{self.status}')>"

    @property
    def is_active(self) -> bool:
        """Check if assistant is active."""
        return self.status == AssistantStatus.ACTIVE

    @property
    def tool_count(self) -> int:
        """Get number of configured tools."""
        return len(self.tools_config) if self.tools_config else 0

    def get_tool_config(self, tool_id: str) -> dict[str, Any] | None:
        """Get configuration for a specific tool."""
        if not self.tools_config:
            return None

        for tool_config in self.tools_config:
            if tool_config.get("id") == tool_id:
                return tool_config
        return None

    def add_tool(self, tool_id: str, config: dict[str, Any] | None = None):
        """Add a tool to the assistant."""
        if not self.tools_config:
            self.tools_config = []

        # Check if tool already exists
        for tool_config in self.tools_config:
            if tool_config.get("id") == tool_id:
                # Update existing tool config
                if config:
                    tool_config.update(config)
                return

        # Add new tool
        tool_entry = {"id": tool_id}
        if config:
            tool_entry.update(config)
        self.tools_config.append(tool_entry)

    def remove_tool(self, tool_id: str) -> bool:
        """Remove a tool from the assistant."""
        if not self.tools_config:
            return False

        for i, tool_config in enumerate(self.tools_config):
            if tool_config.get("id") == tool_id:
                del self.tools_config[i]
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert assistant to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "personality": self.personality,
            "system_prompt": self.system_prompt,
            "instructions": self.instructions,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "status": self.status.value,
            "is_public": self.is_public,
            "is_template": self.is_template,
            "tools_config": self.tools_config,
            "tools_enabled": self.tools_enabled,
            "category": self.category,
            "tags": self.tags,
            "metadata": self.assistant_metadata,
            "creator_id": str(self.creator_id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
