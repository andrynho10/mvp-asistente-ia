"""
GDPR and Ley 19.628 compliance endpoints.

Implements user rights:
- Right to data access (exportar datos)
- Right to be forgotten (derecho al olvido)
- Right to data portability
- Consent management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import sqlite3
from enum import Enum

from src.auth.middleware import get_current_user
from src.auth.models import User, UserRole
from src.utils.logger import get_logger
from src.security.pii_masker import mask_pii
from src.security.data_retention import DataRetentionManager, DataType

logger = get_logger(__name__)

router = APIRouter(prefix="/gdpr", tags=["GDPR"])


class DeletionStatus(str, Enum):
    """Status of user deletion request."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DataExportFormat(str, Enum):
    """Format for data export."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


@router.post("/export-data")
async def export_user_data(
    format: DataExportFormat = DataExportFormat.JSON,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Export all user data in machine-readable format.

    Rights: GDPR Article 20 (Right to data portability)
    Law: Ley 19.628 Art. 12 (Acceso a datos personales)

    Args:
        format: Export format (json, csv, pdf)
        current_user: Authenticated user

    Returns:
        Export metadata with download URL
    """
    logger.audit("data_export_requested", user_id=current_user.id)

    try:
        # Collect all user data from various sources
        user_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "role": current_user.role.value,
                "created_at": current_user.created_at.isoformat(),
            },
            "profile": await _get_user_profile(current_user.id),
            "sessions": await _get_user_sessions(current_user.id),
            "analytics": await _get_user_analytics(current_user.id),
            "activity": await _get_user_activity(current_user.id),
        }

        # Generate export file
        export_path = await _generate_export_file(
            current_user.id,
            user_data,
            format
        )

        logger.audit(
            "data_export_completed",
            user_id=current_user.id,
            details={"format": format.value, "file": str(export_path)}
        )

        return {
            "status": "success",
            "export_id": current_user.id,
            "format": format.value,
            "created_at": datetime.utcnow().isoformat(),
            "download_url": f"/gdpr/download-export/{current_user.id}",
            "expires_at": (datetime.utcnow().timestamp() + 86400 * 7),  # 7 days
            "message": "Your data has been prepared for export. Download it within 7 days."
        }

    except Exception as e:
        logger.error(f"Error exporting user data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error preparing data export"
        )


@router.post("/request-deletion")
async def request_data_deletion(
    password: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Request account and data deletion (right to be forgotten).

    Rights: GDPR Article 17 (Right to erasure)
    Law: Ley 19.628 Art. 12e (Derecho al olvido)

    Note: Requires password confirmation for security.

    Args:
        password: User's password for confirmation
        current_user: Authenticated user

    Returns:
        Deletion request status with grace period
    """
    from src.auth.repository import UserRepository
    from src.auth.authentication import AuthenticationManager

    logger.audit("deletion_requested", user_id=current_user.id)

    try:
        # Verify password
        repo = UserRepository()
        user = repo.get_by_id(current_user.id)
        if not user or not AuthenticationManager.verify_password(password, user.hashed_password):
            logger.warning(
                f"Failed deletion request - invalid password for user {current_user.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )

        # Mark user for deletion
        deletion_requested_at = datetime.utcnow()
        repo.mark_for_deletion(current_user.id, deletion_requested_at)

        grace_period_days = 30  # From settings

        logger.audit(
            "deletion_scheduled",
            user_id=current_user.id,
            details={
                "grace_period_days": grace_period_days,
                "scheduled_deletion": (
                    datetime.fromtimestamp(
                        deletion_requested_at.timestamp() + grace_period_days * 86400
                    ).isoformat()
                )
            }
        )

        return {
            "status": "pending",
            "message": f"Your account deletion has been scheduled. It will be permanently deleted in {grace_period_days} days.",
            "deletion_requested_at": deletion_requested_at.isoformat(),
            "scheduled_deletion_date": (
                datetime.fromtimestamp(
                    deletion_requested_at.timestamp() + grace_period_days * 86400
                ).isoformat()
            ),
            "grace_period_days": grace_period_days,
            "cancellation_url": "/gdpr/cancel-deletion"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing deletion request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing deletion request"
        )


@router.post("/cancel-deletion")
async def cancel_data_deletion(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Cancel a pending data deletion request.

    Can only be done during the grace period.

    Args:
        current_user: Authenticated user

    Returns:
        Cancellation confirmation
    """
    from src.auth.repository import UserRepository

    logger.audit("deletion_cancelled", user_id=current_user.id)

    try:
        repo = UserRepository()
        user = repo.get_by_id(current_user.id)

        if not user or not user.deletion_requested_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending deletion request"
            )

        # Cancel deletion
        repo.cancel_deletion(current_user.id)

        logger.audit(
            "deletion_cancelled_confirmed",
            user_id=current_user.id
        )

        return {
            "status": "success",
            "message": "Your account deletion request has been cancelled"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling deletion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error cancelling deletion"
        )


