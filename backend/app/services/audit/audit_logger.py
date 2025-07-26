"""
Audit logging functionality.

This module handles the logging of audit events.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


class AuditLogger:
    """Handles audit event logging."""

    def __init__(self, db: Session):
        self.db = db

    def log_event(self, event_type: str, user_id: int, details: dict[str, Any]) -> bool:
        """Log an audit event."""
        try:
            audit_log = AuditLog(
                event_type=event_type,
                user_id=user_id,
                details=details,
                timestamp=datetime.utcnow(),
            )
            self.db.add(audit_log)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_events(self, user_id: int = None, event_type: str = None) -> list[AuditLog]:
        """Get audit events with optional filtering."""
        query = self.db.query(AuditLog)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        return query.order_by(AuditLog.timestamp.desc()).all()

    def generate_report(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Generate an audit report for the specified period."""
        events = (
            self.db.query(AuditLog)
            .filter(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            .all()
        )

        return {
            "period": {"start": start_date, "end": end_date},
            "total_events": len(events),
            "event_types": self._count_event_types(events),
            "users": self._count_users(events),
        }

    def _count_event_types(self, events: list[AuditLog]) -> dict[str, int]:
        """Count events by type."""
        counts = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    def _count_users(self, events: list[AuditLog]) -> dict[int, int]:
        """Count events by user."""
        counts = {}
        for event in events:
            counts[event.user_id] = counts.get(event.user_id, 0) + 1
        return counts
