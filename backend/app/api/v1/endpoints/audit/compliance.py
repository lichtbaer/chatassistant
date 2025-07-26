"""
Compliance reporting API endpoints.

This module handles all compliance reporting operations including:
- Creating and managing compliance reports
- Generating compliance reports
- Compliance framework management
"""

import logging
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit_extended import ComplianceFramework
from app.models.user import User
from app.schemas.audit_extended import (
    ComplianceReportCreate,
    ComplianceReportListResponse,
    ComplianceReportParams,
    ComplianceReportResponse,
    ComplianceReportUpdate,
)
from app.services.audit import get_audit_service
from app.utils.exceptions import AuditError, ComplianceError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports", response_model=ComplianceReportListResponse)
async def get_compliance_reports(
    framework: ComplianceFramework | None = Query(
        None,
        description="Filter by framework",
    ),
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get compliance reports with filtering and pagination."""
    try:
        audit_service = get_audit_service()
        return await audit_service.get_compliance_reports(
            db=db,
            framework=framework,
            status=status,
            page=page,
            size=size,
            current_user=current_user,
        )

    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error retrieving compliance reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error retrieving compliance reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/reports",
    response_model=ComplianceReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_compliance_report(
    report_data: ComplianceReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new compliance report."""
    try:
        audit_service = get_audit_service()
        return await audit_service.create_compliance_report(
            db=db,
            report_data=report_data,
            current_user=current_user,
        )

    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error creating compliance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating compliance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/reports/generate", response_model=ComplianceReportResponse)
async def generate_compliance_report(
    report_params: ComplianceReportParams,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a compliance report based on parameters."""
    try:
        audit_service = get_audit_service()
        return await audit_service.generate_compliance_report(
            db=db,
            report_params=report_params,
            current_user=current_user,
        )

    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error generating compliance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error generating compliance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/reports/{report_id}", response_model=ComplianceReportResponse)
async def get_compliance_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific compliance report by ID."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_compliance_report(
            db=db,
            report_id=report_id,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compliance report not found",
            )

        return result
    except HTTPException:
        raise
    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error retrieving compliance report {report_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error retrieving compliance report {report_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/reports/{report_id}", response_model=ComplianceReportResponse)
async def update_compliance_report(
    report_id: UUID,
    report_update: ComplianceReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a compliance report."""
    try:
        audit_service = get_audit_service()
        result = await audit_service.update_compliance_report(
            db=db,
            report_id=report_id,
            report_update=report_update,
            current_user=current_user,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compliance report not found",
            )

        return result
    except HTTPException:
        raise
    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error updating compliance report {report_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error updating compliance report {report_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_compliance_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a compliance report."""
    try:
        audit_service = get_audit_service()
        success = await audit_service.delete_compliance_report(
            db=db,
            report_id=report_id,
            current_user=current_user,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compliance report not found",
            )
    except HTTPException:
        raise
    except (AuditError, ComplianceError) as e:
        logger.exception(f"Error deleting compliance report {report_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error deleting compliance report {report_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
