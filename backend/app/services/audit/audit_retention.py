"""
Audit retention policy management.

This module handles retention policies for audit logs.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit_extended import AuditRetentionRule as AuditRetentionPolicy
from backend.app.models.audit_extended import ExtendedAuditLog as AuditLog


class RetentionManager:
    """Manages retention policies for audit logs."""

    def __init__(self, db: Session):
        self.db = db

    def create_retention_policy(
        self, name: str, retention_days: int, event_types: list[str] = None
    ) -> bool:
        """Create a new retention policy."""
        try:
            policy = AuditRetentionPolicy(
                name=name,
                retention_days=retention_days,
                event_types=event_types or [],
                is_active=True,
            )
            self.db.add(policy)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def apply_policies(self) -> int:
        """Apply all active retention policies."""
        policies = (
            self.db.query(AuditRetentionPolicy)
            .filter(AuditRetentionPolicy.is_active)
            .all()
        )
        total_deleted = 0

        for policy in policies:
            deleted_count = self._apply_policy(policy)
            total_deleted += deleted_count

        return total_deleted

    def _apply_policy(self, policy: AuditRetentionPolicy) -> int:
        """Apply a specific retention policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)

        query = self.db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date)

        if policy.event_types:
            query = query.filter(AuditLog.event_type.in_(policy.event_types))

        # Get count before deletion
        count = query.count()

        # Delete old logs
        query.delete()
        self.db.commit()

        return count

    def get_retention_summary(self) -> dict[str, Any]:
        """Get a summary of retention policies and their impact."""
        policies = self.db.query(AuditRetentionPolicy).all()
        summary = {
            "total_policies": len(policies),
            "active_policies": len([p for p in policies if p.is_active]),
            "policy_details": [],
        }

        for policy in policies:
            cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
            query = self.db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date)

            if policy.event_types:
                query = query.filter(AuditLog.event_type.in_(policy.event_types))

            summary["policy_details"].append(
                {
                    "name": policy.name,
                    "retention_days": policy.retention_days,
                    "event_types": policy.event_types,
                    "is_active": policy.is_active,
                    "logs_to_delete": query.count(),
                }
            )

        return summary
