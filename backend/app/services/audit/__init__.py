"""
audit service module.

This module provides audit functionality for the ConvoSphere platform.
"""

from backend.app.core.database import get_db

from .audit_service import AuditService


def get_audit_service():
    """Get an audit service instance with database connection."""
    db = next(get_db())
    return AuditService(db)


__all__ = ["AuditService", "get_audit_service"]
