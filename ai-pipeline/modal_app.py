"""
BeatSight AI Pipeline - Modal Deployment

This module provides a Modal.com deployment wrapper for the AI pipeline.
Modal handles GPU provisioning, scaling, and container management.

Usage:
    # Deploy to Modal
    modal deploy modal_app.py
    
    # Run locally for testing
    modal run modal_app.py::process_audio
    
Environment Variables Required:
    MODAL_TOKEN_ID: Modal authentication token ID
    MODAL_TOKEN_SECRET: Modal authentication token secret
    BEATSIGHT_API_URL: Backend API URL for job coordination
    
Cost Estimation (A10G GPU):
    - ~$0.60 per job (assuming 30-60 second processing time)
    - Scales to zero when idle
    - Cold start: ~30 seconds
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import modal

# =============================================================================
# Modal App Configuration
# =============================================================================

# Create Modal app
app = modal.App("beatsight-ai-pipeline")

# Docker image with all dependencies
pipeline_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.2-cudnn9-runtime-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "ffmpeg",
        "sox",
        "libsox-dev",
        "libsndfile1",
        "git",
    )
    .pip_install(
        # Core ML
        "torch>=2.0.0",
        "torchaudio>=2.0.0",
        "demucs>=4.0.0",
        
        # Audio processing
        "librosa>=0.10.0",
        "soundfile>=0.12.0",
        "pydub>=0.25.0",
        "audioread>=3.0.0",
        
        # Utilities
        "numpy>=1.24.0",
        "httpx>=0.25.0",
        "structlog>=23.0.0",
        "pydantic>=2.0.0",
        
        # Progress tracking
        "rich>=13.0.0",
    )
    .run_commands(
        # Pre-download Demucs model to bake into image
        "python -c \"import demucs.pretrained; demucs.pretrained.get_model('htdemucs')\"",
    )
)

# Shared volume for model weights (persisted across runs)
models_volume = modal.Volume.from_name("beatsight-models", create_if_missing=True)

# Secrets for API access
api_secrets = modal.Secret.from_name("beatsight-api")


# =============================================================================
# GPU Processing Function
# =============================================================================

@app.function(
    image=pipeline_image,
    gpu="A10G",  # 24GB VRAM, good balance of cost/performance
    timeout=600,  # 10 minute max per job
    retries=1,  # Retry once on failure
    volumes={"/models": models_volume},
    secrets=[api_secrets],
    cpu=4.0,
    memory=16384,  # 16GB RAM
)
async def process_audio(
    job_id: str,
    audio_url: str,
    song_id: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Process an audio file and generate a beatmap.
    
    This function runs on Modal's GPU infrastructure and:
    1. Downloads the audio from the provided URL
    2. Runs source separation (Demucs)
    3. Detects onsets and classifies drum hits
    4. Generates a .bsm beatmap file
    5. Returns the result for upload to storage
    
    Args:
        job_id: Unique job identifier
        audio_url: URL to download the audio file from
        song_id: Song ID for metadata
        options: Optional processing parameters
            - detection_sensitivity: 0-100 (default 50)
            - quantization_grid: "1/4", "1/8", "1/16", "1/32" (default "1/16")
            - use_ml_classifier: bool (default True)
            - tempo_hint: Optional BPM hint
    
    Returns:
        Dictionary with:
            - success: bool
            - beatmap: Base64-encoded .bsm file content
            - stems: Optional dict of stem URLs
            - debug: Optional debug payload
            - error: Error message if failed
    """
    import asyncio
    import base64
    import json
    import tempfile
    
    import httpx
    import structlog
    
    # Local imports for pipeline
    import sys
    sys.path.insert(0, "/root")  # Add modal workspace to path
    
    log = structlog.get_logger().bind(
        job_id=job_id,
        song_id=song_id,
    )
    
    log.info("Starting audio processing on Modal GPU")
    
    # Get API URL for progress updates
    api_url = os.environ.get("BEATSIGHT_API_URL", "https://api.beatsight.app")
    
    async def update_progress(percent: int, message: str):
        """Report progress back to the API."""
        try:
            async with httpx.AsyncClient() as client:
                await client.patch(
                    f"{api_url}/ai-jobs/{job_id}/progress",
                    json={
                        "progress_percent": percent,
                        "progress_message": message,
                    },
                    timeout=5.0,
                )
        except Exception as e:
            log.warning("Progress update failed", error=str(e))
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Download audio
            await update_progress(5, "Downloading audio...")
            audio_path = temp_path / "input_audio"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url, follow_redirects=True, timeout=120.0)
                response.raise_for_status()
                
                # Detect format from content-type or URL
                content_type = response.headers.get("content-type", "")
                if "mp3" in content_type or audio_url.endswith(".mp3"):
                    audio_path = audio_path.with_suffix(".mp3")
                elif "flac" in content_type or audio_url.endswith(".flac"):
                    audio_path = audio_path.with_suffix(".flac")
                else:
                    audio_path = audio_path.with_suffix(".wav")
                
                audio_path.write_bytes(response.content)
            
            log.info("Audio downloaded", size_mb=len(response.content) / 1024 / 1024)
            
            # Step 2: Run pipeline
            await update_progress(15, "Separating drums with Demucs...")
            
            output_path = temp_path / f"{job_id}.bsm"
            debug_path = temp_path / f"{job_id}.debug.json"
            
            # Import and run pipeline
            from pipeline.process import process_audio_file
            
            process_options = options or {}
            
            # Run synchronously in thread pool (pipeline isn't async)
            result = await asyncio.to_thread(
                process_audio_file,
                str(audio_path),
                str(output_path),
                detection_sensitivity=process_options.get("detection_sensitivity", 50),
                quantization_grid=process_options.get("quantization_grid", "1/16"),
                use_ml_classifier=process_options.get("use_ml_classifier", True),
                tempo_hint=process_options.get("tempo_hint"),
                progress_callback=lambda p, m: asyncio.run(update_progress(15 + int(p * 0.75), m)),
                debug_output=str(debug_path),
            )
            
            await update_progress(90, "Packaging results...")
            
            # Read output files
            if not output_path.exists():
                result_payload = {
                    "job_id": job_id,
                    "success": False,
                    "error": "Pipeline did not produce output file",
                }
                await _notify_backend(job_id, result_payload)
                return result_payload
            
            beatmap_content = output_path.read_bytes()
            debug_content = debug_path.read_bytes() if debug_path.exists() else None
            
            await update_progress(95, "Uploading results...")
            
            result_payload = {
                "job_id": job_id,
                "success": True,
                "beatmap": base64.b64encode(beatmap_content).decode("utf-8"),
                "beatmap_size": len(beatmap_content),
                "debug": base64.b64encode(debug_content).decode("utf-8") if debug_content else None,
                "processing_time_seconds": result.get("processing_time", 0),
            }
            
            # Notify backend of completion
            await _notify_backend(job_id, result_payload)
            
            await update_progress(100, "Complete!")
            return result_payload
            
    except httpx.HTTPError as e:
        log.exception("Failed to download audio", error=str(e))
        error_payload = {
            "job_id": job_id,
            "success": False,
            "error": f"Failed to download audio: {e}",
        }
        await _notify_backend(job_id, error_payload)
        return error_payload
    except Exception as e:
        log.exception("Pipeline failed", error=str(e))
        error_payload = {
            "job_id": job_id,
            "success": False,
            "error": f"Processing failed: {e}",
        }
        await _notify_backend(job_id, error_payload)
        return error_payload


