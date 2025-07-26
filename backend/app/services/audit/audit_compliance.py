"""
Audit compliance checking.

This module handles compliance checking for audit policies.
"""

from datetime import UTC
from typing import Any

from sqlalchemy.orm import Session

from .audit_policy import AuditPolicyManager


class ComplianceChecker:
    """Checks compliance with audit policies."""

    def __init__(self, db: Session):
        self.db = db
        self.policy_manager = AuditPolicyManager(db)

    def check_compliance(self, action: str, user_id: int) -> bool:
        """Check if an action complies with audit policies."""
        policies = self.policy_manager.get_policies(active_only=True)

        for policy in policies:
            if not self._check_policy_compliance(policy, action, user_id):
                return False

        return True

    def _check_policy_compliance(self, policy: Any, action: str, user_id: int) -> bool:
        """Check compliance with a specific policy."""
        rules = policy.rules

        # Check action restrictions
        if "restricted_actions" in rules:
            if action in rules["restricted_actions"]:
                return False

        # Check user restrictions
        if "restricted_users" in rules and user_id in rules["restricted_users"]:
            return False

        # Check time restrictions
        if "time_restrictions" in rules:
            if not self._check_time_compliance(rules["time_restrictions"]):
                return False

        return True

    def _check_time_compliance(self, time_rules: dict[str, Any]) -> bool:
        """Check time-based compliance rules."""
        from datetime import datetime, time

        current_time = datetime.now(UTC).time()

        if "start_time" in time_rules and "end_time" in time_rules:
            start_time = time.fromisoformat(time_rules["start_time"])
            end_time = time.fromisoformat(time_rules["end_time"])

            if start_time <= end_time:
                return start_time <= current_time <= end_time
            # Crosses midnight
            return current_time >= start_time or current_time <= end_time

        return True
