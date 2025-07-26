"""
Extended audit logging system for comprehensive compliance.

This module provides detailed audit trails, compliance reporting,
and support for various compliance frameworks including GDPR, SOX, and ISO 27001.
"""

import uuid
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class AuditEventCategory(str, Enum):
    """Audit event categories for classification."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_CONFIGURATION = "system_configuration"
    USER_MANAGEMENT = "user_management"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    BUSINESS_PROCESS = "business_process"
    INTEGRATION = "integration"


class AuditEventType(str, Enum):
    """Extended audit event types."""

    # Authentication Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_TERMINATED = "session_terminated"

    # Authorization Events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    ACCESS_DENIED = "access_denied"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PRIVILEGE_DEESCALATION = "privilege_deescalation"

    # Data Access Events
    DATA_VIEWED = "data_viewed"
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    DATA_SEARCHED = "data_searched"
    DATA_FILTERED = "data_filtered"
    DATA_SORTED = "data_sorted"

    # Data Modification Events
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_RESTORED = "data_restored"
    BULK_OPERATION = "bulk_operation"

    # System Configuration Events
    CONFIGURATION_CHANGED = "configuration_changed"
    SETTING_MODIFIED = "setting_modified"
    FEATURE_ENABLED = "feature_enabled"
    FEATURE_DISABLED = "feature_disabled"
    SYSTEM_MAINTENANCE = "system_maintenance"

    # User Management Events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_LOCKED = "user_locked"
    USER_UNLOCKED = "user_unlocked"
    GROUP_CREATED = "group_created"
    GROUP_UPDATED = "group_updated"
    GROUP_DELETED = "group_deleted"
    DOMAIN_CREATED = "domain_created"
    DOMAIN_UPDATED = "domain_updated"
    DOMAIN_DELETED = "domain_deleted"

    # Security Events
    SECURITY_ALERT = "security_alert"
    THREAT_DETECTED = "threat_detected"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    MALWARE_DETECTED = "malware_detected"
    DATA_BREACH = "data_breach"
    COMPLIANCE_VIOLATION = "compliance_violation"

    # Compliance Events
    AUDIT_REPORT_GENERATED = "audit_report_generated"
    COMPLIANCE_CHECK = "compliance_check"
    POLICY_VIOLATION = "policy_violation"
    RETENTION_POLICY_APPLIED = "retention_policy_applied"
    DATA_PURGED = "data_purged"

    # Business Process Events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Integration Events
    API_CALL = "api_call"
    WEBHOOK_TRIGGERED = "webhook_triggered"
    EXTERNAL_SYSTEM_SYNC = "external_system_sync"
    SSO_AUTHENTICATION = "sso_authentication"
    LDAP_SYNC = "ldap_sync"
    SAML_AUTHENTICATION = "saml_authentication"
    OAUTH_AUTHENTICATION = "oauth_authentication"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks."""

    GDPR = "gdpr"
    SOX = "sox"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOC2 = "soc2"
    CCPA = "ccpa"
    LGPD = "lgpd"