async def _notify_backend(job_id: str, result: dict) -> None:
    """Send job result to backend webhook."""
    import httpx
    import structlog
    
    log = structlog.get_logger().bind(job_id=job_id)
    api_url = os.environ.get("BEATSIGHT_API_URL", "https://api.beatsight.app")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/ai-jobs/modal-webhook",
                json=result,
                timeout=30.0,
            )
            response.raise_for_status()
            log.info("Backend notified of job completion", status_code=response.status_code)
    except Exception as e:
        log.error("Failed to notify backend", error=str(e))
        # Don't raise - the result is still valid even if notification fails


# =============================================================================
# Job Orchestration (Long-running worker mode)
# =============================================================================

@app.function(
    image=pipeline_image,
    timeout=3600,  # 1 hour max
    secrets=[api_secrets],
    cpu=1.0,
    memory=1024,
)
async def poll_and_process():
    """
    Long-running function that polls for jobs and dispatches to GPU workers.
    
    This is an alternative to webhook-based triggering. It runs on cheap CPU
    and spawns GPU workers only when jobs are available.
    """
    import asyncio
    import httpx
    import structlog
    
    log = structlog.get_logger()
    api_url = os.environ.get("BEATSIGHT_API_URL", "https://api.beatsight.app")
    worker_id = str(uuid.uuid4())
    
    log.info("Starting job polling", worker_id=worker_id)
    
    async with httpx.AsyncClient(base_url=api_url) as client:
        while True:
            try:
                # Claim a job
                response = await client.post(
                    "/ai-jobs/claim",
                    params={"worker_id": worker_id},
                    timeout=10.0,
                )
                
                if response.status_code == 200 and response.json():
                    job = response.json()
                    log.info("Claimed job", job_id=job["id"])
                    
                    # Get song metadata
                    song_response = await client.get(f"/songs/{job['song_id']}")
                    if song_response.status_code != 200:
                        log.error("Failed to get song metadata")
                        continue
                    
                    song = song_response.json()
                    audio_url = song.get("audio_url") or song.get("storage_uri")
                    
                    if not audio_url:
                        log.error("No audio URL for song")
                        continue
                    
                    # Dispatch to GPU worker
                    try:
                        result = await process_audio.remote.aio(
                            job_id=job["id"],
                            audio_url=audio_url,
                            song_id=job["song_id"],
                            options=job.get("parameters"),
                        )
                        
                        if result["success"]:
                            # Result is automatically sent to backend via webhook
                            log.info("Job completed successfully", job_id=job["id"])
                        else:
                            log.error("Job failed", job_id=job["id"], error=result.get("error"))
                            
                    except Exception as e:
                        log.exception("GPU worker failed", job_id=job["id"], error=str(e))
                        await client.post(f"/ai-jobs/{job['id']}/release")
                else:
                    # No jobs available, wait before polling again
                    await asyncio.sleep(5)
                    
            except httpx.HTTPError as e:
                log.warning("API request failed", error=str(e))
                await asyncio.sleep(10)
            except Exception as e:
                log.exception("Polling error", error=str(e))
                await asyncio.sleep(10)# =============================================================================
