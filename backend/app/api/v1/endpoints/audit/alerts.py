"""
Audit alerts API endpoints.

This module handles all audit alert related operations including:
- Creating, reading, updating, and deleting audit alerts
- Alert management and configuration
"""

import logging
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.audit_extended import (
    AuditAlertCreate,
    AuditAlertListResponse,
    AuditAlertResponse,
    AuditAlertUpdate,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditAlertListResponse)
async def get_audit_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit alerts with pagination."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_audit_alerts(
            db=db,
            page=page,
            size=size,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving audit alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "",
    response_model=AuditAlertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_audit_alert(
    alert_data: AuditAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new audit alert."""
    try:
        audit_service = get_audit_service()
        return await audit_service.create_audit_alert(
            db=db,
            alert_data=alert_data,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error creating audit alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating audit alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{alert_id}", response_model=AuditAlertResponse)
async def get_audit_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific audit alert by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_alert(
            db=db,
            alert_id=alert_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit alert not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error retrieving audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{alert_id}", response_model=AuditAlertResponse)
async def update_audit_alert(
    alert_id: UUID,
    alert_update: AuditAlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an audit alert."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_audit_alert(
            db=db,
            alert_id=alert_id,
            alert_update=alert_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit alert not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error updating audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an audit alert."""
    try:
        audit_service = get_audit_service()
        success = await audit_service.delete_audit_alert(
            db=db,
            alert_id=alert_id,
            current_user=current_user,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit alert not found",
            )
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error deleting audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error deleting audit alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