class DataClassification(str, Enum):
    """Data classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    CLASSIFIED = "classified"


class ExtendedAuditLog(Base):
    """Extended audit log model with comprehensive compliance features."""

    __tablename__ = "extended_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event identification
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    event_category = Column(SQLEnum(AuditEventCategory), nullable=False, index=True)
    severity = Column(
        SQLEnum(AuditSeverity),
        default=AuditSeverity.INFO,
        nullable=False,
        index=True,
    )

    # Timestamps
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    event_duration = Column(Integer, nullable=True)  # Duration in milliseconds

    # User and session information
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    username = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)

    # Resource information
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    resource_name = Column(String(255), nullable=True)

    # Action details
    action = Column(String(100), nullable=True, index=True)
    action_result = Column(String(50), nullable=True)  # success, failure, partial
    error_message = Column(Text, nullable=True)

    # Context and metadata
    context = Column(JSON, nullable=True)  # Additional context information
    audit_metadata = Column(JSON, nullable=True)  # Extended metadata
    tags = Column(JSON, nullable=True)  # Custom tags for categorization

    # Compliance information
    compliance_frameworks = Column(JSON, nullable=True)  # List of applicable frameworks
    data_classification = Column(SQLEnum(DataClassification), nullable=True)
    retention_period = Column(Integer, nullable=True)  # Retention period in days
    legal_hold = Column(Boolean, default=False, nullable=False)

    # Business context
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    project = Column(String(100), nullable=True, index=True)

    # Security context
    threat_level = Column(String(50), nullable=True)  # low, medium, high, critical
    risk_score = Column(Integer, nullable=True)  # 0-100 risk score
    security_impact = Column(String(50), nullable=True)  # none, low, medium, high

    # Relationships
    user = relationship("User", back_populates="extended_audit_logs")

    # Indexes for performance
    __table_args__ = (
        Index("idx_audit_timestamp_user", "timestamp", "user_id"),
        Index("idx_audit_event_type_timestamp", "event_type", "timestamp"),
        Index("idx_audit_severity_timestamp", "severity", "timestamp"),
        Index(
            "idx_audit_resource_timestamp",
            "resource_type",
            "resource_id",
            "timestamp",
        ),
        # Index("idx_audit_compliance_timestamp", "compliance_frameworks", "timestamp"),  # Disabled due to JSON column indexing issues
        {"extend_existing": True},
    )

    def __repr__(self) -> str:
        return f"<ExtendedAuditLog(id={self.id}, event_type='{self.event_type}', timestamp='{self.timestamp}')>"

    @property
    def is_high_severity(self) -> bool:
        """Check if event is high severity."""
        return self.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]

    @property
    def requires_immediate_attention(self) -> bool:
        """Check if event requires immediate attention."""
        return (
            self.severity == AuditSeverity.CRITICAL
            or self.threat_level == "critical"
            or self.risk_score
            and self.risk_score >= 80
        )

    @property
    def is_compliance_relevant(self) -> bool:
        """Check if event is relevant for compliance."""
        return (
            self.compliance_frameworks is not None
            or self.data_classification
            in [
                DataClassification.CONFIDENTIAL,
                DataClassification.RESTRICTED,
                DataClassification.CLASSIFIED,
            ]
            or self.event_category
            in [AuditEventCategory.SECURITY, AuditEventCategory.COMPLIANCE]
        )


class AuditPolicy(Base):
    """Audit policy configuration."""

    __tablename__ = "audit_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Policy scope
    event_types = Column(JSON, nullable=True)  # List of event types to audit
    event_categories = Column(JSON, nullable=True)  # List of event categories to audit
    resource_types = Column(JSON, nullable=True)  # List of resource types to audit
    user_roles = Column(JSON, nullable=True)  # List of user roles to audit

    # Policy settings
    enabled = Column(Boolean, default=True, nullable=False)
    log_success = Column(Boolean, default=True, nullable=False)
    log_failure = Column(Boolean, default=True, nullable=False)
    include_context = Column(Boolean, default=True, nullable=False)
    include_metadata = Column(Boolean, default=True, nullable=False)

    # Retention settings
    retention_days = Column(Integer, default=365, nullable=False)
    archive_after_days = Column(Integer, default=90, nullable=False)
    legal_hold_retention = Column(Integer, default=2555, nullable=False)  # 7 years

    # Compliance settings
    compliance_frameworks = Column(JSON, nullable=True)
    data_classification = Column(SQLEnum(DataClassification), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AuditPolicy(id={self.id}, name='{self.name}')>"


class AuditRetentionRule(Base):
    """Audit retention rules for compliance."""

    __tablename__ = "audit_retention_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Rule criteria
    event_types = Column(JSON, nullable=True)
    event_categories = Column(JSON, nullable=True)
    severity_levels = Column(JSON, nullable=True)
    compliance_frameworks = Column(JSON, nullable=True)
    data_classification = Column(SQLEnum(DataClassification), nullable=True)

    # Retention settings
    retention_days = Column(Integer, nullable=False)
    archive_days = Column(Integer, nullable=True)
    legal_hold = Column(Boolean, default=False, nullable=False)

    # Action settings
    action_on_expiry = Column(
        String(50),
        default="delete",
        nullable=False,
    )  # delete, archive, anonymize
    notify_before_expiry = Column(
        Integer,
        nullable=True,
    )  # Days before expiry to notify

    # Status
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AuditRetentionRule(id={self.id}, name='{self.name}')>"


class ComplianceReport(Base):
    """Compliance reports and findings."""

    __tablename__ = "compliance_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Report details
    framework = Column(SQLEnum(ComplianceFramework), nullable=False, index=True)
    report_type = Column(String(100), nullable=False)  # audit, assessment, review
    report_period = Column(String(100), nullable=True)  # Q1 2024, Annual 2024

    # Report content
    findings = Column(JSON, nullable=True)  # Compliance findings
    recommendations = Column(JSON, nullable=True)  # Recommendations
    metrics = Column(JSON, nullable=True)  # Compliance metrics

    # Status
    status = Column(
        String(50),
        default="draft",
        nullable=False,
    )  # draft, review, approved, archived
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    generated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by = relationship("User", foreign_keys="ComplianceReport.approved_by")

    def __repr__(self) -> str:
        return f"<ComplianceReport(id={self.id}, name='{self.name}', framework='{self.framework}')>"


class AuditAlert(Base):
    """Audit alerts for critical events."""

    __tablename__ = "audit_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Alert criteria
    event_types = Column(JSON, nullable=True)
    severity_levels = Column(JSON, nullable=True)
    threshold_count = Column(Integer, default=1, nullable=False)
    threshold_period = Column(Integer, default=3600, nullable=False)  # Seconds

    # Alert actions
    notification_channels = Column(JSON, nullable=True)  # email, slack, webhook
    notification_recipients = Column(JSON, nullable=True)
    escalation_rules = Column(JSON, nullable=True)

    # Status
    enabled = Column(Boolean, default=True, nullable=False)
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AuditAlert(id={self.id}, name='{self.name}')>"


class AuditArchive(Base):
    """Archived audit logs for long-term storage."""

    __tablename__ = "audit_archives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Archive details
    archive_name = Column(String(255), nullable=False)
    archive_period = Column(String(100), nullable=False)  # Q1 2024, Annual 2024
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    # Storage information
    storage_location = Column(String(500), nullable=True)  # S3, local, etc.
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    compression_ratio = Column(Float, nullable=True)

    # Content information
    record_count = Column(Integer, nullable=True)
    compliance_frameworks = Column(JSON, nullable=True)
    data_classification = Column(SQLEnum(DataClassification), nullable=True)

    # Status
    status = Column(
        String(50),
        default="archiving",
        nullable=False,
    )  # archiving, completed, failed
    archived_at = Column(DateTime(timezone=True), nullable=True)
    retention_expiry = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<AuditArchive(id={self.id}, archive_name='{self.archive_name}')>"
