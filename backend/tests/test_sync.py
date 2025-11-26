"""Tests for cloud sync service and API routes."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.sync import (
    ConflictResolution,
    SyncAction,
    SyncClient,
    SyncConflict,
    SyncManifestEntry,
    SyncState,
    UserPreferences,
)
from app.services.sync import SyncService


def create_mock_db() -> MagicMock:
    """
    Create a properly configured mock for AsyncSession.

    SQLAlchemy AsyncSession has:
    - Async methods: execute(), commit(), flush(), refresh(), close(), delete()
    - Sync methods: add(), expire(), expunge()
    """
    mock_db = MagicMock()
    # Configure async methods
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.delete = AsyncMock()
    # Sync methods (add) remain as MagicMock by default
    return mock_db


# -------------------------------------------------------------------------
# Unit Tests: SyncService
# -------------------------------------------------------------------------


class TestSyncServicePreferences:
    """Tests for preference management."""

    @pytest.mark.asyncio
    async def test_get_user_preferences_returns_none_when_not_exists(self) -> None:
        """Test that None is returned when no preferences exist."""
        mock_db = create_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        result = await service.get_user_preferences(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_preferences_returns_preferences(self) -> None:
        """Test that preferences are returned when they exist."""
        mock_db = create_mock_db()
        mock_prefs = MagicMock(spec=UserPreferences)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        result = await service.get_user_preferences(uuid.uuid4())

        assert result is mock_prefs

    @pytest.mark.asyncio
    async def test_create_default_preferences(self) -> None:
        """Test creating default preferences for a new user."""
        mock_db = create_mock_db()
        user_id = uuid.uuid4()

        service = SyncService(mock_db)
        result = await service.create_default_preferences(user_id)

        assert result.user_id == user_id
        assert result.scroll_speed == 1.0
        assert result.note_skin == "default"
        assert result.theme == "dark"
        assert result.language == "en"
        assert result.version == 1
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_preferences_creates_if_not_exists(self) -> None:
        """Test that update creates preferences if they don't exist."""
        mock_db = create_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        user_id = uuid.uuid4()
        service = SyncService(mock_db)

        prefs, conflict = await service.update_preferences(
            user_id,
            {"scroll_speed": 1.5, "theme": "light"},
        )

        assert conflict is False
        assert prefs.scroll_speed == 1.5
        assert prefs.theme == "light"
        assert prefs.version == 2  # Incremented from 1

    @pytest.mark.asyncio
    async def test_update_preferences_with_version_conflict(self) -> None:
        """Test version conflict detection."""
        mock_db = create_mock_db()
        mock_prefs = MagicMock(spec=UserPreferences)
        mock_prefs.version = 5
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_prefs
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)

        prefs, conflict = await service.update_preferences(
            uuid.uuid4(),
            {"scroll_speed": 2.0},
            expected_version=3,  # Mismatched version
        )

        assert conflict is True
        assert prefs.version == 5


