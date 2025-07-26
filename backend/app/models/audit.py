"""
Audit log model for comprehensive activity logging.

This module defines the AuditLog model for tracking all user activities,
system events, and security-related actions for compliance and monitoring.
"""

import uuid
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class AuditEventType(str, Enum):
    """Audit event type enumeration."""

    # User events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"

    # Assistant events
    ASSISTANT_CREATE = "assistant_create"
    ASSISTANT_UPDATE = "assistant_update"
    ASSISTANT_DELETE = "assistant_delete"
    ASSISTANT_ACTIVATE = "assistant_activate"
    ASSISTANT_DEACTIVATE = "assistant_deactivate"

    # Conversation events
    CONVERSATION_CREATE = "conversation_create"
    CONVERSATION_UPDATE = "conversation_update"
    CONVERSATION_DELETE = "conversation_delete"
    MESSAGE_SEND = "message_send"
    MESSAGE_RECEIVE = "message_receive"

    # Tool events
    TOOL_CREATE = "tool_create"
    TOOL_UPDATE = "tool_update"
    TOOL_DELETE = "tool_delete"
    TOOL_EXECUTE = "tool_execute"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"
    SYSTEM_MAINTENANCE = "system_maintenance"

    # Security events
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"


class AuditSeverity(str, Enum):
    """Audit severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Audit log model for tracking all activities."""

    __tablename__ = "audit_logs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event information
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    severity = Column(
        SQLEnum(AuditSeverity),
        default=AuditSeverity.INFO,
        nullable=False,
    )

    # User and session information
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="audit_logs")

    session_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)

    # Resource information
    resource_type = Column(
        String(100),
        nullable=True,
    )  # e.g., "assistant", "conversation"
    resource_id = Column(String(255), nullable=True)

    # Event details
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Additional event details

    # Timestamp (inherited from Base)

    def __repr__(self) -> str:
        """String representation of the audit log."""
        return f"<AuditLog(id={self.id}, event_type='{self.event_type}', severity='{self.severity}')>"

    @property
    def is_security_event(self) -> bool:
        """Check if this is a security-related event."""
        security_events = [
            AuditEventType.USER_LOGIN,
            AuditEventType.USER_LOGOUT,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.API_KEY_CREATE,
            AuditEventType.API_KEY_REVOKE,
        ]
        return self.event_type in security_events

    @property
    def is_high_severity(self) -> bool:
        """Check if this is a high severity event."""
        return self.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]

    def to_dict(self) -> dict[str, Any]:
        """Convert audit log to dictionary."""
        return {
            "id": str(self.id),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "user_id": str(self.user_id) if self.user_id else None,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
