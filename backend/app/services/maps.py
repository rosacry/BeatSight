"""Service layer for map operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.song import Map, MapState, Song, SongStatus


class MapError(Exception):
    """Base exception for map operations."""

    pass


class MapNotFoundError(MapError):
    """Raised when a map cannot be found."""

    pass


class SongNotFoundError(MapError):
    """Raised when a song cannot be found."""

    pass


class VerificationError(MapError):
    """Raised when map verification fails."""

    pass


class DuplicateVerifiedMapError(VerificationError):
    """Raised when trying to verify a map but song already has a verified map."""

    def __init__(self, song_id: uuid.UUID, existing_map_id: uuid.UUID):
        self.song_id = song_id
        self.existing_map_id = existing_map_id
        super().__init__(
            f"Song {song_id} already has verified map {existing_map_id}. "
            "Archive or unverify the existing map first."
        )


class MapService:
    """Encapsulates map-related database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_map(self, map_id: uuid.UUID) -> Map:
        """Get a map by ID."""
        result = await self._session.execute(select(Map).where(Map.id == map_id))
        map_obj = result.scalar_one_or_none()
        if map_obj is None:
            raise MapNotFoundError(f"Map {map_id} not found")
        return map_obj

    async def get_song(self, song_id: uuid.UUID) -> Song:
        """Get a song by ID."""
        result = await self._session.execute(select(Song).where(Song.id == song_id))
        song = result.scalar_one_or_none()
        if song is None:
            raise SongNotFoundError(f"Song {song_id} not found")
        return song

    async def get_verified_map_for_song(self, song_id: uuid.UUID) -> Optional[Map]:
        """Get the verified (canonical) map for a song, if any."""
        result = await self._session.execute(
            select(Map).where(
                and_(
                    Map.song_id == song_id,
                    Map.state == MapState.VERIFIED,
                )
            )
        )
        return result.scalar_one_or_none()

    async def verify_map(
        self,
        map_id: uuid.UUID,
        force: bool = False,
    ) -> Map:
        """
        Verify a map and set it as canonical for its song.

        This enforces single verified map per song:
        - If the song already has a verified map, raises DuplicateVerifiedMapError
        - Unless force=True, which archives the existing verified map

        Args:
            map_id: The map to verify.
            force: If True, archive existing verified map instead of failing.

        Returns:
            The verified map.

        Raises:
            MapNotFoundError: If the map doesn't exist.
            DuplicateVerifiedMapError: If song already has a verified map and force=False.
        """
        map_obj = await self.get_map(map_id)
        song = await self.get_song(map_obj.song_id)

        # Check for existing verified map
        existing_verified = await self.get_verified_map_for_song(song.id)
        if existing_verified and existing_verified.id != map_id:
            if not force:
                raise DuplicateVerifiedMapError(song.id, existing_verified.id)

            # Archive the existing verified map
            existing_verified.state = MapState.ARCHIVED
            existing_verified.is_canonical = False

        # Set this map as verified and canonical
        map_obj.state = MapState.VERIFIED
        map_obj.is_canonical = True

        # Update song's canonical map reference
        song.canonical_map_id = map_id
        song.status = SongStatus.VERIFIED

        await self._session.commit()
        await self._session.refresh(map_obj)

        return map_obj

    async def unverify_map(self, map_id: uuid.UUID) -> Map:
        """
        Remove verification from a map.

        If this was the canonical map, clears the song's canonical_map_id.

        Args:
            map_id: The map to unverify.

        Returns:
            The unverified map.
        """
        map_obj = await self.get_map(map_id)
        song = await self.get_song(map_obj.song_id)

        # Set map to unverified
        map_obj.state = MapState.UNVERIFIED
        map_obj.is_canonical = False

        # Clear song's canonical map if this was it
        if song.canonical_map_id == map_id:
            song.canonical_map_id = None
            song.status = SongStatus.UNVERIFIED

        await self._session.commit()
        await self._session.refresh(map_obj)

        return map_obj

    async def archive_map(self, map_id: uuid.UUID) -> Map:
        """
        Archive a map.

        Archived maps are hidden from normal listings but retained for history.

        Args:
            map_id: The map to archive.

        Returns:
            The archived map.
        """
        map_obj = await self.get_map(map_id)
        song = await self.get_song(map_obj.song_id)

        # Archive the map
        map_obj.state = MapState.ARCHIVED
        map_obj.is_canonical = False

        # Clear song's canonical map if this was it
        if song.canonical_map_id == map_id:
            song.canonical_map_id = None
            # Check if there are other verified maps
            other_verified = await self._session.execute(
                select(Map).where(
                    and_(
                        Map.song_id == song.id,
                        Map.state == MapState.VERIFIED,
                        Map.id != map_id,
                    )
                )
            )
            if other_verified.scalar_one_or_none() is None:
                song.status = SongStatus.UNVERIFIED

        await self._session.commit()
        await self._session.refresh(map_obj)

        return map_obj

    async def get_song_maps(
        self,
        song_id: uuid.UUID,
        include_archived: bool = False,
    ) -> list[Map]:
        """
        Get all maps for a song.

        Args:
            song_id: The song to get maps for.
            include_archived: Whether to include archived maps.

        Returns:
            List of maps for the song.
        """
        query = select(Map).where(Map.song_id == song_id)
        if not include_archived:
            query = query.where(Map.state != MapState.ARCHIVED)

        result = await self._session.execute(query.order_by(Map.created_at))
        return list(result.scalars().all())
