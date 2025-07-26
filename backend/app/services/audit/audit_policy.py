"""
Audit policy management.

This module handles audit policy configuration and enforcement.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit_extended import AuditPolicy


class AuditPolicyManager:
    """Manages audit policies."""

    def __init__(self, db: Session):
        self.db = db

    def create_policy(self, name: str, description: str, rules: dict[str, Any]) -> bool:
        """Create a new audit policy."""
        try:
            policy = AuditPolicy(
                name=name, description=description, rules=rules, is_active=True
            )
            self.db.add(policy)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_policies(self, active_only: bool = True) -> list[AuditPolicy]:
        """Get audit policies."""
        query = self.db.query(AuditPolicy)
        if active_only:
            query = query.filter(AuditPolicy.is_active)
        return query.all()

    def update_policy(self, policy_id: int, updates: dict[str, Any]) -> bool:
        """Update an audit policy."""
        try:
            policy = (
                self.db.query(AuditPolicy).filter(AuditPolicy.id == policy_id).first()
            )
            if policy:
                for key, value in updates.items():
                    setattr(policy, key, value)
                self.db.commit()
                return True
            return False
        except Exception:
            self.db.rollback()
            return False

    def delete_policy(self, policy_id: int) -> bool:
        """Delete an audit policy."""
        try:
            policy = (
                self.db.query(AuditPolicy).filter(AuditPolicy.id == policy_id).first()
            )
            if policy:
                self.db.delete(policy)
                self.db.commit()
                return True
            return False
        except Exception:
            self.db.rollback()
            return False
