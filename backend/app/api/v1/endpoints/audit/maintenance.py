"""
Audit maintenance API endpoints.

This module handles all audit maintenance operations including:
- Cleanup of expired logs
- Health checks
- System maintenance tasks
"""

import logging
from typing import Any

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cleanup", response_model=dict[str, Any])
async def cleanup_expired_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clean up expired audit logs based on retention policies."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.cleanup_expired_logs(
            db=db,
            current_user=current_user,
        )

        return {
            "message": "Cleanup completed successfully",
            "details": result,
            "status": "success",
        }
    except AuditError as e:
        logger.exception(f"Error during audit cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error during audit cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/health", response_model=dict[str, Any])
async def audit_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform a health check on the audit system."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.health_check(
            db=db,
            current_user=current_user,
        )

        return {
            "status": "healthy",
            "timestamp": result.get("timestamp"),
            "details": result,
        }
    except AuditError as e:
        logger.exception(f"Audit health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": result.get("timestamp") if "result" in locals() else None,
        }
    except Exception as e:
        logger.exception(f"Unexpected error during audit health check: {e}")
        return {
            "status": "error",
            "error": "Internal server error",
            "timestamp": result.get("timestamp") if "result" in locals() else None,
        }