class TestSyncServiceClients:
    """Tests for client (device) management."""

    @pytest.mark.asyncio
    async def test_register_client(self) -> None:
        """Test registering a new sync client."""
        mock_db = create_mock_db()
        user_id = uuid.uuid4()

        service = SyncService(mock_db)
        client = await service.register_client(
            user_id=user_id,
            client_name="My Desktop",
            client_type="desktop",
            ip_address="192.168.1.1",
        )

        assert client.user_id == user_id
        assert client.client_name == "My Desktop"
        assert client.client_type == "desktop"
        assert client.last_ip == "192.168.1.1"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_clients(self) -> None:
        """Test getting all clients for a user."""
        mock_db = create_mock_db()
        mock_clients = [MagicMock(spec=SyncClient) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_clients
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        clients = await service.get_user_clients(uuid.uuid4())

        assert len(clients) == 3

    @pytest.mark.asyncio
    async def test_remove_client_success(self) -> None:
        """Test successfully removing a client."""
        mock_db = create_mock_db()
        mock_client = MagicMock(spec=SyncClient)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_client
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        result = await service.remove_client(uuid.uuid4(), uuid.uuid4())

        assert result is True
        mock_db.delete.assert_called_once_with(mock_client)

    @pytest.mark.asyncio
    async def test_remove_client_not_found(self) -> None:
        """Test removing a non-existent client."""
        mock_db = create_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        result = await service.remove_client(uuid.uuid4(), uuid.uuid4())

        assert result is False


class TestSyncServiceManifest:
    """Tests for manifest comparison."""

    @pytest.mark.asyncio
    async def test_compare_manifest_checksums_match(self) -> None:
        """Test that matching checksums result in no action."""
        mock_db = create_mock_db()
        map_id = uuid.uuid4()

        mock_entry = MagicMock(spec=SyncManifestEntry)
        mock_entry.map_id = map_id
        mock_entry.checksum = "sha256:abc123"
        mock_entry.cloud_version = 5
        mock_entry.sync_state = SyncState.SYNCED

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [{"map_id": str(map_id), "version": 5, "checksum": "sha256:abc123"}],
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.NONE.value
        assert actions[0]["reason"] == "checksums_match"

    @pytest.mark.asyncio
    async def test_compare_manifest_local_newer(self) -> None:
        """Test that local newer version results in upload action."""
        mock_db = create_mock_db()
        map_id = uuid.uuid4()

        mock_entry = MagicMock(spec=SyncManifestEntry)
        mock_entry.map_id = map_id
        mock_entry.checksum = "sha256:old"
        mock_entry.cloud_version = 3
        mock_entry.sync_state = SyncState.SYNCED

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [{"map_id": str(map_id), "version": 5, "checksum": "sha256:new"}],
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.UPLOAD.value
        assert actions[0]["reason"] == "local_newer"

    @pytest.mark.asyncio
    async def test_compare_manifest_cloud_newer(self) -> None:
        """Test that cloud newer version results in download action."""
        mock_db = create_mock_db()
        map_id = uuid.uuid4()

        mock_entry = MagicMock(spec=SyncManifestEntry)
        mock_entry.map_id = map_id
        mock_entry.checksum = "sha256:cloud"
        mock_entry.cloud_version = 10
        mock_entry.sync_state = SyncState.SYNCED

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [{"map_id": str(map_id), "version": 5, "checksum": "sha256:local"}],
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.DOWNLOAD.value
        assert actions[0]["reason"] == "cloud_newer"
        assert actions[0]["cloud_version"] == 10

    @pytest.mark.asyncio
    async def test_compare_manifest_conflict(self) -> None:
        """Test that same version with different checksums results in conflict."""
        mock_db = create_mock_db()
        map_id = uuid.uuid4()

        mock_entry = MagicMock(spec=SyncManifestEntry)
        mock_entry.map_id = map_id
        mock_entry.checksum = "sha256:cloud"
        mock_entry.cloud_version = 5
        mock_entry.sync_state = SyncState.SYNCED

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [{"map_id": str(map_id), "version": 5, "checksum": "sha256:local"}],
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.CONFLICT.value
        assert actions[0]["reason"] == "both_modified"

    @pytest.mark.asyncio
    async def test_compare_manifest_local_only(self) -> None:
        """Test that local-only maps result in upload action."""
        mock_db = create_mock_db()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No cloud entries
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        new_map_id = uuid.uuid4()
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [{"map_id": str(new_map_id), "version": 1, "checksum": "sha256:new"}],
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.UPLOAD.value
        assert actions[0]["reason"] == "local_only"

    @pytest.mark.asyncio
    async def test_compare_manifest_cloud_only(self) -> None:
        """Test that cloud-only maps result in download action."""
        mock_db = create_mock_db()
        cloud_map_id = uuid.uuid4()

        mock_entry = MagicMock(spec=SyncManifestEntry)
        mock_entry.map_id = cloud_map_id
        mock_entry.checksum = "sha256:cloud"
        mock_entry.cloud_version = 3
        mock_entry.sync_state = SyncState.SYNCED

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        actions = await service.compare_manifest(
            uuid.uuid4(),
            [],  # No local entries
        )

        assert len(actions) == 1
        assert actions[0]["action"] == SyncAction.DOWNLOAD.value
        assert actions[0]["reason"] == "cloud_only"


class TestSyncServiceConflicts:
    """Tests for conflict resolution."""

    @pytest.mark.asyncio
    async def test_create_conflict(self) -> None:
        """Test creating a sync conflict record."""
        mock_db = create_mock_db()

        service = SyncService(mock_db)
        conflict = await service.create_conflict(
            user_id=uuid.uuid4(),
            map_id=uuid.uuid4(),
            local_version=3,
            cloud_version=5,
            local_checksum="sha256:local",
            cloud_checksum="sha256:cloud",
            differences={"hitObjects": "changed"},
        )

        assert conflict.local_version == 3
        assert conflict.cloud_version == 5
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_conflict(self) -> None:
        """Test resolving a sync conflict."""
        mock_db = create_mock_db()
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conflict
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)
        user_id = uuid.uuid4()
        conflict_id = uuid.uuid4()

        result = await service.resolve_conflict(
            conflict_id=conflict_id,
            user_id=user_id,
            resolution=ConflictResolution.KEEP_LOCAL,
        )

        assert result is mock_conflict
        assert mock_conflict.resolution == ConflictResolution.KEEP_LOCAL
        assert mock_conflict.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_conflict_not_found(self) -> None:
        """Test resolving a non-existent conflict."""
        mock_db = create_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = SyncService(mock_db)

        result = await service.resolve_conflict(
            conflict_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            resolution=ConflictResolution.KEEP_CLOUD,
        )

        assert result is None


class TestSyncServiceUtilities:
    """Tests for utility methods."""

    def test_compute_checksum(self) -> None:
        """Test checksum computation is deterministic."""
        data = {"key": "value", "number": 42}

        checksum1 = SyncService._compute_checksum(data)
        checksum2 = SyncService._compute_checksum(data)

        assert checksum1 == checksum2
        assert checksum1.startswith("sha256:")

    def test_compute_checksum_different_order(self) -> None:
        """Test that key order doesn't affect checksum."""
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}

        assert SyncService._compute_checksum(data1) == SyncService._compute_checksum(
            data2
        )

    def test_compute_beatmap_checksum(self) -> None:
        """Test beatmap checksum uses relevant fields only."""
        beatmap = {
            "metadata": {"title": "Test"},
            "timing": {"bpm": 120},
            "hitObjects": [{"time": 0}],
            "irrelevant": "ignored",
        }

        checksum = SyncService.compute_beatmap_checksum(beatmap)

        assert checksum.startswith("sha256:")

        # Verify irrelevant fields don't affect checksum
        beatmap2 = {
            "metadata": {"title": "Test"},
            "timing": {"bpm": 120},
            "hitObjects": [{"time": 0}],
            "other": "also ignored",
        }

        assert SyncService.compute_beatmap_checksum(beatmap2) == checksum
