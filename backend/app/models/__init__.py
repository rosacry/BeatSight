"""SQLAlchemy models for the BeatSight backend."""

from .ai_job import AIJob
from .credits import (
    CreditBalance,
    CreditPackType,
    CreditPurchase,
    CreditTransaction,
    CreditTransactionType,
)
from .karma import KarmaLedger
from .map_asset import MapAsset
from .map_edit import MapEditProposal, MapVerificationDecision
from .map_version import MapVersion
from .map_vote import MapVote, VoteType
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

__all__ = [
    "AIJob",
    "BillingTransaction",
    "ConflictResolution",
    "CreditBalance",
    "CreditPackType",
    "CreditPurchase",
    "CreditTransaction",
    "CreditTransactionType",
    "KarmaLedger",
    "Map",
    "MapAsset",
    "MapEditProposal",
    "MapVerificationDecision",
    "MapVersion",
    "MapVote",
    "PushSubscription",
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
    "UserPreferences",
    "UserRole",
    "VoteType",
]
