"""SQLAlchemy models for the BeatSight backend."""

from .achievement import Achievement, AchievementCategory, UserAchievement
from .ai_job import AIJob
from .credits import (
    CreditBalance,
    CreditPackType,
    CreditPurchase,
    CreditTransaction,
    CreditTransactionType,
)
from .forum import (
    Forum,
    ForumCategory,
    ForumPoll,
    ForumPollOption,
    ForumPollVote,
    ForumPost,
    ForumPostVote,
    ForumPostVoteType,
    ForumReadTracker,
    ForumTopic,
    ForumTopicStatus,
    ForumTopicType,
    ForumTopicVote,
    ForumTopicWatch,
)
from .karma import KarmaLedger, KarmaReason
from .map_accuracy import (
    AccuracyVoteType,
    MapAccuracyConsensus,
    MapAccuracyStatus,
    MapAccuracyVote,
    UserVerificationBonus,
    REQUIRED_VERIFIERS_FOR_ACCURACY,
    VERIFIED_USER_KARMA_BONUS,
)
from .map_asset import MapAsset
from .map_edit import MapEditProposal, MapVerificationDecision
from .map_version import MapVersion
from .map_vote import MapVote, VoteType
from .moderation import ModerationAction, UserAccountHistory
from .phone_verification import PhoneVerificationAttempt, PhoneVerificationCode
from .push_subscription import PushSubscription
from .role import Role, UserRole
from .song import Map, Song
from .subscription import BillingTransaction, Subscription
from .sync import (
    ConflictResolution,
    SyncAction,
    SyncClient,
    SyncConflict,
    SyncLog,
    SyncManifestEntry,
    SyncState,
    UserPreferences,
)
from .training_contribution import (
    ContributionConsent,
    ContributionStatus,
    CorrectionType,
    TrainingContribution,
)
from .social import (
    DirectMessage,
    ReportStatus,
    ReportType,
    UserBlock,
    UserReport,
)
from .user import RestrictionLevel, User
from .user_settings import ReEvaluationPolicy, UploadVisibility, UserSettings
from .user_tag import UserTag
from .webhook_event import ProcessedWebhookEvent

__all__ = [
    "AccuracyVoteType",
    "Achievement",
    "AchievementCategory",
    "AIJob",
    "BillingTransaction",
    "ConflictResolution",
    "CreditBalance",
    "CreditPackType",
    "CreditPurchase",
    "CreditTransaction",
    "CreditTransactionType",
    "DirectMessage",
    "Forum",
    "ForumCategory",
    "ForumPoll",
    "ForumPollOption",
    "ForumPollVote",
    "ForumPost",
    "ForumPostVote",
    "ForumPostVoteType",
    "ForumReadTracker",
    "ForumTopic",
    "ForumTopicStatus",
    "ForumTopicType",
    "ForumTopicVote",
    "ForumTopicWatch",
    "KarmaLedger",
    "KarmaReason",
    "Map",
    "MapAccuracyConsensus",
    "MapAccuracyStatus",
    "MapAccuracyVote",
    "MapAsset",
    "MapEditProposal",
    "MapVerificationDecision",
    "MapVersion",
    "MapVote",
    "ModerationAction",
    "PhoneVerificationAttempt",
    "PhoneVerificationCode",
    "ProcessedWebhookEvent",
    "PushSubscription",
    "REQUIRED_VERIFIERS_FOR_ACCURACY",
    "ReportStatus",
    "ReportType",
    "RestrictionLevel",
    "Role",
    "Song",
    "Subscription",
    "SyncAction",
    "SyncClient",
    "SyncConflict",
    "SyncLog",
    "SyncManifestEntry",
    "SyncState",
    "TrainingContribution",
    "ContributionConsent",
    "ContributionStatus",
    "CorrectionType",
    "User",
    "UserAccountHistory",
    "UserAchievement",
    "UserBlock",
    "UserPreferences",
    "UserReport",
    "UserRole",
    "UserSettings",
    "UserTag",
    "UploadVisibility",
    "ReEvaluationPolicy",
    "UserVerificationBonus",
    "VERIFIED_USER_KARMA_BONUS",
    "VoteType",
]
