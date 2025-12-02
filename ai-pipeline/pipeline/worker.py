"""
BeatSight AI Pipeline Worker

Polls the backend API for jobs and processes them.
Designed to run as a long-lived container service.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from .process import process_audio_file

# =============================================================================
# Configuration
# =============================================================================
@dataclass
class WorkerConfig:
    """Worker configuration from environment variables."""
    
    api_url: str = os.getenv("BEATSIGHT_API_URL", "http://localhost:8000/api")
    worker_id: uuid.UUID = uuid.UUID(os.getenv("WORKER_ID", str(uuid.uuid4())))
    heartbeat_interval: int = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "30"))
    poll_interval: int = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    max_audio_duration: int = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", "600"))
    temp_dir: str = os.getenv("WORKER_TEMP_DIR", "/tmp/beatsight-worker")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # S3/storage configuration (for downloading audio and uploading results)
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local")
    
    def __post_init__(self):
        # Ensure temp directory exists
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)


# =============================================================================
# Logging
# =============================================================================
def setup_logging(config: WorkerConfig) -> structlog.BoundLogger:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if os.getenv("LOG_JSON", "false").lower() == "true"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    import logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.log_level.upper()),
    )
    
    return structlog.get_logger().bind(worker_id=str(config.worker_id))


# =============================================================================
# API Client
# =============================================================================
class APIClient:
    """HTTP client for backend API communication."""
    
    def __init__(self, config: WorkerConfig, log: structlog.BoundLogger):
        self.config = config
        self.log = log
        self.client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=30.0,
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def claim_job(self) -> dict[str, Any] | None:
        """Try to claim the next available job."""
        try:
            response = await self.client.post(
                "/ai-jobs/claim",
                params={"worker_id": str(self.config.worker_id)},
            )
            if response.status_code == 200:
                data = response.json()
                if data:
                    return data
            return None
        except httpx.HTTPError as e:
            self.log.error("Failed to claim job", error=str(e))
            return None
    
    async def heartbeat(self, job_id: uuid.UUID) -> bool:
        """Send heartbeat for a job."""
        try:
            response = await self.client.post(
                f"/ai-jobs/{job_id}/heartbeat",
                params={"worker_id": str(self.config.worker_id)},
            )
            return response.status_code == 204
        except httpx.HTTPError as e:
            self.log.warning("Heartbeat failed", job_id=str(job_id), error=str(e))
            return False
    
    async def update_progress(
        self, 
        job_id: uuid.UUID, 
        percent: int, 
        message: str | None = None
    ) -> bool:
        """Update job progress."""
        try:
            response = await self.client.patch(
                f"/ai-jobs/{job_id}/progress",
                json={
                    "worker_id": str(self.config.worker_id),
                    "progress_percent": percent,
                    "progress_message": message,
                },
            )
            return response.status_code == 204
        except httpx.HTTPError as e:
            self.log.warning("Progress update failed", job_id=str(job_id), error=str(e))
            return False
    
    async def get_song(self, song_id: uuid.UUID) -> dict[str, Any] | None:
        """Get song metadata including audio URL."""
        try:
            response = await self.client.get(f"/songs/{song_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.HTTPError as e:
            self.log.error("Failed to get song", song_id=str(song_id), error=str(e))
            return None
    
    async def release_job(self, job_id: uuid.UUID) -> bool:
        """Release a job back to the queue."""
        try:
            response = await self.client.post(f"/ai-jobs/{job_id}/release")
            return response.status_code == 204
        except httpx.HTTPError as e:
            self.log.error("Failed to release job", job_id=str(job_id), error=str(e))
            return False


# =============================================================================
# Job Processor
# =============================================================================
class JobProcessor:
    """Processes AI generation jobs."""
    
    def __init__(
        self, 
        config: WorkerConfig, 
        api: APIClient, 
        log: structlog.BoundLogger
    ):
        self.config = config
        self.api = api
        self.log = log
        self._heartbeat_task: asyncio.Task | None = None
        self._current_job_id: uuid.UUID | None = None
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeats while processing."""
        while self._current_job_id:
            await asyncio.sleep(self.config.heartbeat_interval)
            if self._current_job_id:
                await self.api.heartbeat(self._current_job_id)
    
    def _start_heartbeat(self, job_id: uuid.UUID):
        """Start background heartbeat task."""
        self._current_job_id = job_id
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    def _stop_heartbeat(self):
        """Stop background heartbeat task."""
        self._current_job_id = None
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
    
    async def process_job(self, job: dict[str, Any]) -> bool:
        """Process a single job. Returns True on success."""
        job_id = uuid.UUID(job["id"])
        song_id = uuid.UUID(job["song_id"])
        
        log = self.log.bind(job_id=str(job_id), song_id=str(song_id))
        log.info("Starting job processing")
        
        try:
            self._start_heartbeat(job_id)
            
            # Step 1: Get song metadata
            await self.api.update_progress(job_id, 5, "Fetching song metadata...")
            song = await self.api.get_song(song_id)
            if not song:
                log.error("Song not found")
                return False
            
            # Step 2: Download audio
            await self.api.update_progress(job_id, 10, "Downloading audio...")
            audio_path = await self._download_audio(song, log)
            if not audio_path:
                log.error("Failed to download audio")
                return False
            
            # Step 3: Process audio
            await self.api.update_progress(job_id, 20, "Separating drums...")
            output_path = Path(self.config.temp_dir) / f"{job_id}.bsm"
            
            # Run the pipeline with progress callbacks
            try:
                result = await self._run_pipeline(
                    job_id=job_id,
                    audio_path=audio_path,
                    output_path=output_path,
                    log=log,
                )
            except Exception as e:
                log.exception("Pipeline failed", error=str(e))
                return False
            finally:
                # Cleanup downloaded audio
                if audio_path.exists():
                    audio_path.unlink()
            
            # Step 4: Upload results
            await self.api.update_progress(job_id, 95, "Uploading results...")
            success = await self._upload_results(job_id, song_id, output_path, result, log)
            
            if success:
                await self.api.update_progress(job_id, 100, "Complete")
                log.info("Job completed successfully")
            
            return success
            
        except Exception as e:
            log.exception("Job failed", error=str(e))
            return False
        finally:
            self._stop_heartbeat()
    
    async def _download_audio(
        self, 
        song: dict[str, Any], 
        log: structlog.BoundLogger
    ) -> Path | None:
        """Download audio file from storage."""
        from .storage_utils import get_storage_client, StorageError
        
        audio_url = song.get("audio_url") or song.get("storage_uri")
        if not audio_url:
            log.error("No audio URL in song metadata")
            return None
        
        try:
            output_path = Path(self.config.temp_dir) / f"{song['id']}_input.wav"
            storage = get_storage_client()
            
            # Use unified storage client for all URI schemes
            await storage.download(audio_url, output_path)
            
            log.info("Audio downloaded", path=str(output_path), size=output_path.stat().st_size)
            return output_path
            
        except StorageError as e:
            log.error("Storage download failed", error=str(e), url=audio_url)
            return None
        except Exception as e:
            log.exception("Audio download failed", error=str(e))
            return None
    
    async def _run_pipeline(
        self,
        job_id: uuid.UUID,
        audio_path: Path,
        output_path: Path,
        log: structlog.BoundLogger,
    ) -> dict[str, Any]:
        """Run the beatmap generation pipeline."""
        
        # Progress callback that updates the API
        async def progress_callback(stage: str, percent: int):
            # Map pipeline stages to overall job progress (20-90%)
            overall_percent = 20 + int(percent * 0.70)
            await self.api.update_progress(job_id, overall_percent, stage)
        
        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        
        # Update progress for different stages
        await progress_callback("Separating drums...", 0)
        
        result = await loop.run_in_executor(
            None,
            lambda: process_audio_file(
                input_path=str(audio_path),
                output_path=str(output_path),
                isolate_drums=True,
                confidence_threshold=0.7,
                detection_sensitivity=60.0,
                quantization_grid="sixteenth",
            )
        )
        
        await progress_callback("Processing complete", 100)
        return result
    
    async def _upload_results(
        self,
        job_id: uuid.UUID,
        song_id: uuid.UUID,
        beatmap_path: Path,
        result: dict[str, Any],
        log: structlog.BoundLogger,
    ) -> bool:
        """Upload generated beatmap to storage."""
        from .storage_utils import get_storage_client, StorageError
        
        if not beatmap_path.exists():
            log.error("Beatmap file not found", path=str(beatmap_path))
            return False
        
        try:
            storage = get_storage_client()
            
            # Construct storage URI
            storage_backend = self.config.storage_backend
            if storage_backend == "s3":
                bucket = os.getenv("S3_BUCKET", "beatsight-beatmaps")
                uri = f"s3://{bucket}/beatmaps/{song_id}/{job_id}.bsm"
            elif storage_backend == "azure":
                container = os.getenv("AZURE_CONTAINER", "beatmaps")
                uri = f"az://{container}/beatmaps/{song_id}/{job_id}.bsm"
            else:
                # Local storage - just log success
                log.info(
                    "Results ready (local mode)",
                    beatmap_size=beatmap_path.stat().st_size,
                    note_count=result.get("note_count", 0),
                    bpm=result.get("bpm"),
                )
                return True
            
            # Upload beatmap
            await storage.upload(beatmap_path, uri)
            
            log.info(
                "Results uploaded",
                uri=uri,
                beatmap_size=beatmap_path.stat().st_size,
                note_count=result.get("note_count", 0),
                bpm=result.get("bpm"),
            )
            
            return True
            
        except StorageError as e:
            log.error("Storage upload failed", error=str(e))
            return False
        except Exception as e:
            log.exception("Unexpected upload error", error=str(e))
            return False


