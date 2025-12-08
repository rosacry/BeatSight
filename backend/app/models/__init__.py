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
from .user import User
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
    "PhoneVerificationAttempt",
    "PhoneVerificationCode",
    "ProcessedWebhookEvent",
    "PushSubscription",
    "REQUIRED_VERIFIERS_FOR_ACCURACY",
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
    "UserAchievement",
    "UserPreferences",
    "UserRole",
    "UserVerificationBonus",
    "VERIFIED_USER_KARMA_BONUS",
    "VoteType",
]
