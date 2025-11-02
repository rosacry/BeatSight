"""
FastAPI Server for BeatSight AI Processing
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import shutil
from pathlib import Path
import asyncio

from .process import process_audio_file

app = FastAPI(title="BeatSight AI API", version="1.0.0")

# Storage for processing jobs
JOBS_DIR = Path("./jobs")
JOBS_DIR.mkdir(exist_ok=True)

# In-memory job status (would use Redis/database in production)
jobs_status: Dict[str, Dict[str, Any]] = {}


class ProcessingStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[float] = None
    error: Optional[str] = None
    result_path: Optional[str] = None


@app.get("/")
async def root():
    return {
        "name": "BeatSight AI API",
        "version": "1.0.0",
        "endpoints": [
            "/api/process",
            "/api/process/{job_id}",
            "/api/process/{job_id}/result",
        ]
    }


@app.post("/api/process")
async def process_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    confidence: float = 0.7,
    isolate_drums: bool = True,
):
    """
    Submit an audio file for processing.
    
    Returns a job ID that can be used to check status and download results.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create job directory
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file
    input_path = job_dir / file.filename
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Initialize job status
    jobs_status[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "input_file": str(input_path),
    }
    
    # Schedule background processing
    background_tasks.add_task(
        process_job,
        job_id,
        str(input_path),
        confidence,
        isolate_drums,
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Audio file uploaded successfully. Processing will begin shortly.",
    }


async def process_job(
    job_id: str,
    input_path: str,
    confidence: float,
    isolate_drums: bool,
):
    """
    Background task to process audio file.
    """
    try:
        # Update status
        jobs_status[job_id]["status"] = "processing"
        jobs_status[job_id]["progress"] = 0.1
        
        # Output path
        job_dir = JOBS_DIR / job_id
        output_path = job_dir / "beatmap.bsm"
        
        # Process audio
        result = process_audio_file(
            input_path,
            str(output_path),
            isolate_drums=isolate_drums,
            confidence_threshold=confidence,
        )
        
        # Update status
        jobs_status[job_id]["status"] = "completed"
        jobs_status[job_id]["progress"] = 1.0
        jobs_status[job_id]["result_path"] = str(output_path)
        jobs_status[job_id]["result"] = result
        
    except Exception as e:
        jobs_status[job_id]["status"] = "failed"
        jobs_status[job_id]["error"] = str(e)
        print(f"Error processing job {job_id}: {e}")
        import traceback
        traceback.print_exc()


@app.get("/api/process/{job_id}")
async def get_job_status(job_id: str):
    """
    Check the status of a processing job.
    """
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs_status[job_id]


@app.get("/api/process/{job_id}/result")
async def download_result(job_id: str):
    """
    Download the resulting beatmap file.
    """
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = jobs_status[job_id]
    
    if status["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {status['status']}"
        )
    
    result_path = status.get("result_path")
    if not result_path or not Path(result_path).exists():
        raise HTTPException(status_code=500, detail="Result file not found")
    
    return FileResponse(
        result_path,
        media_type="application/json",
        filename=f"beatmap_{job_id}.bsm",
    )


@app.delete("/api/process/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a processing job and its files.
    """
    if job_id not in jobs_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Delete job directory
    job_dir = JOBS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    # Remove from status
    del jobs_status[job_id]
    
    return {"message": "Job deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
