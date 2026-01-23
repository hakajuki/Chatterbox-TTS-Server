"""
Job Queue System for TTS Generation
Provides asynchronous job processing with status tracking and result retrieval.
"""
import asyncio
import logging
import uuid
import time
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job execution status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TTSJob:
    """Represents a TTS generation job"""
    job_id: str
    status: JobStatus
    created_at: float
    params: Dict[str, Any]
    
    # Progress tracking
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: int = 0  # 0-100
    current_chunk: int = 0
    total_chunks: int = 1
    
    # Results
    output_path: Optional[Path] = None
    output_format: Optional[str] = None
    error: Optional[str] = None
    
    # Metadata
    duration_sec: Optional[float] = None
    file_size_bytes: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for API responses"""
        result = {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "progress": self.progress,
        }
        
        if self.started_at:
            result["started_at"] = self.started_at
            result["elapsed_sec"] = time.time() - self.started_at
        
        if self.completed_at:
            result["completed_at"] = self.completed_at
            result["duration_sec"] = self.duration_sec or (self.completed_at - self.started_at)
        
        if self.total_chunks > 1:
            result["current_chunk"] = self.current_chunk
            result["total_chunks"] = self.total_chunks
        
        if self.error:
            result["error"] = self.error
        
        if self.status == JobStatus.COMPLETED and self.output_path:
            result["output_available"] = True
            result["output_format"] = self.output_format
            result["file_size_bytes"] = self.file_size_bytes
        
        return result


class TTSJobQueue:
    """
    Manages TTS job queue with background worker.
    Provides job submission, status tracking, and result retrieval.
    """
    
    def __init__(self, max_retries: int = 0, job_ttl_hours: int = 24):
        self.jobs: Dict[str, TTSJob] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self.max_retries = max_retries
        self.job_ttl_hours = job_ttl_hours
        self.cleanup_task: Optional[asyncio.Task] = None
        self._processing_callback: Optional[Callable] = None
        
        logger.info(f"TTSJobQueue initialized (TTL: {job_ttl_hours}h)")
    
    def set_processing_callback(self, callback: Callable):
        """Set the async callback function that processes TTS jobs"""
        self._processing_callback = callback
        logger.info("Job processing callback registered")
    
    async def start(self):
        """Start background worker and cleanup tasks"""
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("Job queue worker started")
        
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_worker())
            logger.info("Job cleanup worker started")
    
    async def stop(self):
        """Stop background workers gracefully"""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Job queue worker stopped")
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Job cleanup worker stopped")
    
    def submit_job(self, params: Dict[str, Any]) -> str:
        """
        Submit a new TTS job to the queue.
        Returns the job_id.
        """
        job_id = str(uuid.uuid4())
        
        # Estimate total chunks for progress tracking
        total_chunks = 1
        if params.get("split_text") and params.get("text"):
            text_len = len(params["text"])
            chunk_size = params.get("chunk_size", 120)
            if text_len > chunk_size * 1.5:
                total_chunks = max(1, text_len // chunk_size)
        
        job = TTSJob(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=time.time(),
            params=params,
            total_chunks=total_chunks
        )
        
        self.jobs[job_id] = job
        self.queue.put_nowait(job_id)
        
        logger.info(f"Job {job_id} queued (queue size: {self.queue.qsize()})")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[TTSJob]:
        """Retrieve job by ID"""
        return self.jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running job"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
    
    async def _worker(self):
        """Background worker that processes jobs from the queue"""
        logger.info("Job worker started and waiting for jobs...")
        
        while True:
            try:
                # Wait for next job
                job_id = await self.queue.get()
                job = self.jobs.get(job_id)
                
                if not job:
                    logger.warning(f"Job {job_id} not found in job store")
                    continue
                
                if job.status == JobStatus.CANCELLED:
                    logger.info(f"Skipping cancelled job {job_id}")
                    continue
                
                # Process the job
                job.status = JobStatus.RUNNING
                job.started_at = time.time()
                logger.info(f"Processing job {job_id}...")
                
                try:
                    if self._processing_callback is None:
                        raise RuntimeError("No processing callback registered")
                    
                    # Call the registered TTS processing function
                    result = await self._processing_callback(job)
                    
                    if job.status != JobStatus.CANCELLED:
                        job.status = JobStatus.COMPLETED
                        job.completed_at = time.time()
                        job.duration_sec = job.completed_at - job.started_at
                        job.progress = 100
                        
                        # Store result metadata
                        if result and "output_path" in result:
                            job.output_path = result["output_path"]
                            job.output_format = result.get("output_format")
                            if job.output_path and job.output_path.exists():
                                job.file_size_bytes = job.output_path.stat().st_size
                        
                        logger.info(f"Job {job_id} completed in {job.duration_sec:.2f}s")
                
                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.completed_at = time.time()
                    job.error = str(e)
                    logger.error(f"Job {job_id} failed: {e}", exc_info=True)
                
                finally:
                    self.queue.task_done()
            
            except asyncio.CancelledError:
                logger.info("Job worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in job worker: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _cleanup_worker(self):
        """Periodically clean up old completed/failed jobs"""
        logger.info("Cleanup worker started")
        
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                cutoff_time = time.time() - (self.job_ttl_hours * 3600)
                jobs_to_remove = []
                
                for job_id, job in self.jobs.items():
                    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                        if job.completed_at and job.completed_at < cutoff_time:
                            jobs_to_remove.append(job_id)
                            
                            # Clean up output file
                            if job.output_path and job.output_path.exists():
                                try:
                                    job.output_path.unlink()
                                    logger.debug(f"Removed output file: {job.output_path}")
                                except Exception as e:
                                    logger.warning(f"Failed to remove output file {job.output_path}: {e}")
                
                for job_id in jobs_to_remove:
                    del self.jobs[job_id]
                
                if jobs_to_remove:
                    logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
            
            except asyncio.CancelledError:
                logger.info("Cleanup worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}", exc_info=True)


# Global job queue instance
job_queue: Optional[TTSJobQueue] = None


def get_job_queue() -> TTSJobQueue:
    """Get or create the global job queue instance"""
    global job_queue
    if job_queue is None:
        job_queue = TTSJobQueue()
    return job_queue
