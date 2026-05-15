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
from app.models.invitation import Invitation
from app.models.payment import Order, PaymentTransaction
from app.models.share import ShareAction
from app.models.training import Drill, PracticeLog, TrainingPlan, TrainingTask
from app.models.user import User

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
    "Invitation",
    "Order",
    "PaymentTransaction",
    "PracticeLog",
    "ShareAction",
    "SwingAnalysis",
    "TrainingPlan",
    "TrainingTask",
    "User",
]
