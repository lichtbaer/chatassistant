"""
Conversation and Message models for chat functionality.

This module defines the Conversation and Message models for managing
chat conversations between users and AI assistants.
"""

import uuid
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class MessageRole(str, Enum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageType(str, Enum):
    """Message type enumeration."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"


class Conversation(Base):
    """Conversation model for chat sessions."""

    __tablename__ = "conversations"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic information
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="conversations")

    assistant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assistants.id"),
        nullable=False,
    )
    assistant = relationship("Assistant", back_populates="conversations")

    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)

    # Statistics
    message_count = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)

    # Metadata
    conversation_metadata = Column(JSON, default=dict)  # Additional metadata

    # Relationships
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of the conversation."""
        return f"<Conversation(id={self.id}, title='{self.title}')>"

    @property
    def last_message(self) -> Optional["Message"]:
        """Get the last message in the conversation."""
        if self.messages:
            return max(self.messages, key=lambda m: m.created_at)
        return None

    def update_title_from_messages(self):
        """Update conversation title from first user message."""
        if not self.messages:
            return

        first_user_message = next(
            (msg for msg in self.messages if msg.role == MessageRole.USER),
            None,
        )

        if first_user_message:
            # Generate title from first message (first 100 characters)
            title = first_user_message.content[:100]
            if len(first_user_message.content) > 100:
                title += "..."
            self.title = title

    def to_dict(self) -> dict[str, Any]:
        """Convert conversation to dictionary."""
        result = {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "user_id": str(self.user_id),
            "assistant_id": str(self.assistant_id),
            "is_active": self.is_active,
            "is_archived": self.is_archived,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "conversation_metadata": self.conversation_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # Add assistant name if relationship is loaded
        if hasattr(self, "assistant") and self.assistant:
            result["assistant_name"] = self.assistant.name
        else:
            result["assistant_name"] = "Unknown Assistant"

        return result


class Message(Base):
    """Message model for individual chat messages."""

    __tablename__ = "messages"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Content
    content = Column(Text, nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)
    message_type = Column(
        SQLEnum(MessageType),
        default=MessageType.TEXT,
        nullable=False,
    )

    # Relationships
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    conversation = relationship("Conversation", back_populates="messages")

    # Tool information (for tool messages)
    tool_name = Column(String(200), nullable=True)
    tool_input = Column(JSON, nullable=True)
    tool_output = Column(JSON, nullable=True)

    # Token information
    tokens_used = Column(Integer, default=0, nullable=False)
    model_used = Column(String(100), nullable=True)

    # Metadata
    message_metadata = Column(JSON, default=dict)  # Additional metadata

    def __repr__(self) -> str:
        """String representation of the message."""
        return f"<Message(id={self.id}, role='{self.role}', content='{self.content[:50]}...')>"

    @property
    def is_from_user(self) -> bool:
        """Check if message is from user."""
        return self.role == MessageRole.USER

    @property
    def is_from_assistant(self) -> bool:
        """Check if message is from assistant."""
        return self.role == MessageRole.ASSISTANT

    @property
    def is_tool_message(self) -> bool:
        """Check if message is a tool message."""
        return self.role == MessageRole.TOOL

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": str(self.id),
            "content": self.content,
            "role": self.role.value,
            "message_type": self.message_type.value,
            "conversation_id": str(self.conversation_id),
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
            "metadata": self.message_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
