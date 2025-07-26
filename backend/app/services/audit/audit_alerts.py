"""
Audit alert management.

This module handles audit alert creation and management.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit_extended import AuditAlert


class AlertManager:
    """Manages audit alerts."""

    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, alert_type: str, message: str, severity: str) -> bool:
        """Create a new audit alert."""
        try:
            alert = AuditAlert(
                alert_type=alert_type,
                message=message,
                severity=severity,
                created_at=datetime.utcnow(),
                is_resolved=False,
            )
            self.db.add(alert)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_alerts(
        self, resolved: bool = None, severity: str = None
    ) -> list[AuditAlert]:
        """Get audit alerts with optional filtering."""
        query = self.db.query(AuditAlert)

        if resolved is not None:
            query = query.filter(AuditAlert.is_resolved == resolved)

        if severity:
            query = query.filter(AuditAlert.severity == severity)

        return query.order_by(AuditAlert.created_at.desc()).all()

    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved."""
        try:
            alert = self.db.query(AuditAlert).filter(AuditAlert.id == alert_id).first()
            if alert:
                alert.is_resolved = True
                alert.resolved_at = datetime.utcnow()
                self.db.commit()
                return True
            return False
        except Exception:
            self.db.rollback()
            return False

    def get_alert_summary(self) -> dict[str, Any]:
        """Get a summary of alerts."""
        total_alerts = self.db.query(AuditAlert).count()
        unresolved_alerts = (
            self.db.query(AuditAlert).filter(not AuditAlert.is_resolved).count()
        )

        severity_counts = {}
        for alert in self.db.query(AuditAlert).all():
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        return {
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "severity_counts": severity_counts,
        }
