"""Critical scenario tests for VFI Processing Pipeline.

This test suite covers high-priority missing areas identified in the testing gap analysis:
1. End-to-end workflow integration with all components
2. Cancellation and timeout handling
3. Resource limit enforcement and memory management
4. Concurrent processing stress scenarios
5. Error propagation and recovery
6. Process cleanup under failure conditions
7. Performance monitoring and progress tracking
"""

import gc
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

from PIL import Image
import pytest

from goesvfi.pipeline.exceptions import FFmpegError, ProcessingError, RIFEError
from goesvfi.pipeline.run_vfi import (
    InterpolationPipeline,
    VFIProcessor,
    VfiWorker,
    run_vfi,
)


class TestVFIPipelineCritical:
    """Critical scenario tests for VFI processing pipeline."""

    @pytest.fixture()
    def temp_dir(self) -> Any:
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture()
    def pipeline_test_generator(self) -> Any:
        """Generate test scenarios for VFI pipeline."""

        class PipelineTestGenerator:
            @staticmethod
            def create_test_images(
                count: int, width: int = 64, height: int = 64, temp_dir: Path | None = None
            ) -> list[Path]:
                """Create sequence of test PNG images."""
                if temp_dir is None:
                    temp_dir = Path(tempfile.mkdtemp())

                image_paths = []
                for i in range(count):
                    # Create different images to simulate real sequence
                    img = Image.new("RGB", (width, height), color=(i * 30 % 255, 128, 200))
                    path = temp_dir / f"frame_{i:04d}.png"
                    img.save(path)
                    image_paths.append(path)

                return image_paths

            @staticmethod
            def create_test_rife_executable(temp_dir: Path) -> Path:
                """Create mock RIFE executable for testing."""
                rife_path = temp_dir / "rife" / "rife-cli"
                rife_path.parent.mkdir(parents=True, exist_ok=True)
                rife_path.touch()
                rife_path.chmod(0o755)

                # Create models directory structure
                models_dir = rife_path.parent.parent / "models" / "rife-v4.6"
                models_dir.mkdir(parents=True, exist_ok=True)
                (models_dir / "flownet.pkl").touch()

                return rife_path

            @staticmethod
            def create_vfi_processor(rife_path: Path, temp_dir: Path) -> VFIProcessor:
                """Create VFIProcessor with test configuration."""
                rife_config = {
                    "rife_tile_enable": False,
                    "rife_tile_size": 256,
                    "rife_uhd_mode": False,
                    "rife_thread_spec": "1:2:2",
                    "rife_tta_spatial": False,
                    "rife_tta_temporal": False,
                    "model_key": "rife-v4.6",
                }

                processing_config = {
                    "false_colour": False,
                    "res_km": 4,
                }

                return VFIProcessor(
                    rife_exe_path=rife_path,
                    fps=30,
                    num_intermediate_frames=1,
                    max_workers=2,
                    rife_config=rife_config,
                    processing_config=processing_config,
                )

        return PipelineTestGenerator()

    @pytest.fixture()
    def progress_monitor(self) -> Any:
        """Create progress monitoring fixture."""

        class ProgressMonitor:
            def __init__(self) -> None:
                self.progress_updates: list[tuple[int, int, float, float]] = []
                self.completion_events: list[tuple[str, float]] = []
                self.error_events: list[tuple[str, float]] = []
                self.lock = threading.Lock()

            def on_progress(self, current: int, total: int, eta: float) -> None:
                with self.lock:
                    self.progress_updates.append((current, total, eta, time.time()))

            def on_completion(self, result_path: str) -> None:
                with self.lock:
                    self.completion_events.append((result_path, time.time()))

            def on_error(self, error_message: str) -> None:
                with self.lock:
                    self.error_events.append((error_message, time.time()))

            def reset(self) -> None:
                with self.lock:
                    self.progress_updates.clear()
                    self.completion_events.clear()
                    self.error_events.clear()

            def get_latest_progress(self):
                with self.lock:
                    return self.progress_updates[-1] if self.progress_updates else None

        return ProgressMonitor()

    def test_end_to_end_workflow_integration(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test complete end-to-end VFI processing workflow."""
        # Create test images
        image_paths = pipeline_test_generator.create_test_images(5, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)
        output_path = temp_dir / "output.mp4"

        # Mock all external dependencies
        with patch("subprocess.Popen") as mock_popen:
            # Mock FFmpeg process and create output file
            def create_output_file(*args, **kwargs):
                mock_ffmpeg = Mock()
                mock_ffmpeg.stdin = Mock()
                mock_ffmpeg.stdout = iter([])  # Make stdout iterable
                mock_ffmpeg.poll.return_value = None
                mock_ffmpeg.wait.return_value = 0

                # Create the raw output file that FFmpeg would create
                if len(args) > 0 and "output.raw.mp4" in str(args[0]):
                    for arg in args[0]:
                        if "output.raw.mp4" in str(arg):
                            output_file = Path(arg)
                            output_file.touch()
                            break

                return mock_ffmpeg

            mock_popen.side_effect = create_output_file

            with patch("goesvfi.pipeline.run_vfi._run_rife_pair") as mock_rife:
                # Mock RIFE interpolation
                def mock_rife_func(p1, p2, exe, config):
                    interp_path = p1.parent / f"interp_{time.monotonic_ns()}.png"
                    # Create interpolated image
                    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
                    img.save(interp_path)
                    return interp_path

                mock_rife.side_effect = mock_rife_func

                with patch("pathlib.Path.exists") as mock_exists:
                    mock_exists.return_value = True

                    with patch("pathlib.Path.glob") as mock_glob:
                        # Mock glob to return our test images
                        mock_glob.return_value = iter(image_paths)

                        # Run VFI processing
                        results = list(
                            run_vfi(
                                folder=temp_dir,
                                output_mp4_path=output_path,
                                rife_exe_path=rife_path,
                                fps=30,
                                num_intermediate_frames=1,
                                max_workers=2,
                                skip_model=False,
                            )
                        )

                        # Verify processing completed
                        assert len(results) > 0

                        # Should have progress updates and final path
                        progress_updates = [r for r in results if isinstance(r, tuple)]
                        final_paths = [r for r in results if isinstance(r, Path)]

                        assert len(progress_updates) > 0, "Should have progress updates"
                        assert len(final_paths) == 1, "Should have exactly one final output path"

                        # Verify FFmpeg was called
                        mock_popen.assert_called()

    def test_processing_cancellation_and_cleanup(
        self, temp_dir: Path, pipeline_test_generator: Any, progress_monitor: Any
    ) -> None:
        """Test cancellation of long-running VFI processing."""
        # Create test images
        image_paths = pipeline_test_generator.create_test_images(10, temp_dir=temp_dir)
        pipeline_test_generator.create_test_rife_executable(temp_dir)
        output_path = temp_dir / "output.mp4"

        # Create VFI worker for Qt thread simulation
        worker = VfiWorker(
            in_dir=str(temp_dir),
            out_file_path=str(output_path),
            fps=30,
            mid_count=1,
            max_workers=2,
            skip_model=False,
        )

        # Connect signals
        worker.progress.connect(progress_monitor.on_progress)
        worker.finished.connect(progress_monitor.on_completion)
        worker.error.connect(progress_monitor.on_error)

        # Mock long-running process
        cancel_requested = threading.Event()

        def slow_rife_mock(p1, p2, exe, config):
            # Simulate slow RIFE processing
            for _i in range(10):
                if cancel_requested.is_set():
                    msg = "Processing cancelled"
                    raise ProcessingError(msg)
                time.sleep(0.1)

            # Create result
            interp_path = p1.parent / f"interp_{time.monotonic_ns()}.png"
            img = Image.new("RGB", (64, 64), color=(100, 150, 200))
            img.save(interp_path)
            return interp_path

        with patch("goesvfi.pipeline.run_vfi._run_rife_pair", side_effect=slow_rife_mock):
            with patch("subprocess.Popen") as mock_popen:
                mock_ffmpeg = Mock()
                mock_ffmpeg.stdin = Mock()
                mock_ffmpeg.stdout = iter([])
                mock_ffmpeg.poll.return_value = None
                mock_ffmpeg.terminate = Mock()
                mock_ffmpeg.kill = Mock()
                mock_ffmpeg.wait = Mock(return_value=0)
                mock_popen.return_value = mock_ffmpeg

                with patch("pathlib.Path.glob") as mock_glob:
                    # Mock glob to return our test images
                    mock_glob.return_value = iter(image_paths)

                    # Start worker in separate thread
                    worker_thread = threading.Thread(target=worker.run)
                    worker_thread.start()

                    # Let it start processing
                    time.sleep(0.2)

                    # Request cancellation
                    cancel_requested.set()

                    # Wait for thread to complete
                    worker_thread.join(timeout=5.0)

                    # Verify cancellation was handled
                    assert len(progress_monitor.error_events) > 0, "Should have error events from cancellation"

    def test_resource_limit_enforcement(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test resource limit enforcement during processing."""
        # Create test images
        image_paths = pipeline_test_generator.create_test_images(10, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Mock resource manager to enforce limits
        with patch("goesvfi.pipeline.run_vfi.get_resource_manager") as mock_resource_mgr:
            mock_mgr = Mock()
            mock_mgr.get_optimal_workers.return_value = 1  # Limit to 1 worker
            mock_mgr.check_resources.return_value = None
            mock_resource_mgr.return_value = mock_mgr

            with patch("goesvfi.pipeline.run_vfi.managed_executor") as mock_executor:
                # Mock executor context manager
                mock_exec = Mock()
                mock_exec.__enter__ = Mock(return_value=mock_exec)
                mock_exec.__exit__ = Mock(return_value=None)
                mock_executor.return_value = mock_exec

                with patch("subprocess.Popen") as mock_popen:
                    mock_ffmpeg = Mock()
                    mock_ffmpeg.stdin = Mock()
                    mock_ffmpeg.stdout = iter([])
                    mock_ffmpeg.poll.return_value = None
                    mock_ffmpeg.wait.return_value = 0
                    mock_popen.return_value = mock_ffmpeg

                    with patch("pathlib.Path.glob") as mock_glob:
                        # Mock glob to return our test images
                        mock_glob.return_value = iter(image_paths)

                        with patch("goesvfi.pipeline.run_vfi._run_rife_pair") as mock_rife:
                            # Create dummy output
                            def mock_rife_func(p1, p2, exe, config):
                                interp_path = p1.parent / f"interp_{time.monotonic_ns()}.png"
                                img = Image.new("RGB", (64, 64), color=(100, 150, 200))
                                img.save(interp_path)
                                return interp_path

                            mock_rife.side_effect = mock_rife_func

                            # Run VFI processing - this should trigger resource manager usage
                            list(
                                run_vfi(
                                    folder=temp_dir,
                                    output_mp4_path=temp_dir / "resource_test.mp4",
                                    rife_exe_path=rife_path,
                                    fps=30,
                                    num_intermediate_frames=1,
                                    max_workers=2,  # This should be limited by resource manager
                                    skip_model=False,
                                )
                            )

                            # Verify resource manager was consulted
                            mock_resource_mgr.assert_called()

    def test_concurrent_processing_stress(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test concurrent processing under stress conditions."""
        # Create multiple interpolation pipelines
        pipelines = []

        with InterpolationPipeline(max_workers=2) as pipeline1:
            with InterpolationPipeline(max_workers=2) as pipeline2:
                pipelines.extend([pipeline1, pipeline2])

                # Process multiple tasks concurrently
                results = []
                errors = []

                def process_task(pipeline, task_id, image_count) -> None:
                    try:
                        images = [f"image_{i}.png" for i in range(image_count)]
                        result = pipeline.process(images, task_id)
                        results.append((task_id, result))
                    except Exception as e:
                        errors.append((task_id, str(e)))

                # Start multiple concurrent tasks
                threads = []
                for i in range(4):
                    pipeline = pipelines[i % len(pipelines)]
                    thread = threading.Thread(target=process_task, args=(pipeline, f"task_{i}", 5 + i))
                    threads.append(thread)
                    thread.start()

                # Wait for all to complete
                for thread in threads:
                    thread.join(timeout=10.0)

                # Verify all tasks completed successfully
                assert len(errors) == 0, f"Concurrent processing errors: {errors}"
                assert len(results) == 4, f"Expected 4 results, got {len(results)}"

    def test_error_propagation_and_recovery(
        self, temp_dir: Path, pipeline_test_generator: Any, progress_monitor: Any
    ) -> None:
        """Test error propagation and recovery mechanisms."""
        # Create test setup
        pipeline_test_generator.create_test_images(3, temp_dir=temp_dir)
        pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Test different error scenarios
        error_scenarios = [
            ("rife_failure", RIFEError("RIFE execution failed")),
            ("ffmpeg_failure", FFmpegError("FFmpeg encoding failed")),
            ("processing_failure", ProcessingError("Generic processing error")),
            ("file_not_found", FileNotFoundError("Input file not found")),
            ("permission_error", PermissionError("Cannot write output file")),
        ]

        for scenario_name, exception in error_scenarios:
            progress_monitor.reset()

            worker = VfiWorker(
                in_dir=str(temp_dir),
                out_file_path=str(temp_dir / f"output_{scenario_name}.mp4"),
                fps=30,
                mid_count=1,
                skip_model=False,
            )

            worker.progress.connect(progress_monitor.on_progress)
            worker.error.connect(progress_monitor.on_error)

            # Mock the specific failure
            with patch("goesvfi.pipeline.run_vfi.run_vfi") as mock_run_vfi:
                mock_run_vfi.side_effect = exception

                # Run worker
                worker.run()

                # Verify error was captured and handled
                assert len(progress_monitor.error_events) > 0, f"No error event for {scenario_name}"
                error_msg = progress_monitor.error_events[0][0]
                assert scenario_name.split("_")[0] in error_msg.lower() or "error" in error_msg.lower()

    def test_memory_management_large_sequences(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test memory management with large image sequences."""
        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create large sequence of images
        large_sequence = pipeline_test_generator.create_test_images(50, width=256, height=256, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Mock processing to avoid actual heavy computation
        with patch("goesvfi.pipeline.run_vfi._run_rife_pair") as mock_rife:
            mock_rife.return_value = large_sequence[0]  # Return dummy path

            with patch("subprocess.Popen") as mock_popen:
                mock_ffmpeg = Mock()
                mock_ffmpeg.stdin = Mock()
                mock_ffmpeg.stdout = iter([])
                mock_ffmpeg.poll.return_value = None
                mock_ffmpeg.wait.return_value = 0
                mock_popen.return_value = mock_ffmpeg

                with patch("pathlib.Path.glob") as mock_glob:
                    # Mock glob to return our test images
                    mock_glob.return_value = iter(large_sequence)

                    # Process the large sequence
                    list(
                        run_vfi(
                            folder=temp_dir,
                            output_mp4_path=temp_dir / "large_output.mp4",
                            rife_exe_path=rife_path,
                            fps=30,
                            num_intermediate_frames=1,
                            max_workers=2,
                            skip_model=False,
                        )
                    )

                    # Force garbage collection
                    gc.collect()

                    # Check memory usage didn't grow excessively
                    final_memory = process.memory_info().rss
                    memory_increase = final_memory - initial_memory

                    # Allow for some memory increase but detect significant leaks
                    # 200MB increase might indicate a memory leak
                    assert memory_increase < 200 * 1024 * 1024, (
                        f"Potential memory leak: {memory_increase / 1024 / 1024:.1f} MB increase"
                    )

    def test_progress_tracking_accuracy(
        self, temp_dir: Path, pipeline_test_generator: Any, progress_monitor: Any
    ) -> None:
        """Test accuracy of progress tracking throughout pipeline."""
        # Create test sequence
        pipeline_test_generator.create_test_images(8, temp_dir=temp_dir)
        pipeline_test_generator.create_test_rife_executable(temp_dir)

        worker = VfiWorker(
            in_dir=str(temp_dir),
            out_file_path=str(temp_dir / "progress_test.mp4"),
            fps=30,
            mid_count=1,
            skip_model=False,
        )

        worker.progress.connect(progress_monitor.on_progress)
        worker.finished.connect(progress_monitor.on_completion)

        # Mock with controlled progress reporting
        def controlled_run_vfi(*args, **kwargs):
            total_pairs = 7  # 8 images = 7 pairs

            for i in range(total_pairs):
                yield (i + 1, total_pairs, float(i + 1) * 0.5)  # Simulated ETA

            yield temp_dir / "progress_test.mp4"

        with patch("goesvfi.pipeline.run_vfi.run_vfi", side_effect=controlled_run_vfi):
            worker.run()

        # Verify progress tracking
        assert len(progress_monitor.progress_updates) > 0, "Should have progress updates"
        assert len(progress_monitor.completion_events) == 1, "Should have exactly one completion event"

        # Check progress is monotonically increasing
        progress_values = [update[0] for update in progress_monitor.progress_updates]
        for i in range(len(progress_values) - 1):
            assert progress_values[i] <= progress_values[i + 1], "Progress values should be monotonically increasing"

        # Check final progress reaches total
        final_progress = progress_monitor.progress_updates[-1]
        current, total, _eta = final_progress[:3]
        assert current == total, "Final progress should reach total"

    def test_process_cleanup_under_failures(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test that processes are properly cleaned up when failures occur."""
        # Create test setup
        pipeline_test_generator.create_test_images(5, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Track process lifecycle
        processes_created = []
        processes_terminated = []

        def track_popen(*args, **kwargs):
            mock_proc = Mock()
            mock_proc.stdin = Mock()
            mock_proc.stdout = Mock()
            mock_proc.poll.return_value = None

            # Track when terminate/kill are called
            def track_terminate() -> None:
                processes_terminated.append(("terminate", time.time()))

            def track_kill() -> None:
                processes_terminated.append(("kill", time.time()))

            mock_proc.terminate = Mock(side_effect=track_terminate)
            mock_proc.kill = Mock(side_effect=track_kill)
            mock_proc.wait = Mock(return_value=0)

            processes_created.append((mock_proc, time.time()))
            return mock_proc

        with patch("subprocess.Popen", side_effect=track_popen):
            with patch("goesvfi.pipeline.run_vfi._run_rife_pair") as mock_rife:
                # Make RIFE fail after some processing
                call_count = 0

                def failing_rife(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:  # Fail after 2 successful calls
                        msg = "RIFE processing failed"
                        raise RIFEError(msg)

                    # Create dummy output for successful calls
                    interp_path = args[0].parent / f"interp_{call_count}.png"
                    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
                    img.save(interp_path)
                    return interp_path

                mock_rife.side_effect = failing_rife

                # Try to run VFI (should fail)
                try:
                    list(
                        run_vfi(
                            folder=temp_dir,
                            output_mp4_path=temp_dir / "cleanup_test.mp4",
                            rife_exe_path=rife_path,
                            fps=30,
                            num_intermediate_frames=1,
                            max_workers=2,
                            skip_model=False,
                        )
                    )
                except (RIFEError, RuntimeError):
                    pass  # Expected failure

                # Verify processes were created and then cleaned up
                assert len(processes_created) > 0, "Should have created processes"
                assert len(processes_terminated) > 0, "Should have terminated processes when error occurred"

    def test_timeout_handling(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test handling of process timeouts."""
        # Create test setup
        image_paths = pipeline_test_generator.create_test_images(3, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Mock RIFE to simulate timeout but with controlled duration
        def timeout_rife(*args, **kwargs):
            # Simulate hanging process (short for testing)
            time.sleep(2)  # Reduced timeout for testing
            return args[0]  # Never reached

        with patch("goesvfi.pipeline.run_vfi._run_rife_pair", side_effect=timeout_rife):
            with patch("subprocess.Popen") as mock_popen:
                mock_ffmpeg = Mock()
                mock_ffmpeg.stdin = Mock()
                mock_ffmpeg.stdout = iter([])
                mock_ffmpeg.poll.return_value = None
                mock_ffmpeg.wait.return_value = 0
                mock_popen.return_value = mock_ffmpeg

                with patch("pathlib.Path.glob") as mock_glob:
                    # Mock glob to return our test images
                    mock_glob.return_value = iter(image_paths)

                    # Use a timeout mechanism in the test
                    start_time = time.time()
                    timeout_occurred = False

                    try:
                        # Run with a short timeout
                        results = []
                        for result in run_vfi(
                            folder=temp_dir,
                            output_mp4_path=temp_dir / "timeout_test.mp4",
                            rife_exe_path=rife_path,
                            fps=30,
                            num_intermediate_frames=1,
                            max_workers=2,
                            skip_model=False,
                        ):
                            results.append(result)

                            # Check for timeout
                            if time.time() - start_time > 2.5:  # 2.5 second timeout
                                timeout_occurred = True
                                break

                    except Exception:
                        # Expected due to hanging operation
                        timeout_occurred = True

                    # Verify timeout was handled appropriately
                    elapsed = time.time() - start_time
                    assert elapsed < 8.0, "Should not hang for more than 8 seconds"
                    assert timeout_occurred or elapsed < 1.0, "Should either timeout or process quickly"

    def test_signal_handling_interruption(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test handling of system signals during processing."""
        # Create test setup
        image_paths = pipeline_test_generator.create_test_images(10, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Track signal handling
        signal_received = threading.Event()

        def mock_rife_with_signal_check(*args, **kwargs):
            # Check for signal during processing
            if signal_received.is_set():
                msg = "Processing interrupted"
                raise KeyboardInterrupt(msg)

            time.sleep(0.1)  # Simulate processing time

            # Create dummy output
            interp_path = args[0].parent / f"interp_{time.monotonic_ns()}.png"
            img = Image.new("RGB", (64, 64), color=(100, 150, 200))
            img.save(interp_path)
            return interp_path

        with patch("goesvfi.pipeline.run_vfi._run_rife_pair", side_effect=mock_rife_with_signal_check):
            with patch("subprocess.Popen") as mock_popen:
                mock_ffmpeg = Mock()
                mock_ffmpeg.stdin = Mock()
                mock_ffmpeg.stdout = iter([])
                mock_ffmpeg.poll.return_value = None
                mock_ffmpeg.terminate = Mock()
                mock_ffmpeg.kill = Mock()
                mock_ffmpeg.wait = Mock(return_value=0)
                mock_popen.return_value = mock_ffmpeg

                with patch("pathlib.Path.glob") as mock_glob:
                    # Mock glob to return our test images
                    mock_glob.return_value = iter(image_paths)

                    # Start processing in a separate thread
                    processing_exception = None

                    def run_processing() -> None:
                        nonlocal processing_exception
                        try:
                            list(
                                run_vfi(
                                    folder=temp_dir,
                                    output_mp4_path=temp_dir / "signal_test.mp4",
                                    rife_exe_path=rife_path,
                                    fps=30,
                                    num_intermediate_frames=1,
                                    max_workers=2,
                                    skip_model=False,
                                )
                            )
                        except Exception as e:
                            processing_exception = e

                    processing_thread = threading.Thread(target=run_processing)
                    processing_thread.start()

                    # Let processing start
                    time.sleep(0.3)

                    # Simulate signal
                    signal_received.set()

                    # Wait for processing to complete
                    processing_thread.join(timeout=5.0)

                    # Verify interruption was handled
                    assert processing_exception is not None, "Should have received interruption exception"
                    assert isinstance(processing_exception, KeyboardInterrupt), "Should be KeyboardInterrupt exception"

    def test_resource_exhaustion_recovery(self, temp_dir: Path, pipeline_test_generator: Any) -> None:
        """Test recovery from resource exhaustion scenarios."""
        # Create test setup
        pipeline_test_generator.create_test_images(5, temp_dir=temp_dir)
        rife_path = pipeline_test_generator.create_test_rife_executable(temp_dir)

        # Simulate resource exhaustion scenarios
        exhaustion_scenarios = [
            ("memory_error", MemoryError("Cannot allocate memory")),
            ("disk_full", OSError("No space left on device")),
            ("too_many_files", OSError("Too many open files")),
        ]

        for scenario_name, exception in exhaustion_scenarios:
            call_count = 0

            def resource_exhaustion_rife(*args, **kwargs):
                nonlocal call_count
                call_count += 1

                if call_count == 2:  # Fail on second call
                    raise exception

                # Create dummy output for other calls
                interp_path = args[0].parent / f"interp_{call_count}.png"
                img = Image.new("RGB", (64, 64), color=(100, 150, 200))
                img.save(interp_path)
                return interp_path

            with patch("goesvfi.pipeline.run_vfi._run_rife_pair", side_effect=resource_exhaustion_rife):
                with patch("subprocess.Popen") as mock_popen:
                    mock_ffmpeg = Mock()
                    mock_ffmpeg.stdin = Mock()
                    mock_ffmpeg.stdout = iter([])
                    mock_ffmpeg.poll.return_value = None
                    mock_ffmpeg.wait.return_value = 0
                    mock_popen.return_value = mock_ffmpeg

                    # Should handle resource exhaustion gracefully
                    with pytest.raises((MemoryError, OSError)):
                        list(
                            run_vfi(
                                folder=temp_dir,
                                output_mp4_path=temp_dir / f"exhaustion_{scenario_name}.mp4",
                                rife_exe_path=rife_path,
                                fps=30,
                                num_intermediate_frames=1,
                                max_workers=2,
                                skip_model=False,
                            )
                        )
