from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    SUCCESS = "SUCCESS"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class NotificationResponse(BaseModel):
    id: str
    userId: str
    title: Optional[str]
    notificationType: NotificationType
    body: str
    dismissed: bool
    createdAt: datetime
    expiresAt: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    userId: str
    title: Optional[str] = None
    notificationType: NotificationType
    body: str = Field(..., max_length=5000)
    expiresAt: datetime


class NotificationUpdate(BaseModel):
    dismissed: bool


class NotificationStats(BaseModel):
    total: int
    unread: int
    byType: dict


class BulkNotificationResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    unread: int
    page: int
    pageSize: int
    hasMore: bool
