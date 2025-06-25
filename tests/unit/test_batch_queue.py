"""
Unit tests for batch processing queue functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from goesvfi.pipeline.batch_queue import (
    BatchJob,
    BatchProcessor,
    BatchQueue,
    JobPriority,
    JobStatus,
)


class TestBatchJob:
    """Test BatchJob class."""

    def test_job_creation(self):
        """Test creating a batch job."""
        job = BatchJob(
            id="test_001",
            name="Test Job",
            input_path=Path("/tmp/input.png"),
            output_path=Path("/tmp/output.mp4"),
            settings={"fps": 30},
        )

        assert job.id == "test_001"
        assert job.name == "Test Job"
        assert job.priority == JobPriority.NORMAL
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0
        assert job.error_message is None

    def test_job_comparison(self):
        """Test job priority comparison."""
        high_job = BatchJob(
            id="high",
            name="High Priority",
            input_path=Path("/tmp/high.png"),
            output_path=Path("/tmp/high.mp4"),
            settings={},
            priority=JobPriority.HIGH,
        )

        normal_job = BatchJob(
            id="normal",
            name="Normal Priority",
            input_path=Path("/tmp/normal.png"),
            output_path=Path("/tmp/normal.mp4"),
            settings={},
            priority=JobPriority.NORMAL,
        )

        # High priority should come before normal
        assert high_job < normal_job
        assert not (normal_job < high_job)

    def test_job_serialization(self):
        """Test job to/from dict conversion."""
        original = BatchJob(
            id="test_002",
            name="Serialization Test",
            input_path=Path("/tmp/test.png"),
            output_path=Path("/tmp/test.mp4"),
            settings={"key": "value"},
            priority=JobPriority.HIGH,
        )

        # Convert to dict and back
        job_dict = original.to_dict()
        restored = BatchJob.from_dict(job_dict)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.input_path == original.input_path
        assert restored.output_path == original.output_path
        assert restored.settings == original.settings
        assert restored.priority == original.priority


class TestBatchQueue:
    """Test BatchQueue class."""

    @pytest.fixture
    def mock_process_function(self):
        """Create a mock process function."""
        return MagicMock()

    @pytest.fixture
    def batch_queue(self, mock_process_function):
        """Create a batch queue for testing."""
        with patch("goesvfi.pipeline.batch_queue.Path.home") as mock_home:
            mock_home.return_value = Path("/tmp")
            # Also patch file operations to avoid actual file I/O
            with patch("goesvfi.pipeline.batch_queue.open", create=True):
                with patch("goesvfi.pipeline.batch_queue.json.load", return_value={"jobs": []}):
                    with patch("goesvfi.pipeline.batch_queue.json.dump"):
                        queue = BatchQueue(
                            process_function=mock_process_function,
                            max_concurrent_jobs=1,
                        )
                        yield queue
                        # Clean up
                        if queue._running:
                            queue.stop()

    def test_queue_creation(self, batch_queue):
        """Test creating a batch queue."""
        assert batch_queue.max_concurrent_jobs == 1
        assert not batch_queue._running
        assert len(batch_queue._jobs) == 0

    def test_add_job(self, batch_queue):
        """Test adding a job to queue."""
        job = BatchJob(
            id="test_add",
            name="Add Test",
            input_path=Path("/tmp/add.png"),
            output_path=Path("/tmp/add.mp4"),
            settings={},
        )

        # Connect signal spy
        signal_received = []
        batch_queue.job_added.connect(lambda job_id: signal_received.append(job_id))

        # Add job
        batch_queue.add_job(job)

        # Check job was added
        assert job.id in batch_queue._jobs
        assert batch_queue.get_job(job.id) == job
        assert job.id in signal_received

    def test_cancel_job(self, batch_queue):
        """Test cancelling a job."""
        job = BatchJob(
            id="test_cancel",
            name="Cancel Test",
            input_path=Path("/tmp/cancel.png"),
            output_path=Path("/tmp/cancel.mp4"),
            settings={},
        )

        batch_queue.add_job(job)

        # Connect signal spy
        signal_received = []
        batch_queue.job_cancelled.connect(lambda job_id: signal_received.append(job_id))

        # Cancel job
        result = batch_queue.cancel_job(job.id)

        assert result is True
        assert batch_queue.get_job(job.id).status == JobStatus.CANCELLED
        assert job.id in signal_received

        # Can't cancel already cancelled job
        assert batch_queue.cancel_job(job.id) is False

    def test_get_pending_jobs(self, batch_queue):
        """Test getting pending jobs sorted by priority."""
        # Add jobs with different priorities
        low_job = BatchJob(
            id="low",
            name="Low Priority",
            input_path=Path("/tmp/low.png"),
            output_path=Path("/tmp/low.mp4"),
            settings={},
            priority=JobPriority.LOW,
        )

        high_job = BatchJob(
            id="high",
            name="High Priority",
            input_path=Path("/tmp/high.png"),
            output_path=Path("/tmp/high.mp4"),
            settings={},
            priority=JobPriority.HIGH,
        )

        batch_queue.add_job(low_job)
        batch_queue.add_job(high_job)

        # Get pending jobs
        pending = batch_queue.get_pending_jobs()

        assert len(pending) == 2
        assert pending[0].id == "high"  # High priority first
        assert pending[1].id == "low"

    def test_clear_completed(self, batch_queue):
        """Test clearing completed jobs."""
        # Add jobs with different statuses
        completed_job = BatchJob(
            id="completed",
            name="Completed",
            input_path=Path("/tmp/completed.png"),
            output_path=Path("/tmp/completed.mp4"),
            settings={},
        )
        completed_job.status = JobStatus.COMPLETED

        pending_job = BatchJob(
            id="pending",
            name="Pending",
            input_path=Path("/tmp/pending.png"),
            output_path=Path("/tmp/pending.mp4"),
            settings={},
        )

        batch_queue.add_job(completed_job)
        batch_queue.add_job(pending_job)

        # Clear completed
        removed = batch_queue.clear_completed()

        assert removed == 1
        assert batch_queue.get_job("completed") is None
        assert batch_queue.get_job("pending") is not None

    @patch("goesvfi.pipeline.batch_queue.json.dump")
    @patch("goesvfi.pipeline.batch_queue.open", create=True)
    def test_save_queue(self, mock_open, mock_json_dump, batch_queue):
        """Test saving queue state."""
        job = BatchJob(
            id="save_test",
            name="Save Test",
            input_path=Path("/tmp/save.png"),
            output_path=Path("/tmp/save.mp4"),
            settings={},
        )

        batch_queue.add_job(job)

        # Force save
        batch_queue._save_queue()

        # Check save was called
        mock_open.assert_called()
        mock_json_dump.assert_called()


class TestBatchProcessor:
    """Test BatchProcessor class."""

    def test_create_queue(self):
        """Test creating a queue through processor."""
        processor = BatchProcessor()
        mock_func = MagicMock()

        queue = processor.create_queue(process_function=mock_func, max_concurrent=2)

        assert isinstance(queue, BatchQueue)
        assert queue.max_concurrent_jobs == 2
        assert processor.queue == queue

    def test_create_jobs_from_paths(self):
        """Test creating jobs from file paths."""
        processor = BatchProcessor()

        input_paths = [
            Path("/tmp/image1.png"),
            Path("/tmp/image2.png"),
            Path("/tmp/image3.png"),
        ]

        output_dir = Path("/tmp/output")
        settings = {"fps": 30}

        jobs = processor.create_job_from_paths(
            input_paths=input_paths,
            output_dir=output_dir,
            settings=settings,
            job_name_prefix="Test",
            priority=JobPriority.HIGH,
        )

        assert len(jobs) == 3
        assert all(isinstance(job, BatchJob) for job in jobs)
        assert all(job.priority == JobPriority.HIGH for job in jobs)
        assert jobs[0].name == "Test 1/3: image1.png"
        assert jobs[0].output_path == output_dir / "image1_processed.png"

    @patch("goesvfi.pipeline.batch_queue.Path.glob")
    def test_add_directory(self, mock_glob):
        """Test adding all files from a directory."""
        processor = BatchProcessor()
        processor.queue = MagicMock()

        # Mock finding files
        mock_glob.return_value = [
            Path("/tmp/input/file1.png"),
            Path("/tmp/input/file2.png"),
        ]

        input_dir = Path("/tmp/input")
        output_dir = Path("/tmp/output")
        settings = {"fps": 60}

        with patch.object(Path, "glob", mock_glob):
            job_ids = processor.add_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                settings=settings,
                pattern="*.png",
                priority=JobPriority.NORMAL,
            )

        assert len(job_ids) == 2
        assert processor.queue.add_job.call_count == 2
