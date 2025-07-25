"""
Models package for the AI Assistant Platform.

This package contains all database models for the platform.
"""

from .assistant import Assistant, AssistantStatus
from .audit import AuditEventType, AuditLog, AuditSeverity
from .base import Base
from .conversation import Conversation, Message, MessageRole, MessageType
from .knowledge import Document, DocumentChunk, SearchQuery
from .tool import Tool, ToolCategory
from .user import User, UserRole

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Assistant",
    "AssistantStatus",
    "Conversation",
    "Message",
    "MessageRole",
    "MessageType",
    "Tool",
    "ToolCategory",
    "AuditLog",
    "AuditEventType",
    "AuditSeverity",
    "Document",
    "DocumentChunk",
    "SearchQuery",
]
