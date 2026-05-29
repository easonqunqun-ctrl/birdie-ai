"""SQLAlchemy 模型聚合导出（供 Alembic autogenerate 使用）."""

from app.models.analysis import (
    AnalysisIssue,
    AnalysisQuota,
    AnalysisRecommendation,
    SwingAnalysis,
)
from app.models.base import Base
from app.models.chat import ChatMessage, ChatQuota, ChatSession
from app.models.coach import (
    AnalysisAnnotation,
    CoachAssignedTask,
    CoachProfile,
    CoachStudentRelation,
    CoachVerification,
    CourseSessionRecap,
)
from app.models.course import Course, CourseCertificate, Lesson, UserCourseProgress
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
from app.models.pro_library import (
    ProClipAnnotation,
    ProPlayer,
    ProSwingClip,
    ProTopic,
    UserProFavorite,
    UserProMatchHistory,
)
from app.models.share import ShareAction
from app.models.training import Drill, PracticeLog, TrainingPlan, TrainingTask
from app.models.user import User
from app.models.user_profile_v2 import UserClub, UserProfileV2

__all__ = [
    "AnalysisAnnotation",
    "AnalysisIssue",
    "AnalysisQuota",
    "AnalysisRecommendation",
    "Base",
    "ChatMessage",
    "ChatQuota",
    "ChatSession",
    "CoachAssignedTask",
    "CoachProfile",
    "CoachStudentRelation",
    "CoachVerification",
    "Course",
    "CourseCertificate",
    "CourseSessionRecap",
    "Drill",
    "Event",
    "EventParticipation",
    "Feedback",
    "Invitation",
    "Lesson",
    "MeetupFeedback",
    "MeetupInvitation",
    "Order",
    "PaymentTransaction",
    "PracticeLog",
    "ProClipAnnotation",
    "ProPlayer",
    "ProSwingClip",
    "ProTopic",
    "SelfOrganizedEvent",
    "ShareAction",
    "SwingAnalysis",
    "TrainingPlan",
    "TrainingTask",
    "User",
    "UserClub",
    "UserCourseProgress",
    "UserProFavorite",
    "UserProMatchHistory",
    "UserProfileV2",
    "Venue",
]
