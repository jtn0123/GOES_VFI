"""
Unit tests for batch processing queue functionality (Optimized v2).

Optimizations:
- Shared fixtures for common test objects
- Mocked file I/O operations for speed
- Parameterized tests for similar scenarios
- Consolidated related test cases
- Mock signal emission to avoid Qt dependencies
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from goesvfi.pipeline.batch_queue import (
    BatchJob,
    BatchProcessor,
    BatchQueue,
    JobPriority,
    JobStatus,
)


@pytest.fixture()
def sample_job_data() -> dict[str, Any]:
    """Sample data for creating test jobs.

    Returns:
        dict[str, Any]: Sample job data for testing.
    """
    return {
        "basic": {
            "id": "test_001",
            "name": "Test Job",
            "input_path": Path("/tmp/input.png"),  # noqa: S108
            "output_path": Path("/tmp/output.mp4"),  # noqa: S108
            "settings": {"fps": 30},
        },
        "high_priority": {
            "id": "high_priority_job",
            "name": "High Priority Job",
            "input_path": Path("/tmp/high.png"),  # noqa: S108
            "output_path": Path("/tmp/high.mp4"),  # noqa: S108
            "settings": {"fps": 60},
            "priority": JobPriority.HIGH,
        },
        "serialization_test": {
            "id": "test_002",
            "name": "Serialization Test",
            "input_path": Path("/tmp/test.png"),  # noqa: S108
            "output_path": Path("/tmp/test.mp4"),  # noqa: S108
            "settings": {"key": "value"},
            "priority": JobPriority.HIGH,
        },
    }


@pytest.fixture()
def mock_file_operations() -> Any:
    """Mock file operations to avoid actual file I/O.

    Yields:
        Any: Mock context for file operations.
    """
    with patch("goesvfi.pipeline.batch_queue.Path.home") as mock_home:
        mock_home.return_value = Path("/tmp")  # noqa: S108
        with (
            patch("goesvfi.pipeline.batch_queue.open", create=True),
            patch("goesvfi.pipeline.batch_queue.json.load", return_value={"jobs": []}),
            patch("goesvfi.pipeline.batch_queue.json.dump"),
        ):
            yield


@pytest.fixture()
def mock_process_function() -> Any:
    """Create a mock process function.

    Returns:
        Any: Mock process function.
    """
    return MagicMock()


@pytest.fixture()
def batch_queue(mock_process_function: Any, mock_file_operations: Any) -> Any:  # noqa: ARG001
    """Create a batch queue for testing.

    Yields:
        BatchQueue: Test batch queue instance.
    """
    queue = BatchQueue(
        process_function=mock_process_function,
        max_concurrent_jobs=2,  # Increased for better testing
    )
    yield queue
    # Clean up
    if queue._running:  # noqa: SLF001
        queue.stop()


class TestBatchJob:
    """Test BatchJob class with shared fixtures."""

    def test_job_creation_basic(self, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test creating a basic batch job."""
        job_data = sample_job_data["basic"]
        job = BatchJob(**job_data)

        assert job.id == job_data["id"]
        assert job.name == job_data["name"]
        assert job.input_path == job_data["input_path"]
        assert job.output_path == job_data["output_path"]
        assert job.settings == job_data["settings"]
        assert job.priority == JobPriority.NORMAL  # default
        assert job.status == JobStatus.PENDING  # default
        assert job.progress == 0.0
        assert job.error_message is None

    def test_job_creation_with_priority(self, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test creating job with specific priority."""
        job_data = sample_job_data["high_priority"]
        job = BatchJob(**job_data)

        assert job.priority == JobPriority.HIGH
        assert job.id == job_data["id"]

    @pytest.mark.parametrize(
        "priority1,priority2,expected_order",
        [
            (JobPriority.HIGH, JobPriority.NORMAL, True),
            (JobPriority.NORMAL, JobPriority.LOW, True),
            (JobPriority.HIGH, JobPriority.LOW, True),
            (JobPriority.NORMAL, JobPriority.HIGH, False),
        ],
    )
    def test_job_priority_comparison(self, sample_job_data: Any, priority1: Any, priority2: Any, expected_order: Any) -> None:  # noqa: PLR6301
        """Test job priority comparison with parameterized priorities."""
        job1_data = sample_job_data["basic"].copy()
        job1_data["id"] = "job1"
        job1_data["priority"] = priority1

        job2_data = sample_job_data["basic"].copy()
        job2_data["id"] = "job2"
        job2_data["priority"] = priority2

        job1 = BatchJob(**job1_data)
        job2 = BatchJob(**job2_data)

        if expected_order:
            assert job1 < job2
            assert not (job2 < job1)
        else:
            assert job2 < job1
            assert not (job1 < job2)

    def test_job_serialization_roundtrip(self, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test job to/from dict conversion."""
        job_data = sample_job_data["serialization_test"]
        original = BatchJob(**job_data)

        # Convert to dict and back
        job_dict = original.to_dict()
        restored = BatchJob.from_dict(job_dict)

        # Verify all fields match
        for field in ["id", "name", "input_path", "output_path", "settings", "priority"]:
            assert getattr(restored, field) == getattr(original, field)


class TestBatchQueue:
    """Test BatchQueue class with optimized test methods."""

    def test_queue_initialization(self, batch_queue: Any, mock_process_function: Any) -> None:  # noqa: PLR6301
        """Test batch queue initialization."""
        assert batch_queue.max_concurrent_jobs == 2
        assert not batch_queue._running  # noqa: SLF001
        assert len(batch_queue._jobs) == 0  # noqa: SLF001
        assert batch_queue.process_function == mock_process_function

    def test_job_lifecycle_operations(self, batch_queue: Any, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test complete job lifecycle: add, cancel, remove."""
        job_data = sample_job_data["basic"]
        job = BatchJob(**job_data)

        # Test add job
        signal_received = []
        batch_queue.job_added.connect(signal_received.append)

        batch_queue.add_job(job)

        # Verify job was added
        assert job.id in batch_queue._jobs  # noqa: SLF001
        assert batch_queue.get_job(job.id) == job
        assert job.id in signal_received

        # Test cancel job
        cancel_signals = []
        batch_queue.job_cancelled.connect(cancel_signals.append)

        result = batch_queue.cancel_job(job.id)
        assert result is True
        assert batch_queue.get_job(job.id).status == JobStatus.CANCELLED
        assert job.id in cancel_signals

        # Can't cancel already cancelled job
        assert batch_queue.cancel_job(job.id) is False

    def test_priority_based_job_retrieval(self, batch_queue: Any, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test getting jobs sorted by priority."""
        # Create jobs with different priorities
        priorities_and_ids = [
            (JobPriority.LOW, "low_job"),
            (JobPriority.HIGH, "high_job"),
            (JobPriority.NORMAL, "normal_job"),
        ]

        created_jobs = []
        for priority, job_id in priorities_and_ids:
            job_data = sample_job_data["basic"].copy()
            job_data["id"] = job_id
            job_data["priority"] = priority
            job = BatchJob(**job_data)
            batch_queue.add_job(job)
            created_jobs.append(job)

        # Get pending jobs (should be sorted by priority)
        pending = batch_queue.get_pending_jobs()

        assert len(pending) == 3
        # Should be in priority order: HIGH, NORMAL, LOW
        assert pending[0].id == "high_job"
        assert pending[1].id == "normal_job"
        assert pending[2].id == "low_job"

    def test_completed_job_management(self, batch_queue: Any, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test clearing completed jobs."""
        # Create jobs with different statuses
        job_statuses = [
            ("completed_1", JobStatus.COMPLETED),
            ("pending_1", JobStatus.PENDING),
            ("completed_2", JobStatus.COMPLETED),
            ("running_1", JobStatus.RUNNING),
        ]

        for job_id, status in job_statuses:
            job_data = sample_job_data["basic"].copy()
            job_data["id"] = job_id
            job = BatchJob(**job_data)
            job.status = status
            batch_queue.add_job(job)

        # Clear completed jobs
        removed = batch_queue.clear_completed()

        assert removed == 2  # Should remove 2 completed jobs
        assert batch_queue.get_job("completed_1") is None
        assert batch_queue.get_job("completed_2") is None
        assert batch_queue.get_job("pending_1") is not None
        assert batch_queue.get_job("running_1") is not None

    @patch("goesvfi.pipeline.batch_queue.json.dump")
    @patch("goesvfi.pipeline.batch_queue.open", create=True)
    def test_queue_persistence(self, mock_open: Any, mock_json_dump: Any, batch_queue: Any, sample_job_data: Any) -> None:  # noqa: PLR6301
        """Test saving and loading queue state."""
        job_data = sample_job_data["basic"]
        job = BatchJob(**job_data)
        batch_queue.add_job(job)

        # Force save
        batch_queue._save_queue()  # noqa: SLF001

        # Verify save operations were called
        mock_open.assert_called()
        mock_json_dump.assert_called()

    @pytest.mark.parametrize("max_concurrent", [1, 2, 4])
    def test_queue_concurrency_settings(self, mock_process_function: Any, mock_file_operations: Any, max_concurrent: Any) -> None:  # noqa: PLR6301, ARG002
        """Test queue with different concurrency settings."""
        queue = BatchQueue(
            process_function=mock_process_function,
            max_concurrent_jobs=max_concurrent,
        )

        try:
            assert queue.max_concurrent_jobs == max_concurrent

            # Add multiple jobs
            for i in range(max_concurrent + 2):
                job = BatchJob(
                    id=f"job_{i}",
                    name=f"Job {i}",
                    input_path=Path(f"/tmp/input_{i}.png"),  # noqa: S108
                    output_path=Path(f"/tmp/output_{i}.mp4"),  # noqa: S108
                    settings={"fps": 30},
                )
                queue.add_job(job)

            pending_jobs = queue.get_pending_jobs()
            assert len(pending_jobs) == max_concurrent + 2
        finally:
            if queue._running:  # noqa: SLF001
                queue.stop()


class TestBatchProcessor:
    """Test BatchProcessor class with consolidated test methods."""

    def test_processor_queue_creation(self) -> None:  # noqa: PLR6301
        """Test creating a queue through processor."""
        processor = BatchProcessor()
        mock_func = MagicMock()

        queue = processor.create_queue(process_function=mock_func, max_concurrent=3)

        assert isinstance(queue, BatchQueue)
        assert queue.max_concurrent_jobs == 3
        assert processor.queue == queue

    def test_job_creation_from_paths(self) -> None:  # noqa: PLR6301
        """Test creating jobs from file paths with various configurations."""
        processor = BatchProcessor()

        test_configs = [
            {
                "input_paths": [Path("/tmp/image1.png"), Path("/tmp/image2.png")],  # noqa: S108
                "output_dir": Path("/tmp/output"),  # noqa: S108
                "settings": {"fps": 30},
                "job_name_prefix": "Test",
                "priority": JobPriority.HIGH,
                "expected_count": 2,
            },
            {
                "input_paths": [Path("/tmp/single.png")],  # noqa: S108
                "output_dir": Path("/tmp/single_output"),  # noqa: S108
                "settings": {"fps": 60},
                "job_name_prefix": "Single",
                "priority": JobPriority.NORMAL,
                "expected_count": 1,
            },
        ]

        for config in test_configs:
            jobs = processor.create_job_from_paths(
                input_paths=config["input_paths"],
                output_dir=config["output_dir"],
                settings=config["settings"],
                job_name_prefix=config["job_name_prefix"],
                priority=config["priority"],
            )

            assert len(jobs) == config["expected_count"]
            assert all(isinstance(job, BatchJob) for job in jobs)
            assert all(job.priority == config["priority"] for job in jobs)

            if config["expected_count"] > 1:
                assert jobs[0].name.startswith(config["job_name_prefix"])

    @patch("goesvfi.pipeline.batch_queue.Path.glob")
    def test_directory_processing(self, mock_glob: Any) -> None:  # noqa: PLR6301
        """Test adding all files from a directory."""
        processor = BatchProcessor()
        processor.queue = MagicMock()

        # Mock finding different file patterns
        test_cases = [
            {
                "pattern": "*.png",
                "found_files": [Path("/tmp/input/file1.png"), Path("/tmp/input/file2.png")],  # noqa: S108
                "expected_jobs": 2,
            },
            {
                "pattern": "*.jpg",
                "found_files": [Path("/tmp/input/image.jpg")],  # noqa: S108
                "expected_jobs": 1,
            },
            {
                "pattern": "*.mp4",
                "found_files": [],
                "expected_jobs": 0,
            },
        ]

        for case in test_cases:
            mock_glob.return_value = case["found_files"]

            with patch.object(Path, "glob", mock_glob):
                job_ids = processor.add_directory(
                    input_dir=Path("/tmp/input"),  # noqa: S108
                    output_dir=Path("/tmp/output"),  # noqa: S108
                    settings={"fps": 60},
                    pattern=case["pattern"],
                    priority=JobPriority.NORMAL,
                )

            assert len(job_ids) == case["expected_jobs"]
            assert processor.queue.add_job.call_count >= case["expected_jobs"]

            # Reset mock for next iteration
            processor.queue.add_job.reset_mock()

    def test_processor_with_mock_queue_integration(self) -> None:  # noqa: PLR6301
        """Test processor integration with mock queue."""
        processor = BatchProcessor()
        mock_queue = MagicMock()
        processor.queue = mock_queue

        # Test that processor methods interact correctly with queue
        input_paths = [Path("/tmp/test1.png"), Path("/tmp/test2.png")]  # noqa: S108
        output_dir = Path("/tmp/output")  # noqa: S108
        settings = {"fps": 24}

        jobs = processor.create_job_from_paths(
            input_paths=input_paths,
            output_dir=output_dir,
            settings=settings,
        )

        # Jobs should be created but not automatically added to queue
        assert len(jobs) == 2
        assert all(isinstance(job, BatchJob) for job in jobs)

        # Manually add jobs to queue
        for job in jobs:
            processor.queue.add_job(job)

        # Verify queue interactions
        assert mock_queue.add_job.call_count == 2

    @pytest.mark.parametrize(
        "file_extension,expected_output_ext",
        [
            (".png", "_processed.png"),
            (".jpg", "_processed.jpg"),
            (".tiff", "_processed.tiff"),
        ],
    )
    def test_output_file_naming(self, file_extension: str, expected_output_ext: str) -> None:  # noqa: PLR6301
        """Test output file naming for different input file types."""
        processor = BatchProcessor()

        input_path = Path(f"/tmp/input/test{file_extension}")  # noqa: S108
        output_dir = Path("/tmp/output")  # noqa: S108

        jobs = processor.create_job_from_paths(
            input_paths=[input_path],
            output_dir=output_dir,
            settings={"fps": 30},
        )

        assert len(jobs) == 1
        assert jobs[0].output_path.name == f"test{expected_output_ext}"
        assert jobs[0].output_path.parent == output_dir
