#!/usr/bin/env python3
"""
Demonstration of batch processing functionality for GOES-VFI.

This example shows how to:
1. Create a batch processing queue
2. Add multiple jobs with different priorities
3. Monitor job progress
4. Handle job completion and failures
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from goesvfi.pipeline.batch_queue import (
    BatchJob,
    BatchProcessor,
    BatchQueue,
    JobPriority,
    JobStatus,
)
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


def mock_process_function(job: BatchJob) -> None:
    """Mock processing function that simulates video processing."""
    LOGGER.info(f"Processing job {job.id}: {job.name}")

    # Get progress callback if provided
    progress_callback = job.settings.get("progress_callback")

    # Simulate processing with progress updates
    total_steps = 10
    for i in range(total_steps):
        # Simulate work
        time.sleep(0.5)

        # Update progress
        progress = (i + 1) / total_steps * 100
        if progress_callback:
            progress_callback(progress)

        LOGGER.info(f"Job {job.id} progress: {progress:.1f}%")

        # Simulate occasional failure
        if job.name == "fail_job" and i == 5:
            raise RuntimeError("Simulated processing failure")

    LOGGER.info(f"Job {job.id} completed successfully")


def demonstrate_batch_processing():
    """Demonstrate batch processing functionality."""
    print("=== GOES-VFI Batch Processing Demo ===\n")

    # Create batch processor
    processor = BatchProcessor()

    # Create queue with mock processing function
    queue = processor.create_queue(process_function=mock_process_function, max_concurrent=2)

    # Connect signal handlers
    def on_job_started(job_id: str):
        print(f"✅ Job started: {job_id}")

    def on_job_progress(job_id: str, progress: float):
        print(f"📊 Job {job_id} progress: {progress:.1f}%")

    def on_job_completed(job_id: str):
        print(f"✅ Job completed: {job_id}")

    def on_job_failed(job_id: str, error: str):
        print(f"❌ Job failed: {job_id} - {error}")

    def on_queue_empty():
        print("\n🎉 All jobs completed!")

    queue.job_started.connect(on_job_started)
    queue.job_progress.connect(on_job_progress)
    queue.job_completed.connect(on_job_completed)
    queue.job_failed.connect(on_job_failed)
    queue.queue_empty.connect(on_queue_empty)

    # Create test jobs
    print("Creating test jobs...\n")

    jobs = []

    # High priority job
    job1 = BatchJob(
        id="job_001",
        name="High Priority Video",
        input_path=Path("/tmp/input1.png"),
        output_path=Path("/tmp/output1.mp4"),
        settings={"target_fps": 30},
        priority=JobPriority.HIGH,
    )
    jobs.append(job1)

    # Normal priority jobs
    for i in range(2, 5):
        job = BatchJob(
            id=f"job_{i:03d}",
            name=f"Normal Priority Video {i}",
            input_path=Path(f"/tmp/input{i}.png"),
            output_path=Path(f"/tmp/output{i}.mp4"),
            settings={"target_fps": 30},
            priority=JobPriority.NORMAL,
        )
        jobs.append(job)

    # Job that will fail
    fail_job = BatchJob(
        id="job_005",
        name="fail_job",
        input_path=Path("/tmp/input_fail.png"),
        output_path=Path("/tmp/output_fail.mp4"),
        settings={"target_fps": 30},
        priority=JobPriority.LOW,
    )
    jobs.append(fail_job)

    # Add jobs to queue
    print(f"Adding {len(jobs)} jobs to queue...\n")
    for job in jobs:
        queue.add_job(job)
        print(f"  Added: {job.name} (Priority: {job.priority.name})")

    # Display queue status
    print("\nQueue Status:")
    print(f"  Pending jobs: {len(queue.get_pending_jobs())}")
    print(f"  Total jobs: {len(queue.get_all_jobs())}")

    # Start processing
    print("\nStarting batch processing with max 2 concurrent jobs...\n")
    queue.start()

    # Wait for completion
    try:
        while queue._running and (queue.get_pending_jobs() or queue._active_jobs):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping queue...")
        queue.stop()

    # Final statistics
    print("\n=== Final Statistics ===")
    all_jobs = queue.get_all_jobs()

    status_counts = {status: 0 for status in JobStatus}
    for job in all_jobs:
        status_counts[job.status] += 1

    print(f"Total jobs: {len(all_jobs)}")
    for status, count in status_counts.items():
        if count > 0:
            print(f"  {status.value}: {count}")

    # Clean up completed jobs
    print("\nCleaning up completed jobs...")
    removed = queue.clear_completed()
    print(f"Removed {removed} jobs from queue")

    print("\n✅ Demo completed!")


def demonstrate_directory_processing():
    """Demonstrate processing all files in a directory."""
    print("\n=== Directory Processing Demo ===\n")

    # Create batch processor
    processor = BatchProcessor()

    # Create queue
    queue = processor.create_queue(process_function=mock_process_function, max_concurrent=3)

    # Create test directory structure
    test_dir = Path("/tmp/goes_vfi_batch_test")
    test_dir.mkdir(exist_ok=True)

    # Create some test files
    print("Creating test files...")
    for i in range(5):
        file_path = test_dir / f"image_{i:03d}.png"
        file_path.touch()  # Create empty file
        print(f"  Created: {file_path}")

    # Add directory to queue
    print(f"\nAdding all PNG files from {test_dir}...")

    output_dir = Path("/tmp/goes_vfi_batch_output")
    output_dir.mkdir(exist_ok=True)

    settings = {"target_fps": 60, "skip_ai": False, "encoder": "libx265"}

    job_ids = processor.add_directory(
        input_dir=test_dir,
        output_dir=output_dir,
        settings=settings,
        pattern="*.png",
        priority=JobPriority.NORMAL,
    )

    print(f"Added {len(job_ids)} jobs to queue")

    # Clean up test files
    print("\nCleaning up test files...")
    for file in test_dir.glob("*.png"):
        file.unlink()
    test_dir.rmdir()

    print("\n✅ Directory processing demo completed!")


if __name__ == "__main__":
    # Run demonstrations
    demonstrate_batch_processing()
    demonstrate_directory_processing()
