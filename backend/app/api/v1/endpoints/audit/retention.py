"""
Audit retention rules API endpoints.

This module handles all audit retention rule related operations including:
- Creating, reading, updating, and deleting retention rules
- Retention policy management
"""

import logging
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.audit_extended import (
    RetentionRuleCreate,
    RetentionRuleListResponse,
    RetentionRuleResponse,
    RetentionRuleUpdate,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=RetentionRuleListResponse)
async def get_retention_rules(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get retention rules with pagination."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_retention_rules(
            db=db,
            page=page,
            size=size,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error retrieving retention rules: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving retention rules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "",
    response_model=RetentionRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_retention_rule(
    rule_data: RetentionRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new retention rule."""
    try:
        audit_service = get_audit_service()
        return await audit_service.create_retention_rule(
            db=db,
            rule_data=rule_data,
            current_user=current_user,
        )

    except AuditError as e:
        logger.exception(f"Error creating retention rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating retention rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{rule_id}", response_model=RetentionRuleResponse)
async def get_retention_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific retention rule by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_retention_rule(
            db=db,
            rule_id=rule_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retention rule not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error retrieving retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{rule_id}", response_model=RetentionRuleResponse)
async def update_retention_rule(
    rule_id: UUID,
    rule_update: RetentionRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a retention rule."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_retention_rule(
            db=db,
            rule_id=rule_id,
            rule_update=rule_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retention rule not found",
            )

        return result
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error updating retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error updating retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_retention_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a retention rule."""
    try:
        audit_service = get_audit_service()
        success = await audit_service.delete_retention_rule(
            db=db,
            rule_id=rule_id,
            current_user=current_user,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retention rule not found",
            )
    except HTTPException:
        raise
    except AuditError as e:
        logger.exception(f"Error deleting retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error deleting retention rule {rule_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