@router.get("/consent-status")
async def get_consent_status(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get user's current consent preferences.

    Tracks what data processing the user has consented to.

    Args:
        current_user: Authenticated user

    Returns:
        User's consent preferences
    """
    from src.auth.repository import UserRepository

    try:
        repo = UserRepository()
        user = repo.get_by_id(current_user.id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        consents = {
            "analytics": user.consent_analytics if hasattr(user, 'consent_analytics') else False,
            "marketing": user.consent_marketing if hasattr(user, 'consent_marketing') else False,
            "personalization": user.consent_personalization if hasattr(user, 'consent_personalization') else True,
        }

        return {
            "user_id": current_user.id,
            "consent_preferences": consents,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting consent status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving consent preferences"
        )


@router.post("/update-consent")
async def update_consent_preferences(
    analytics: Optional[bool] = None,
    marketing: Optional[bool] = None,
    personalization: Optional[bool] = None,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Update user's consent preferences.

    Args:
        analytics: Consent for analytics tracking
        marketing: Consent for marketing communications
        personalization: Consent for personalized recommendations
        current_user: Authenticated user

    Returns:
        Updated consent preferences
    """
    from src.auth.repository import UserRepository

    logger.audit(
        "consent_updated",
        user_id=current_user.id,
        details={
            "analytics": analytics,
            "marketing": marketing,
            "personalization": personalization
        }
    )

    try:
        repo = UserRepository()

        # Update consent preferences
        repo.update_consent(
            current_user.id,
            analytics=analytics,
            marketing=marketing,
            personalization=personalization
        )

        return {
            "status": "success",
            "message": "Consent preferences updated",
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error updating consent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating consent preferences"
        )


@router.get("/download-export/{export_id}")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Download exported user data.

    Security: Only user can download their own export.

    Args:
        export_id: Export ID (should match user ID)
        current_user: Authenticated user

    Returns:
        Export file content or metadata
    """
    # Security check
    if export_id != current_user.id:
        logger.warning(f"Unauthorized export download attempt by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's export"
        )

    try:
        export_path = Path(f"data/exports/{export_id}_export.json")

        if not export_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export file not found or has expired"
            )

        with open(export_path) as f:
            export_data = json.load(f)

        logger.audit("export_downloaded", user_id=current_user.id)

        return {
            "status": "success",
            "data": export_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading export"
        )


# Helper functions

async def _get_user_profile(user_id: str) -> dict:
    """Get user profile information."""
    # This would query the user database
    return {"profile_data": "user profile"}


async def _get_user_sessions(user_id: str) -> list:
    """Get user's active and historical sessions."""
    try:
        conn = sqlite3.connect("data/sessions/sessions.db")
        cursor = conn.execute(
            "SELECT id, created_at, expires_at FROM sessions WHERE user_id = ?",
            (user_id,)
        )
        sessions = [
            {
                "id": row[0],
                "created_at": row[1],
                "expires_at": row[2]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return sessions
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        return []


async def _get_user_analytics(user_id: str) -> dict:
    """Get user's analytics data."""
    try:
        conn = sqlite3.connect("data/analytics/analytics.db")
        cursor = conn.execute(
            "SELECT timestamp, event, details FROM metrics WHERE user_id = ? LIMIT 100",
            (user_id,)
        )
        analytics = [
            {
                "timestamp": row[0],
                "event": row[1],
                "details": json.loads(row[2]) if row[2] else {}
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return {"records": len(analytics), "sample": analytics[:10]}
    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        return {}


async def _get_user_activity(user_id: str) -> list:
    """Get user's activity logs."""
    try:
        conn = sqlite3.connect("data/analytics/analytics.db")
        cursor = conn.execute(
            "SELECT timestamp, action, details FROM activity_logs WHERE user_id = ? LIMIT 100",
            (user_id,)
        )
        activity = [
            {
                "timestamp": row[0],
                "action": row[1],
                "details": row[2]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return activity
    except Exception as e:
        logger.error(f"Error getting user activity: {e}")
        return []


async def _generate_export_file(
    user_id: str,
    data: dict,
    format: DataExportFormat
) -> Path:
    """
    Generate export file in requested format.

    Args:
        user_id: User ID
        data: User data to export
        format: Export format

    Returns:
        Path to generated file
    """
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    if format == DataExportFormat.JSON:
        export_path = export_dir / f"{user_id}_export.json"
        with open(export_path, "w") as f:
            json.dump(data, f, indent=2)

    elif format == DataExportFormat.CSV:
        # Simplified CSV export
        export_path = export_dir / f"{user_id}_export.csv"
        # Implementation would flatten JSON to CSV
        with open(export_path, "w") as f:
            f.write("field,value\n")
            for key, value in data.items():
                f.write(f'"{key}","{value}"\n')

    else:  # PDF
        # Would require PDF library like reportlab
        export_path = export_dir / f"{user_id}_export.pdf"
        # Placeholder
        with open(export_path, "w") as f:
            f.write("PDF export placeholder\n")

    return export_path
