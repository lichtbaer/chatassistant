"""
Audit policies API endpoints.

This module handles all audit policy related operations including:
- Creating, reading, updating, and deleting audit policies
- Policy management and configuration
"""

import logging
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.audit_extended import (
    AuditPolicyCreate,
    AuditPolicyListResponse,
    AuditPolicyResponse,
    AuditPolicyUpdate,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=AuditPolicyListResponse)
async def get_audit_policies(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit policies with pagination."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_audit_policies(
            db=db,
            page=page,
            size=size,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving audit policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "",
    response_model=AuditPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_audit_policy(
    policy_data: AuditPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new audit policy."""
    try:
        audit_service = get_audit_service()
        return await audit_service.create_audit_policy(
            db=db,
            policy_data=policy_data,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error creating audit policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating audit policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{policy_id}", response_model=AuditPolicyResponse)
async def get_audit_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific audit policy by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_policy(
            db=db,
            policy_id=policy_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit policy not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error retrieving audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{policy_id}", response_model=AuditPolicyResponse)
async def update_audit_policy(
    policy_id: UUID,
    policy_update: AuditPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an audit policy."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_audit_policy(
            db=db,
            policy_id=policy_id,
            policy_update=policy_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit policy not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error updating audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an audit policy."""
    try:
        audit_service = get_audit_service()
        success = await audit_service.delete_audit_policy(
            db=db,
            policy_id=policy_id,
            current_user=current_user,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit policy not found",
            )
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error deleting audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error deleting audit policy {policy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
