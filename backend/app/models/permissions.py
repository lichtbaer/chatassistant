"""
Granular permissions model for advanced RBAC.

This module defines a more sophisticated permission system with
resource-specific permissions, conditions, and dynamic permission evaluation.
"""

import uuid
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class PermissionAction(str, Enum):
    """Granular permission actions."""

    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

    # Special operations
    EXECUTE = "execute"
    APPROVE = "approve"
    PUBLISH = "publish"
    ARCHIVE = "archive"
    RESTORE = "restore"
    EXPORT = "export"
    IMPORT = "import"

    # Administrative operations
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_PERMISSIONS = "manage_permissions"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SYSTEM = "manage_system"


class PermissionResource(str, Enum):
    """Permission resources."""

    ASSISTANT = "assistant"
    CONVERSATION = "conversation"
    TOOL = "tool"
    KNOWLEDGE = "knowledge"
    USER = "user"
    GROUP = "group"
    ORGANIZATION = "organization"
    AUDIT_LOG = "audit_log"
    SYSTEM = "system"
    DOCUMENT = "document"
    SEARCH = "search"
    ANALYTICS = "analytics"


class PermissionCondition(str, Enum):
    """Permission conditions."""

    OWN_RESOURCE = "own_resource"
    SAME_ORGANIZATION = "same_organization"
    SAME_GROUP = "same_group"
    PUBLIC_RESOURCE = "public_resource"
    ACTIVE_STATUS = "active_status"
    VERIFIED_USER = "verified_user"
    TIME_RESTRICTION = "time_restriction"
    IP_RESTRICTION = "ip_restriction"


class Permission(Base):
    """Granular permission model."""

    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Permission definition
    resource = Column(SQLEnum(PermissionResource), nullable=False)
    action = Column(SQLEnum(PermissionAction), nullable=False)

    # Conditions and constraints
    conditions = Column(JSON, nullable=True)  # List of PermissionCondition
    constraints = Column(JSON, nullable=True)  # Custom constraints (time, IP, etc.)

    # Metadata
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}', resource='{self.resource}', action='{self.action}')>"

    @property
    def full_name(self) -> str:
        """Get full permission name."""
        return f"{self.resource}:{self.action}"

    def evaluate_conditions(
        self,
        user: "User",
        resource: Any = None,
        context: dict[str, Any] = None,
    ) -> bool:
        """Evaluate permission conditions."""
        if not self.conditions:
            return True

        context = context or {}

        for condition in self.conditions:
            if not self._evaluate_condition(condition, user, resource, context):
                return False

        return True

    def _evaluate_condition(
        self,
        condition: str,
        user: "User",
        resource: Any,
        context: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition."""
        if condition == PermissionCondition.OWN_RESOURCE:
            return (
                resource
                and hasattr(resource, "creator_id")
                and resource.creator_id == user.id
            )

        if condition == PermissionCondition.SAME_ORGANIZATION:
            return (
                resource
                and hasattr(resource, "organization_id")
                and resource.organization_id == user.organization_id
            )

        if condition == PermissionCondition.SAME_GROUP:
            if not resource or not hasattr(resource, "allowed_groups"):
                return False
            user_group_ids = [str(group.id) for group in user.groups]
            return any(
                group_id in user_group_ids for group_id in resource.allowed_groups
            )

        if condition == PermissionCondition.PUBLIC_RESOURCE:
            return resource and hasattr(resource, "is_public") and resource.is_public

        if condition == PermissionCondition.ACTIVE_STATUS:
            return user.is_active

        if condition == PermissionCondition.VERIFIED_USER:
            return user.is_verified

        if condition == PermissionCondition.TIME_RESTRICTION:
            return self._evaluate_time_constraint(context.get("current_time"))

        if condition == PermissionCondition.IP_RESTRICTION:
            return self._evaluate_ip_constraint(context.get("ip_address"))

        return True

    def _evaluate_time_constraint(self, current_time: str | None) -> bool:
        """Evaluate time-based constraints."""
        if not self.constraints or "time_restriction" not in self.constraints:
            return True

        # Implementation for time-based restrictions
        # e.g., only allow access during business hours
        return True

    def _evaluate_ip_constraint(self, ip_address: str | None) -> bool:
        """Evaluate IP-based constraints."""
        if not self.constraints or "ip_restriction" not in self.constraints:
            return True

        # Implementation for IP-based restrictions
        # e.g., only allow access from corporate network
        return True


# Association table for role permissions
role_permission_association = Table(
    "role_permission_association",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id"),
        primary_key=True,
    ),
)


class Role(Base):
    """Enhanced role model with granular permissions."""

    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Role hierarchy
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    parent_role = relationship("Role", remote_side=[id])
    child_roles = relationship("Role")

    # Role settings
    is_system = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    permissions = relationship("Permission", secondary=role_permission_association)
    users = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"

    def has_permission(
        self,
        permission_name: str,
        user: "User" = None,
        resource: Any = None,
        context: dict[str, Any] = None,
    ) -> bool:
        """Check if role has specific permission."""
        for permission in self.permissions:
            if permission.name == permission_name:
                if user and resource:
                    return permission.evaluate_conditions(user, resource, context)
                return True
        return False

    def get_inherited_permissions(self) -> list[Permission]:
        """Get all permissions including inherited ones."""
        permissions = set(self.permissions)

        # Add permissions from parent roles
        if self.parent_role:
            permissions.update(self.parent_role.get_inherited_permissions())

        return list(permissions)
