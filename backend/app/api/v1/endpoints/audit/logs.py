"""
Audit logs API endpoints.

This module handles all audit log related operations including:
- Retrieving audit logs with filtering and pagination
- Getting individual audit log details
- Updating audit log metadata
- Exporting audit logs
- Audit statistics
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit_extended import (
    AuditEventCategory,
    AuditEventType,
    ComplianceFramework,
    DataClassification,
)
from app.models.user import User
from app.schemas.audit_extended import (
    AuditLogExportParams,
    AuditLogExportResponse,
    AuditLogListResponse,
    AuditLogUpdate,
    AuditStatisticsResponse,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    user_id: str | None = Query(None, description="Filter by user ID"),
    event_type: AuditEventType | None = Query(
        None,
        description="Filter by event type",
    ),
    event_category: AuditEventCategory | None = Query(
        None,
        description="Filter by event category",
    ),
    severity: str | None = Query(None, description="Filter by severity level"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    compliance_framework: ComplianceFramework | None = Query(
        None,
        description="Filter by compliance framework",
    ),
    data_classification: DataClassification | None = Query(
        None,
        description="Filter by data classification",
    ),
    start_date: datetime | None = Query(
        None,
        description="Start date for filtering",
    ),
    end_date: datetime | None = Query(None, description="End date for filtering"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    include_context: bool = Query(True, description="Include context in response"),
    include_metadata: bool = Query(True, description="Include metadata in response"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit logs with filtering and pagination."""
    try:
        audit_service = get_audit_service()
        filters = {
            "user_id": user_id,
            "event_type": event_type,
            "event_category": event_category,
            "severity": severity,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "compliance_framework": compliance_framework,
            "data_classification": data_classification,
            "start_date": start_date,
            "end_date": end_date,
        }

        return await audit_service.get_audit_logs(
            db=db,
            filters=filters,
            page=page,
            size=size,
            include_context=include_context,
            include_metadata=include_metadata,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{log_id}", response_model=dict[str, Any])
async def get_audit_log(
    log_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific audit log by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_log(
            db=db,
            log_id=log_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error retrieving audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{log_id}", response_model=dict[str, Any])
async def update_audit_log(
    log_id: UUID,
    log_update: AuditLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update audit log metadata."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_audit_log(
            db=db,
            log_id=log_id,
            log_update=log_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error updating audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/statistics/overview", response_model=AuditStatisticsResponse)
async def get_audit_statistics(
    start_date: datetime | None = Query(
        None,
        description="Start date for statistics",
    ),
    end_date: datetime | None = Query(None, description="End date for statistics"),
    organization_id: str | None = Query(
        None,
        description="Organization ID for filtering",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit statistics overview."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_audit_statistics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            organization_id=organization_id,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving audit statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/export", response_model=AuditLogExportResponse)
async def export_audit_logs(
    export_params: AuditLogExportParams,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export audit logs based on specified parameters."""
    try:
        audit_service = get_audit_service()
        return await audit_service.export_audit_logs(
            db=db,
            export_params=export_params,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error exporting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error exporting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