# =============================================================================
# Main Worker Loop
# =============================================================================
class Worker:
    """Main worker that polls for and processes jobs."""
    
    def __init__(self):
        self.config = WorkerConfig()
        self.log = setup_logging(self.config)
        self.api = APIClient(self.config, self.log)
        self.processor = JobProcessor(self.config, self.api, self.log)
        self._running = True
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.log.info("Received shutdown signal", signal=signum)
        self._running = False
    
    async def run(self):
        """Main worker loop."""
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        self.log.info(
            "Worker starting",
            api_url=self.config.api_url,
            poll_interval=self.config.poll_interval,
        )
        
        try:
            while self._running:
                # Try to claim a job
                job = await self.api.claim_job()
                
                if job:
                    success = await self.processor.process_job(job)
                    
                    if not success:
                        # Release job back to queue for retry
                        job_id = uuid.UUID(job["id"])
                        await self.api.release_job(job_id)
                        self.log.warning("Job released for retry", job_id=str(job_id))
                else:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(self.config.poll_interval)
                    
        except asyncio.CancelledError:
            self.log.info("Worker cancelled")
        finally:
            await self.api.close()
            self.log.info("Worker shutdown complete")


# =============================================================================
# Entry Point
# =============================================================================
def main():
    """Entry point for the worker."""
    worker = Worker()
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
