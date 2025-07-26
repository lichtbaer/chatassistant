"""
Domain-based group system for flexible user organization.

This module implements a sophisticated domain group system that allows
organizations to create flexible user groups based on domains, projects,
departments, or functional areas with shared access to resources.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    ForeignKey,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class DomainType(str, Enum):
    """Domain types for categorization."""

    PROJECT = "project"
    DEPARTMENT = "department"
    TEAM = "team"
    FUNCTIONAL_AREA = "functional_area"
    CLIENT = "client"
    PRODUCT = "product"
    GEOGRAPHIC = "geographic"
    TEMPORARY = "temporary"
    CROSS_FUNCTIONAL = "cross_functional"


class AccessLevel(str, Enum):
    """Access levels for domain resources."""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    FULL_ACCESS = "full_access"
    ADMIN = "admin"
    OWNER = "owner"


class ResourceType(str, Enum):
    """Resource types that can be shared within domains."""

    ASSISTANT = "assistant"
    DOCUMENT = "document"
    KNOWLEDGE_BASE = "knowledge_base"
    TOOL = "tool"
    CONVERSATION = "conversation"
    WORKSPACE = "workspace"
    TEMPLATE = "template"
    WORKFLOW = "workflow"


# Association table for domain group members
domain_group_members = Table(
    "domain_group_members",
    Base.metadata,
    Column(
        "domain_group_id",
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        primary_key=True,
    ),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column(
        "access_level",
        SQLEnum(AccessLevel),
        default=AccessLevel.READ_WRITE,
        nullable=False,
    ),
    Column("joined_at", DateTime(timezone=True), server_default=func.now()),
    Column("invited_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
    Column("is_active", Boolean, default=True, nullable=False),
    extend_existing=True,
)


# Association table for domain group resources
domain_group_resources = Table(
    "domain_group_resources",
    Base.metadata,
    Column(
        "domain_group_id",
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        primary_key=True,
    ),
    Column("resource_id", String(255), primary_key=True),
    Column("resource_type", SQLEnum(ResourceType), nullable=False),
    Column(
        "access_level",
        SQLEnum(AccessLevel),
        default=AccessLevel.READ_WRITE,
        nullable=False,
    ),
    Column("added_at", DateTime(timezone=True), server_default=func.now()),
    Column("added_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
    Column("is_active", Boolean, default=True, nullable=False),
    extend_existing=True,
)


# Association table for domain group hierarchy
domain_group_hierarchy = Table(
    "domain_group_hierarchy",
    Base.metadata,
    Column(
        "parent_domain_id",
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        primary_key=True,
    ),
    Column(
        "child_domain_id",
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        primary_key=True,
    ),
    Column(
        "relationship_type",
        String(50),
        default="contains",
        nullable=False,
    ),  # contains, collaborates, reports_to
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    extend_existing=True,
)


class DomainGroup(Base):
    """Domain group model for flexible user organization."""

    __tablename__ = "domain_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    display_name = Column(String(200), nullable=True)

    # Domain categorization
    domain_type = Column(SQLEnum(DomainType), nullable=False, index=True)
    parent_domain_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        nullable=True,
    )

    # Organization and metadata
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    external_id = Column(
        String(255),
        nullable=True,
        index=True,
    )  # For external system integration
    tags = Column(JSON, nullable=True)  # Flexible tagging system

    # Domain settings
    is_public = Column(Boolean, default=False, nullable=False)  # Public domain groups
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)

    # Access control
    default_access_level = Column(
        SQLEnum(AccessLevel),
        default=AccessLevel.READ_WRITE,
        nullable=False,
    )
    allow_self_join = Column(Boolean, default=False, nullable=False)
    require_approval = Column(Boolean, default=True, nullable=False)

    # Domain-specific settings
    settings = Column(JSON, nullable=True)  # Domain-specific configuration
    permissions = Column(JSON, nullable=True)  # Custom permissions for the domain

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For temporary domains

    # Relationships
    members = relationship(
        "User",
        secondary=domain_group_members,
        primaryjoin="DomainGroup.id == domain_group_members.c.domain_group_id",
        secondaryjoin="User.id == domain_group_members.c.user_id",
        back_populates="domain_groups",
        lazy="dynamic",
    )

    resources = relationship(
        "DomainResource",
        back_populates="domain_group",
        lazy="dynamic",
    )

    # Hierarchy relationships
    parent_domain = relationship(
        "DomainGroup",
        remote_side=[id],
        backref="child_domains",
    )

    # Domain managers
    # Temporarily commented out to fix registration
    # managers = relationship(
    #     "User",
    #     secondary="domain_group_managers",
    #     back_populates="managed_domains"
    # )

    def __repr__(self) -> str:
        return f"<DomainGroup(id={self.id}, name='{self.name}', type='{self.domain_type}')>"

    @property
    def member_count(self) -> int:
        """Get active member count."""
        return self.members.filter_by(is_active=True).count()

    @property
    def resource_count(self) -> int:
        """Get active resource count."""
        return self.resources.filter_by(is_active=True).count()

    @property
    def is_expired(self) -> bool:
        """Check if domain group is expired."""
        if self.expires_at:
            return datetime.now(UTC) > self.expires_at
        return False

    def has_member(self, user_id: str, access_level: AccessLevel = None) -> bool:
        """Check if user is a member with specific access level."""
        query = self.members.filter_by(id=user_id, is_active=True)
        if access_level:
            query = query.filter_by(access_level=access_level)
        return query.first() is not None

    def get_member_access_level(self, user_id: str) -> AccessLevel | None:
        """Get user's access level in this domain."""
        member = self.members.filter_by(id=user_id, is_active=True).first()
        return member.access_level if member else None

    def can_access_resource(
        self,
        user_id: str,
        resource_type: ResourceType,
        required_level: AccessLevel = AccessLevel.READ_ONLY,
    ) -> bool:
        """Check if user can access resources of specific type."""
        member = self.members.filter_by(id=user_id, is_active=True).first()
        if not member:
            return False

        # Check if user's access level meets required level
        access_levels = [
            AccessLevel.READ_ONLY,
            AccessLevel.READ_WRITE,
            AccessLevel.FULL_ACCESS,
            AccessLevel.ADMIN,
            AccessLevel.OWNER,
        ]
        user_level_index = access_levels.index(member.access_level)
        required_level_index = access_levels.index(required_level)

        return user_level_index >= required_level_index

    def get_inherited_permissions(self) -> set[str]:
        """Get permissions including inherited ones from parent domains."""
        permissions = set(self.permissions or [])

        # Add permissions from parent domains
        if self.parent_domain:
            permissions.update(self.parent_domain.get_inherited_permissions())

        return permissions


