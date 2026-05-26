"""SQLAlchemy 模型聚合导出（供 Alembic autogenerate 使用）."""

from app.models.analysis import (
    AnalysisIssue,
    AnalysisQuota,
    AnalysisRecommendation,
    SwingAnalysis,
)
from app.models.base import Base
from app.models.chat import ChatMessage, ChatQuota, ChatSession
from app.models.event import Event
from app.models.feedback import Feedback
from app.models.invitation import Invitation
from app.models.meetup import (
    EventParticipation,
    MeetupFeedback,
    MeetupInvitation,
    SelfOrganizedEvent,
    Venue,
)
from app.models.payment import Order, PaymentTransaction
from app.models.share import ShareAction
from app.models.training import Drill, PracticeLog, TrainingPlan, TrainingTask
from app.models.user import User
from app.models.user_profile_v2 import UserClub, UserProfileV2

__all__ = [
    "AnalysisIssue",
    "AnalysisQuota",
    "AnalysisRecommendation",
    "Base",
    "ChatMessage",
    "ChatQuota",
    "ChatSession",
    "Drill",
    "Event",
    "EventParticipation",
    "Feedback",
    "Invitation",
    "MeetupFeedback",
    "MeetupInvitation",
    "Order",
    "PaymentTransaction",
    "PracticeLog",
    "SelfOrganizedEvent",
    "ShareAction",
    "SwingAnalysis",
    "TrainingPlan",
    "TrainingTask",
    "User",
    "UserClub",
    "UserProfileV2",
    "Venue",
]
