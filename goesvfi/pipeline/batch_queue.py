"""
Batch processing queue for GOES-VFI.

This module provides a queue-based system for processing multiple video
interpolation jobs in sequence with configurable priorities and resource
management.
"""

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from queue import PriorityQueue
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class JobStatus(Enum):
    """Status of a batch job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Priority levels for batch jobs."""

    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


@dataclass
class BatchJob:
    """Represents a single batch processing job."""

    id: str
    name: str
    input_path: Path
    output_path: Path
    settings: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: float = 0.0

    def __lt__(self, other: "BatchJob") -> bool:
        """Compare jobs by priority for queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "settings": self.settings,
            "priority": self.priority.name,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "error_message": self.error_message,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls: type["BatchJob"], data: Dict[str, Any]) -> "BatchJob":
        """Create job from dictionary."""
        job = cls(
            id=data["id"],
            name=data["name"],
            input_path=Path(data["input_path"]),
            output_path=Path(data["output_path"]),
            settings=data["settings"],
            priority=JobPriority[data["priority"]],
            status=JobStatus[data["status"]],
            created_at=datetime.fromisoformat(data["created_at"]),
            error_message=data.get("error_message"),
            progress=data.get("progress", 0.0),
        )

        if data.get("started_at"):
            job.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            job.completed_at = datetime.fromisoformat(data["completed_at"])

        return job


class BatchQueue(QObject):
    """Manages a queue of batch processing jobs."""

    # Signals
    job_added = pyqtSignal(str)  # job_id
    job_started = pyqtSignal(str)  # job_id
    job_progress = pyqtSignal(str, float)  # job_id, progress
    job_completed = pyqtSignal(str)  # job_id
    job_failed = pyqtSignal(str, str)  # job_id, error
    job_cancelled = pyqtSignal(str)  # job_id
    queue_empty = pyqtSignal()

    def __init__(
        self,
        process_function: Callable[[BatchJob], None],
        max_concurrent_jobs: int = 1,
        resource_manager: Optional[Any] = None,
    ) -> None:
        """
        Initialize batch queue.

        Args:
            process_function: Function to process each job
            max_concurrent_jobs: Maximum concurrent jobs (default 1)
            resource_manager: Optional resource manager for limits
        """
        super().__init__()

        self.process_function = process_function
        self.max_concurrent_jobs = max_concurrent_jobs
        self.resource_manager = resource_manager

        self._queue: PriorityQueue[BatchJob] = PriorityQueue()
        self._jobs: Dict[str, BatchJob] = {}
        self._active_jobs: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Load persisted queue
        self._load_queue()

    def start(self) -> None:
        """Start processing queue."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        LOGGER.info("Batch queue started")

    def stop(self) -> None:
        """Stop processing queue."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        LOGGER.info("Batch queue stopped")

    def add_job(self, job: BatchJob) -> None:
        """Add job to queue."""
        with self._lock:
            self._jobs[job.id] = job
            self._queue.put(job)
            # Don't call _save_queue here as we're already holding the lock
            # Save the queue data directly
            data = {"jobs": [j.to_dict() for j in self._jobs.values()]}

        # Save outside the lock to avoid deadlock
        queue_file = Path.home() / ".config" / "goesvfi" / "batch_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOGGER.error("Failed to save queue: %s", e)

        self.job_added.emit(job.id)
        LOGGER.info("Job %s added to queue: %s", job.id, job.name)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        with self._lock:
            if job_id not in self._jobs:
                return False

            job = self._jobs[job_id]

            # Can only cancel pending jobs
            if job.status != JobStatus.PENDING:
                return False

            job.status = JobStatus.CANCELLED
            # Don't call _save_queue here as we're already holding the lock
            data = {"jobs": [j.to_dict() for j in self._jobs.values()]}

        # Save outside the lock to avoid deadlock
        queue_file = Path.home() / ".config" / "goesvfi" / "batch_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOGGER.error("Failed to save queue: %s", e)

        self.job_cancelled.emit(job_id)
        LOGGER.info("Job %s cancelled", job_id)
        return True

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> List[BatchJob]:
        """Get all jobs."""
        with self._lock:
            return list(self._jobs.values())

    def get_pending_jobs(self) -> List[BatchJob]:
        """Get pending jobs sorted by priority."""
        with self._lock:
            pending = [j for j in self._jobs.values() if j.status == JobStatus.PENDING]
            return sorted(pending)

    def clear_completed(self) -> int:
        """Clear completed and cancelled jobs."""
        with self._lock:
            to_remove = [
                job_id for job_id, job in self._jobs.items() if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)
            ]

            for job_id in to_remove:
                del self._jobs[job_id]

            # Don't call _save_queue here as we're already holding the lock
            data = {"jobs": [j.to_dict() for j in self._jobs.values()]}

        # Save outside the lock to avoid deadlock
        queue_file = Path.home() / ".config" / "goesvfi" / "batch_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOGGER.error("Failed to save queue: %s", e)

        LOGGER.info("Cleared %s completed/cancelled jobs", len(to_remove))
        return len(to_remove)

    def _process_queue(self) -> None:
        """Worker thread to process queue."""
        while self._running:
            # Check if we can start another job
            with self._lock:
                if len(self._active_jobs) >= self.max_concurrent_jobs:
                    time.sleep(0.5)
                    continue

            # Get next job
            try:
                job = self._queue.get(timeout=0.5)
            except Exception:
                continue

            # Skip if cancelled
            if job.status == JobStatus.CANCELLED:
                continue

            # Start processing
            thread = threading.Thread(target=self._process_job, args=(job,), daemon=True)

            with self._lock:
                self._active_jobs[job.id] = thread

            thread.start()

        # Wait for active jobs to complete
        for thread in self._active_jobs.values():
            thread.join(timeout=5.0)

    def _process_job(self, job: BatchJob) -> None:
        """Process a single job."""
        try:
            # Update status
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            self._save_queue()
            self.job_started.emit(job.id)

            LOGGER.info("Processing job %s: %s", job.id, job.name)

            # Set up progress callback
            def progress_callback(progress: float) -> None:
                job.progress = progress
                self.job_progress.emit(job.id, progress)

            # Inject progress callback into settings
            job.settings["progress_callback"] = progress_callback

            # Apply resource limits if configured
            if self.resource_manager:
                with self.resource_manager.monitor_resources():
                    self.process_function(job)
            else:
                self.process_function(job)

            # Mark completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress = 100.0
            self._save_queue()
            self.job_completed.emit(job.id)

            LOGGER.info("Job %s completed successfully", job.id)

        except Exception as e:
            # Mark failed
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error_message = str(e)
            self._save_queue()
            self.job_failed.emit(job.id, str(e))

            LOGGER.error("Job %s failed: %s", job.id, e, exc_info=True)

        finally:
            # Remove from active jobs
            with self._lock:
                self._active_jobs.pop(job.id, None)

            # Check if queue is empty
            if self._queue.empty() and not self._active_jobs:
                self.queue_empty.emit()

    def _save_queue(self) -> None:
        """Save queue state to disk."""
        queue_file = Path.home() / ".config" / "goesvfi" / "batch_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            data = {"jobs": [job.to_dict() for job in self._jobs.values()]}

        try:
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOGGER.error("Failed to save queue: %s", e)

    def _load_queue(self) -> None:
        """Load queue state from disk."""
        queue_file = Path.home() / ".config" / "goesvfi" / "batch_queue.json"

        if not queue_file.exists():
            return

        try:
            with open(queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for job_data in data.get("jobs", []):
                try:
                    job = BatchJob.from_dict(job_data)

                    # Reset running jobs to pending
                    if job.status == JobStatus.RUNNING:
                        job.status = JobStatus.PENDING
                        job.started_at = None
                        job.progress = 0.0

                    self._jobs[job.id] = job

                    # Add pending jobs back to queue
                    if job.status == JobStatus.PENDING:
                        self._queue.put(job)

                except Exception as e:
                    LOGGER.error("Failed to load job: %s", e)

            LOGGER.info("Loaded %s jobs from queue", len(self._jobs))

        except Exception as e:
            LOGGER.error("Failed to load queue: %s", e)


class BatchProcessor:
    """High-level batch processing manager."""

    def __init__(self, resource_manager: Optional[Any] = None) -> None:
        """Initialize batch processor."""
        self.resource_manager = resource_manager
        self.queue: Optional[BatchQueue] = None

    def create_queue(self, process_function: Callable[[BatchJob], None], max_concurrent: int = 1) -> BatchQueue:
        """Create and return a batch queue."""
        self.queue = BatchQueue(
            process_function=process_function,
            max_concurrent_jobs=max_concurrent,
            resource_manager=self.resource_manager,
        )
        return self.queue

    def create_job_from_paths(
        self,
        input_paths: List[Path],
        output_dir: Path,
        settings: Dict[str, Any],
        job_name_prefix: str = "Batch",
        priority: JobPriority = JobPriority.NORMAL,
    ) -> List[BatchJob]:
        """Create batch jobs from a list of input paths."""
        jobs = []

        for i, input_path in enumerate(input_paths):
            # Generate unique job ID
            job_id = f"{int(time.time() * 1000)}_{i}"

            # Create output path
            output_name = f"{input_path.stem}_processed{input_path.suffix}"
            output_path = output_dir / output_name

            # Create job
            job = BatchJob(
                id=job_id,
                name=f"{job_name_prefix} {i + 1}/{len(input_paths)}: {input_path.name}",
                input_path=input_path,
                output_path=output_path,
                settings=settings.copy(),
                priority=priority,
            )

            jobs.append(job)

        return jobs

    def add_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        settings: Dict[str, Any],
        pattern: str = "*.png",
        recursive: bool = False,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> List[str]:
        """Add all matching files from a directory as batch jobs."""
        if not self.queue:
            raise RuntimeError("Queue not initialized")

        # Find matching files
        if recursive:
            input_paths = list(input_dir.rglob(pattern))
        else:
            input_paths = list(input_dir.glob(pattern))

        if not input_paths:
            LOGGER.warning("No files matching '%s' found in %s", pattern, input_dir)
            return []

        # Create jobs
        jobs = self.create_job_from_paths(
            input_paths=input_paths,
            output_dir=output_dir,
            settings=settings,
            job_name_prefix=f"Batch {input_dir.name}",
            priority=priority,
        )

        # Add to queue
        job_ids = []
        for job in jobs:
            self.queue.add_job(job)
            job_ids.append(job.id)

        LOGGER.info("Added %s jobs from %s", len(jobs), input_dir)
        return job_ids
