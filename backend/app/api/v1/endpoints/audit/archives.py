"""
Audit archives API endpoints.

This module handles all audit archive related operations including:
- Managing audit archives
- Archive retrieval and updates
"""

import logging
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.audit_extended import (
    AuditArchiveListResponse,
    AuditArchiveResponse,
    AuditArchiveUpdate,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditArchiveListResponse)
async def get_audit_archives(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit archives with pagination."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_audit_archives(
            db=db,
            page=page,
            size=size,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving audit archives: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit archives: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{archive_id}", response_model=AuditArchiveResponse)
async def get_audit_archive(
    archive_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific audit archive by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_archive(
            db=db,
            archive_id=archive_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit archive not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error retrieving audit archive {archive_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit archive {archive_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{archive_id}", response_model=AuditArchiveResponse)
async def update_audit_archive(
    archive_id: UUID,
    archive_update: AuditArchiveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an audit archive."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_audit_archive(
            db=db,
            archive_id=archive_id,
            archive_update=archive_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit archive not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error updating audit archive {archive_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating audit archive {archive_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