# Association table for domain group managers
domain_group_managers = Table(
    "domain_group_managers",
    Base.metadata,
    Column(
        "domain_group_id",
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        primary_key=True,
    ),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column(
        "manager_type",
        String(50),
        default="manager",
        nullable=False,
    ),  # manager, admin, owner
    Column("assigned_at", DateTime(timezone=True), server_default=func.now()),
    Column("assigned_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=True),
)


class DomainResource(Base):
    """Domain resource model for managing shared resources."""

    __tablename__ = "domain_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        nullable=False,
    )

    # Resource identification
    resource_id = Column(String(255), nullable=False, index=True)
    resource_type = Column(SQLEnum(ResourceType), nullable=False, index=True)
    resource_name = Column(String(200), nullable=True)

    # Access control
    access_level = Column(
        SQLEnum(AccessLevel),
        default=AccessLevel.READ_WRITE,
        nullable=False,
    )
    is_public = Column(Boolean, default=False, nullable=False)

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    resource_metadata = Column(JSON, nullable=True)  # Additional resource metadata

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    domain_group = relationship("DomainGroup", back_populates="resources")

    def __repr__(self) -> str:
        return f"<DomainResource(id={self.id}, type='{self.resource_type}', resource_id='{self.resource_id}')>"

    @property
    def is_expired(self) -> bool:
        """Check if resource access is expired."""
        if self.expires_at:
            return datetime.now(UTC) > self.expires_at
        return False


class DomainInvitation(Base):
    """Domain invitation model for managing join requests."""

    __tablename__ = "domain_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        nullable=False,
    )

    # Invitation details
    email = Column(String(255), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    access_level = Column(
        SQLEnum(AccessLevel),
        default=AccessLevel.READ_WRITE,
        nullable=False,
    )

    # Invitation status
    status = Column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, accepted, declined, expired
    token = Column(String(255), nullable=False, unique=True, index=True)

    # Metadata
    message = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    domain_group = relationship("DomainGroup")
    invited_by = relationship("User", foreign_keys="DomainInvitation.user_id")

    def __repr__(self) -> str:
        return f"<DomainInvitation(id={self.id}, email='{self.email}', status='{self.status}')>"

    @property
    def is_expired(self) -> bool:
        """Check if invitation is expired."""
        return datetime.now(UTC) > self.expires_at


class DomainActivity(Base):
    """Domain activity log for tracking domain-related actions."""

    __tablename__ = "domain_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domain_groups.id"),
        nullable=False,
    )

    # Activity details
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    activity_type = Column(String(100), nullable=False, index=True)
    resource_type = Column(SQLEnum(ResourceType), nullable=True)
    resource_id = Column(String(255), nullable=True)

    # Activity data
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    domain_group = relationship("DomainGroup")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<DomainActivity(id={self.id}, type='{self.activity_type}', domain='{self.domain_group_id}')>"
