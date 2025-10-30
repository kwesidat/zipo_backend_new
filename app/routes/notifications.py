from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from app.models.notifications import (
    NotificationResponse,
    NotificationCreate,
    NotificationUpdate,
    NotificationStats,
    BulkNotificationResponse,
    NotificationType,
)
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return user_data
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )


# ========== GET USER NOTIFICATIONS ==========


@router.get("/notifications", response_model=BulkNotificationResponse)
async def get_user_notifications(
    current_user=Depends(get_current_user),
    dismissed: Optional[bool] = None,
    notification_type: Optional[NotificationType] = None,
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get user's notifications with pagination and filtering.

    Query Parameters:
    - dismissed: Filter by dismissed status (true/false)
    - notification_type: Filter by notification type (SUCCESS, INFO, WARNING, ERROR)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)

    Returns:
    - List of notifications
    - Total count
    - Unread count
    - Pagination info
    """
    try:
        user_id = current_user["user_id"]
        offset = (page - 1) * page_size

        # Build query
        query = (
            supabase.table("Notification")
            .select("*", count="exact")
            .eq("userId", user_id)
        )

        # Apply filters
        if dismissed is not None:
            query = query.eq("dismissed", dismissed)

        if notification_type:
            query = query.eq("notificationType", notification_type.value)

        # Filter out expired notifications
        now = datetime.now(timezone.utc).isoformat()
        query = query.gte("expiresAt", now)

        # Get total count for unread notifications
        unread_query = (
            supabase.table("Notification")
            .select("id", count="exact")
            .eq("userId", user_id)
            .eq("dismissed", False)
            .gte("expiresAt", now)
        )
        unread_response = unread_query.execute()
        unread_count = unread_response.count or 0

        # Execute main query with pagination
        query = query.order("createdAt", desc=True).range(offset, offset + page_size - 1)
        response = query.execute()

        notifications = response.data or []
        total = response.count or 0

        has_more = (offset + page_size) < total

        return {
            "notifications": notifications,
            "total": total,
            "unread": unread_count,
            "page": page,
            "pageSize": page_size,
            "hasMore": has_more,
        }

    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications",
        )


# ========== GET NOTIFICATION STATS ==========


@router.get("/notifications/stats", response_model=NotificationStats)
async def get_notification_stats(current_user=Depends(get_current_user)):
    """
    Get notification statistics for the user.

    Returns:
    - Total notification count
    - Unread notification count
    - Breakdown by notification type
    """
    try:
        user_id = current_user["user_id"]
        now = datetime.now(timezone.utc).isoformat()

        # Get total count
        total_response = (
            supabase.table("Notification")
            .select("id", count="exact")
            .eq("userId", user_id)
            .gte("expiresAt", now)
            .execute()
        )
        total = total_response.count or 0

        # Get unread count
        unread_response = (
            supabase.table("Notification")
            .select("id", count="exact")
            .eq("userId", user_id)
            .eq("dismissed", False)
            .gte("expiresAt", now)
            .execute()
        )
        unread = unread_response.count or 0

        # Get breakdown by type
        by_type = {}
        for notif_type in NotificationType:
            type_response = (
                supabase.table("Notification")
                .select("id", count="exact")
                .eq("userId", user_id)
                .eq("notificationType", notif_type.value)
                .eq("dismissed", False)
                .gte("expiresAt", now)
                .execute()
            )
            by_type[notif_type.value] = type_response.count or 0

        return {"total": total, "unread": unread, "byType": by_type}

    except Exception as e:
        logger.error(f"Error fetching notification stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notification statistics",
        )


# ========== GET SINGLE NOTIFICATION ==========


@router.get("/notifications/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str, current_user=Depends(get_current_user)
):
    """Get a single notification by ID"""
    try:
        user_id = current_user["user_id"]

        response = (
            supabase.table("Notification")
            .select("*")
            .eq("id", notification_id)
            .eq("userId", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notification",
        )


# ========== MARK NOTIFICATION AS DISMISSED ==========


@router.patch("/notifications/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: str, current_user=Depends(get_current_user)
):
    """Mark a notification as dismissed"""
    try:
        user_id = current_user["user_id"]

        # Verify ownership
        check_response = (
            supabase.table("Notification")
            .select("id")
            .eq("id", notification_id)
            .eq("userId", user_id)
            .execute()
        )

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )

        # Update notification
        response = (
            supabase.table("Notification")
            .update({"dismissed": True})
            .eq("id", notification_id)
            .execute()
        )

        return {"message": "Notification dismissed successfully", "id": notification_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss notification",
        )


# ========== MARK ALL NOTIFICATIONS AS DISMISSED ==========


@router.post("/notifications/dismiss-all")
async def dismiss_all_notifications(current_user=Depends(get_current_user)):
    """Mark all user notifications as dismissed"""
    try:
        user_id = current_user["user_id"]

        response = (
            supabase.table("Notification")
            .update({"dismissed": True})
            .eq("userId", user_id)
            .eq("dismissed", False)
            .execute()
        )

        count = len(response.data) if response.data else 0

        return {
            "message": f"{count} notification(s) dismissed successfully",
            "count": count,
        }

    except Exception as e:
        logger.error(f"Error dismissing all notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss notifications",
        )


# ========== DELETE NOTIFICATION ==========


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str, current_user=Depends(get_current_user)
):
    """Delete a notification"""
    try:
        user_id = current_user["user_id"]

        # Verify ownership
        check_response = (
            supabase.table("Notification")
            .select("id")
            .eq("id", notification_id)
            .eq("userId", user_id)
            .execute()
        )

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )

        # Delete notification
        supabase.table("Notification").delete().eq("id", notification_id).execute()

        return {
            "message": "Notification deleted successfully",
            "id": notification_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification",
        )


# ========== DELETE ALL DISMISSED NOTIFICATIONS ==========


@router.delete("/notifications/dismissed/cleanup")
async def cleanup_dismissed_notifications(current_user=Depends(get_current_user)):
    """Delete all dismissed notifications for the user"""
    try:
        user_id = current_user["user_id"]

        response = (
            supabase.table("Notification")
            .delete()
            .eq("userId", user_id)
            .eq("dismissed", True)
            .execute()
        )

        count = len(response.data) if response.data else 0

        return {
            "message": f"{count} dismissed notification(s) deleted successfully",
            "count": count,
        }

    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup notifications",
        )


# ========== CREATE NOTIFICATION (Admin/System Use) ==========


@router.post("/notifications/create", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate, current_user=Depends(get_current_user)
):
    """
    Create a notification for a user.
    Note: In production, this should be restricted to admin users or system processes.
    For now, users can create notifications for themselves for testing.
    """
    try:
        user_id = current_user["user_id"]

        # For security, only allow users to create notifications for themselves
        # In production, you'd want admin-only access here
        if notification.userId != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create notifications for yourself",
            )

        notification_data = {
            "id": str(uuid.uuid4()),
            "userId": notification.userId,
            "title": notification.title,
            "notificationType": notification.notificationType.value,
            "body": notification.body,
            "dismissed": False,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": notification.expiresAt.isoformat(),
        }

        response = supabase.table("Notification").insert(notification_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create notification",
            )

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification",
        )