# Web Endpoint (Webhook-based triggering)
# =============================================================================

@app.function(
    image=pipeline_image,
    secrets=[api_secrets],
    cpu=0.25,
    memory=256,
)
@modal.web_endpoint(method="POST")
async def trigger_job(job_data: dict) -> dict:
    """
    HTTP endpoint to trigger a job.
    
    Called by the backend when a new job is enqueued.
    This is more efficient than polling as it only spins up
    GPU resources when needed.
    
    Request body:
    {
        "job_id": "...",
        "song_id": "...",
        "audio_url": "...",
        "options": {...}
    }
    
    Returns:
    {
        "accepted": true,
        "call_id": "..."  // Modal function call ID for tracking
    }
    """
    import json
    
    # Validate request
    required = ["job_id", "audio_url", "song_id"]
    for field in required:
        if field not in job_data:
            return {"accepted": False, "error": f"Missing required field: {field}"}
    
    # Spawn GPU worker asynchronously
    call = process_audio.spawn(
        job_id=job_data["job_id"],
        audio_url=job_data["audio_url"],
        song_id=job_data["song_id"],
        options=job_data.get("options"),
    )
    
    return {
        "accepted": True,
        "call_id": call.object_id,
    }


# =============================================================================
# CLI Entry Points
# =============================================================================

@app.local_entrypoint()
def main():
    """Local CLI entry point for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: modal run modal_app.py [poll|test]")
        print("  poll  - Start job polling loop")
        print("  test  - Process a test audio file")
        return
    
    command = sys.argv[1]
    
    if command == "poll":
        poll_and_process.remote()
    elif command == "test":
        if len(sys.argv) < 3:
            print("Usage: modal run modal_app.py test <audio_url>")
            return
        
        audio_url = sys.argv[2]
        result = process_audio.remote(
            job_id=str(uuid.uuid4()),
            audio_url=audio_url,
            song_id=str(uuid.uuid4()),
        )
        
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {command}")


# =============================================================================
# Health Check
# =============================================================================

@app.function(
    image=modal.Image.debian_slim(),
    cpu=0.1,
    memory=128,
)
@modal.web_endpoint(method="GET")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "beatsight-ai-pipeline",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
