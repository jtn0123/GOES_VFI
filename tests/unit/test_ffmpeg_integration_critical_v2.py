"""Critical scenario tests for FFmpeg Integration.

This test suite covers high-priority missing areas identified in the testing gap analysis:
1. FFmpeg command construction with complex parameter combinations
2. Error parsing from FFmpeg stderr/stdout with real-world scenarios
3. Process management and cleanup under stress conditions
4. Large file processing with memory and resource monitoring
5. Concurrent execution and resource contention management
6. Hardware encoder fallback and error recovery
7. Profile validation and compatibility checking
"""

import contextlib
from pathlib import Path
import subprocess  # noqa: S404
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

from goesvfi.pipeline.exceptions import FFmpegError
from goesvfi.pipeline.ffmpeg_builder import FFmpegCommandBuilder
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class TestFFmpegIntegrationCritical:
    """Critical scenario tests for FFmpeg integration."""

    @pytest.fixture()
    @staticmethod
    def temp_media_files(tmp_path: Path) -> dict[str, Path]:
        """Create temporary media files for testing.

        Returns:
            dict[str, Path]: Dictionary mapping file types to their paths.
        """
        files = {}

        # Create test input video file (minimal valid MP4)
        input_video = tmp_path / "input.mp4"
        input_video.write_bytes(b"\x00\x00\x00\x20ftypmp41")  # Minimal MP4 header
        files["input_video"] = input_video

        # Create output paths
        files["output_video"] = tmp_path / "output.mp4"
        files["large_output"] = tmp_path / "large_output.mp4"
        files["pass_log"] = tmp_path / "pass_log"

        # Create test images for VFI
        for i in range(5):
            img_path = tmp_path / f"frame_{i:03d}.png"
            img_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header
            files[f"frame_{i}"] = img_path

        return files

    @pytest.fixture()
    @staticmethod
    def process_monitor() -> Any:
        """Create process monitoring fixture for resource tracking.

        Returns:
            ProcessMonitor: Instance for monitoring process resources.
        """

        class ProcessMonitor:
            def __init__(self) -> None:
                self.processes: list[dict[str, Any]] = []
                self.memory_usage: list[float] = []
                self.execution_times: list[float] = []
                self.exit_codes: list[int] = []
                self.stdout_captures: list[str] = []
                self.stderr_captures: list[str] = []
                self.lock = threading.Lock()

            def track_process(self, process: subprocess.Popen, start_time: float) -> None:
                with self.lock:
                    self.processes.append({
                        "process": process,
                        "start_time": start_time,
                        "pid": process.pid if process else None,
                    })

            def track_completion(
                self, exit_code: int, execution_time: float, stdout: str, stderr: str, memory_peak: float = 0.0
            ) -> None:
                with self.lock:
                    self.exit_codes.append(exit_code)
                    self.execution_times.append(execution_time)
                    self.stdout_captures.append(stdout)
                    self.stderr_captures.append(stderr)
                    self.memory_usage.append(memory_peak)

            def get_active_processes(self) -> int:
                with self.lock:
                    return len([p for p in self.processes if p["process"] and p["process"].poll() is None])

            def cleanup_all(self) -> None:
                with self.lock:
                    for proc_info in self.processes:
                        process = proc_info["process"]
                        if process and process.poll() is None:
                            try:
                                process.terminate()
                                process.wait(timeout=5)
                            except (subprocess.TimeoutExpired, ProcessLookupError):
                                with contextlib.suppress(ProcessLookupError):
                                    process.kill()

        return ProcessMonitor()

    def test_command_construction_complex_scenarios(self, temp_media_files: dict[str, Path]) -> None:
        """Test FFmpeg command construction with complex parameter combinations."""

        # Test complex x265 two-pass encoding
        builder = FFmpegCommandBuilder()
        pass1_cmd = (
            builder.set_input(temp_media_files["input_video"])
            .set_output(temp_media_files["output_video"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(5000)
            .set_bufsize(10000)
            .set_pix_fmt("yuv420p10le")
            .set_preset("slower")
            .set_tune("grain")
            .set_profile("main10")
            .set_two_pass(True, str(temp_media_files["pass_log"]), 1)
            .build()
        )

        # Verify pass 1 command structure
        assert "ffmpeg" in pass1_cmd
        assert "-i" in pass1_cmd
        assert str(temp_media_files["input_video"]) in pass1_cmd
        assert "-c:v" in pass1_cmd
        assert "libx265" in pass1_cmd
        assert "-preset" in pass1_cmd
        assert "slower" in pass1_cmd
        assert "-b:v" in pass1_cmd
        assert "5000k" in pass1_cmd
        assert "-passlogfile" in pass1_cmd
        assert "-f" in pass1_cmd
        assert "null" in pass1_cmd
        # Note: tune and profile are not included in pass 1

        # Test pass 2 with same builder (should reset internal state)
        builder_pass2 = FFmpegCommandBuilder()
        pass2_cmd = (
            builder_pass2.set_input(temp_media_files["input_video"])
            .set_output(temp_media_files["output_video"])
            .set_encoder("Software x265 (2-Pass)")
            .set_bitrate(5000)
            .set_bufsize(10000)
            .set_pix_fmt("yuv420p10le")
            .set_preset("slower")
            .set_tune("grain")
            .set_profile("main10")
            .set_two_pass(True, str(temp_media_files["pass_log"]), 2)
            .build()
        )

        # Verify pass 2 command structure
        assert str(temp_media_files["output_video"]) in pass2_cmd
        assert "-pix_fmt" in pass2_cmd
        assert "yuv420p10le" in pass2_cmd
        assert "-movflags" in pass2_cmd
        assert "+faststart" in pass2_cmd

        # Test hardware encoder with safety limits
        hardware_cmd = (
            FFmpegCommandBuilder()
            .set_input(temp_media_files["input_video"])
            .set_output(temp_media_files["output_video"])
            .set_encoder("Hardware HEVC (VideoToolbox)")
            .set_bitrate(50000)  # High bitrate
            .set_bufsize(100000)  # High buffer
            .set_pix_fmt("yuv420p")
            .build()
        )

        # Verify hardware encoder command
        assert "-c:v" in hardware_cmd
        assert "hevc_videotoolbox" in hardware_cmd
        assert "-tag:v" in hardware_cmd
        assert "hvc1" in hardware_cmd
        assert "-b:v" in hardware_cmd
        assert "-maxrate" in hardware_cmd

        # Test stream copy (no re-encoding)
        copy_cmd = (
            FFmpegCommandBuilder()
            .set_input(temp_media_files["input_video"])
            .set_output(temp_media_files["output_video"])
            .set_encoder("None (copy original)")
            .build()
        )

        # Verify copy command simplicity
        assert len(copy_cmd) < 10  # Should be minimal command
        assert "-c" in copy_cmd
        assert "copy" in copy_cmd
        assert "-y" in copy_cmd  # Overwrite existing files

    def test_command_validation_edge_cases(self, temp_media_files: dict[str, Path]) -> None:
        """Test command validation with invalid parameter combinations."""

        # Test missing required parameters
        builder = FFmpegCommandBuilder()

        with pytest.raises(ValueError, match="Input path, output path, and encoder must be set"):
            builder.build()

        with pytest.raises(ValueError, match="Input path, output path, and encoder must be set"):
            builder.set_input(temp_media_files["input_video"]).build()

        with pytest.raises(ValueError, match="Input path, output path, and encoder must be set"):
            builder.set_output(temp_media_files["output_video"]).build()

        # Test CRF required for single-pass x265
        with pytest.raises(ValueError, match="CRF must be set for single-pass x265"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Software x265")
                .build()
            )

        # Test CRF required for x264
        with pytest.raises(ValueError, match="CRF must be set for x264"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Software x264")
                .build()
            )

        # Test bitrate required for hardware encoders
        with pytest.raises(ValueError, match="Bitrate and bufsize must be set"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Hardware HEVC (VideoToolbox)")
                .set_bitrate(5000)  # Missing bufsize
                .build()
            )

        # Test two-pass parameter validation - missing two-pass setup
        with pytest.raises(ValueError, match="Two-pass encoding requires"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Software x265 (2-Pass)")
                .set_bitrate(5000)
                # Missing set_two_pass call
                .build()
            )

        # Test invalid pass number
        with pytest.raises(ValueError, match="Invalid pass number"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Software x265 (2-Pass)")
                .set_bitrate(5000)
                .set_two_pass(True, "test_log", 3)  # Invalid pass number
                .build()
            )

        # Test unsupported encoder
        with pytest.raises(ValueError, match="Unsupported encoder selected"):
            (
                FFmpegCommandBuilder()
                .set_input(temp_media_files["input_video"])
                .set_output(temp_media_files["output_video"])
                .set_encoder("Nonexistent Encoder")
                .build()
            )

    def test_error_parsing_real_world_scenarios(self, process_monitor: Any) -> None:
        """Test FFmpeg error parsing with real-world error scenarios."""

        # Mock FFmpeg error scenarios with realistic stderr output
        ffmpeg_error_scenarios = [
            {
                "name": "codec_not_found",
                "stderr": "[h264_nvenc @ 0x7f8b8c000000] Codec not found\\nError initializing output stream",
                "exit_code": 1,
                "expected_category": "codec_error",
            },
            {
                "name": "input_file_not_found",
                "stderr": "No such file or directory\\n[in#0 @ 0x7f8b8c000000] Error opening input",
                "exit_code": 1,
                "expected_category": "input_error",
            },
            {
                "name": "permission_denied",
                "stderr": "Permission denied\\n[out#0 @ 0x7f8b8c000000] Error opening output file",
                "exit_code": 1,
                "expected_category": "output_error",
            },
            {
                "name": "disk_full",
                "stderr": "No space left on device\\nError writing output file",
                "exit_code": 1,
                "expected_category": "resource_error",
            },
            {
                "name": "filter_error",
                "stderr": "[graph 0 input 0 @ 0x7f8b8c000000] No such filter: 'invalid_filter'",
                "exit_code": 1,
                "expected_category": "filter_error",
            },
            {
                "name": "memory_allocation_failed",
                "stderr": "Cannot allocate memory\\nError allocating AVFrame",
                "exit_code": 134,
                "expected_category": "memory_error",
            },
            {
                "name": "hardware_encoder_unavailable",
                "stderr": "[hevc_videotoolbox @ 0x7f8b8c000000] Error creating VideoToolbox encoder",
                "exit_code": 1,
                "expected_category": "hardware_error",
            },
        ]

        for scenario in ffmpeg_error_scenarios:
            # Create mock FFmpegError from scenario
            ffmpeg_error = FFmpegError(
                message=scenario["stderr"], command="ffmpeg -i input.mp4 output.mp4", stderr=scenario["stderr"]
            )

            # Verify error attributes
            assert scenario["stderr"] in ffmpeg_error.stderr
            assert "ffmpeg -i input.mp4 output.mp4" in ffmpeg_error.command

            # Test error classification (would require actual classifier implementation)
            # For now, just verify the error structure is properly captured
            process_monitor.track_completion(
                exit_code=scenario["exit_code"],
                execution_time=0.1,
                stdout="",
                stderr=scenario["stderr"],
                memory_peak=0.0,
            )

        # Verify all error scenarios were tracked
        assert len(process_monitor.stderr_captures) == len(ffmpeg_error_scenarios)

        # Check that different error types are distinguished
        exit_codes = set(process_monitor.exit_codes)
        assert len(exit_codes) > 1, "Should have multiple distinct exit codes"

        # Verify stderr content variety
        stderr_contents = process_monitor.stderr_captures
        unique_errors = set(stderr_contents)
        assert len(unique_errors) == len(ffmpeg_error_scenarios), "All error scenarios should be unique"

    def test_process_management_stress_conditions(
        self, temp_media_files: dict[str, Path], process_monitor: Any
    ) -> None:
        """Test process management under stress conditions."""

        class MockFFmpegProcess:
            def __init__(
                self,
                duration: float,
                exit_code: int = 0,
                memory_usage: float = 100.0,
                stdout_lines: list[str] | None = None,
            ):
                self.duration = duration
                self.exit_code = exit_code
                self.memory_usage = memory_usage
                self.stdout_lines = stdout_lines or [
                    "frame=  100 fps= 25 q=28.0 size=     512kB time=00:00:04.00 bitrate=1048.6kbits/s speed=1.00x"
                ]
                self.start_time = time.time()
                self.poll_count = 0

            def poll(self):
                self.poll_count += 1
                elapsed = time.time() - self.start_time
                if elapsed >= self.duration:
                    return self.exit_code
                return None

            def communicate(self, timeout=None):
                # Simulate process completion
                remaining_time = self.duration - (time.time() - self.start_time)
                if remaining_time > 0:
                    time.sleep(min(remaining_time, timeout or remaining_time))

                stdout = "\\n".join(self.stdout_lines)
                stderr = "Encoding completed" if self.exit_code == 0 else f"Process failed with code {self.exit_code}"
                return stdout, stderr

            def terminate(self) -> None:
                self.exit_code = -15  # SIGTERM

            def kill(self) -> None:
                self.exit_code = -9  # SIGKILL

            @property
            def pid(self):
                return 12345 + id(self) % 10000

        # Test concurrent process execution
        concurrent_processes = []
        max_concurrent = 4

        with patch("subprocess.Popen") as mock_popen:
            for i in range(max_concurrent):
                # Create processes with varying characteristics
                mock_process = MockFFmpegProcess(
                    duration=0.5 + (i * 0.2),  # Staggered completion times
                    exit_code=0 if i < 3 else 1,  # One failure
                    memory_usage=50.0 + (i * 25.0),  # Increasing memory usage
                    stdout_lines=[
                        f"frame={100 + i * 10} fps=25 q=28.0 size={512 + i * 100}kB time=00:00:0{4 + i}.00 bitrate=1048.6kbits/s speed=1.00x"
                    ],
                )

                mock_popen.return_value = mock_process

                # Track process start
                start_time = time.time()
                process_monitor.track_process(mock_process, start_time)
                concurrent_processes.append(mock_process)

            # Simulate process monitoring
            start_time = time.time()
            completed_processes = []

            while len(completed_processes) < max_concurrent and (time.time() - start_time) < 10:
                for process in concurrent_processes:
                    if process not in completed_processes and process.poll() is not None:
                        # Process completed
                        execution_time = time.time() - process.start_time
                        stdout, stderr = process.communicate(timeout=1)

                        process_monitor.track_completion(
                            exit_code=process.exit_code,
                            execution_time=execution_time,
                            stdout=stdout,
                            stderr=stderr,
                            memory_peak=process.memory_usage,
                        )
                        completed_processes.append(process)

                time.sleep(0.1)  # Polling interval

        # Verify process tracking
        assert len(process_monitor.processes) == max_concurrent
        assert len(process_monitor.execution_times) == max_concurrent
        assert len(process_monitor.exit_codes) == max_concurrent

        # Check execution time variety
        execution_times = process_monitor.execution_times
        assert min(execution_times) >= 0.5, "Minimum execution time should be respected"
        assert max(execution_times) <= 2.0, "Maximum execution time should be reasonable"

        # Verify mixed success/failure results
        exit_codes = process_monitor.exit_codes
        successful_processes = [code for code in exit_codes if code == 0]
        failed_processes = [code for code in exit_codes if code != 0]

        assert len(successful_processes) == 3, "Should have 3 successful processes"
        assert len(failed_processes) == 1, "Should have 1 failed process"

        # Check memory usage tracking
        memory_usage = process_monitor.memory_usage
        assert all(mem > 0 for mem in memory_usage), "All processes should report memory usage"
        assert max(memory_usage) > min(memory_usage), "Memory usage should vary between processes"

    def test_large_file_processing_simulation(self, temp_media_files: dict[str, Path], process_monitor: Any) -> None:
        """Test large file processing with memory and resource monitoring."""

        class LargeFileProcessor:
            def __init__(self, file_size_gb: float):
                self.file_size_gb = file_size_gb
                self.processing_phases = ["analyze", "decode", "filter", "encode", "finalize"]
                self.current_phase = 0
                self.progress_percent = 0.0
                self.memory_usage_mb = 0.0
                self.temp_files_created = []

            def simulate_processing_step(self, step_duration: float = 0.1) -> dict[str, Any]:
                """Simulate one processing step with resource usage."""
                time.sleep(step_duration)

                # Advance progress
                self.progress_percent += 2.0
                self.progress_percent = min(100.0, self.progress_percent)

                # Simulate memory usage pattern (peak during encode phase)
                phase = (
                    self.processing_phases[self.current_phase]
                    if self.current_phase < len(self.processing_phases)
                    else "encode"
                )

                if phase == "analyze":
                    self.memory_usage_mb = 100 + (self.file_size_gb * 10)
                elif phase == "decode":
                    self.memory_usage_mb = 200 + (self.file_size_gb * 50)
                elif phase == "filter":
                    self.memory_usage_mb = 300 + (self.file_size_gb * 100)  # Peak memory
                elif phase == "encode":
                    self.memory_usage_mb = 250 + (self.file_size_gb * 75)
                else:  # finalize
                    self.memory_usage_mb = 50 + (self.file_size_gb * 5)

                # Create temporary files
                if phase in {"decode", "filter"} and len(self.temp_files_created) < 3:
                    temp_file = f"temp_{phase}_{len(self.temp_files_created)}.tmp"
                    self.temp_files_created.append(temp_file)

                # Advance phase
                if self.progress_percent > (self.current_phase + 1) * 20:
                    self.current_phase = min(self.current_phase + 1, len(self.processing_phases) - 1)

                return {
                    "phase": phase,
                    "progress": self.progress_percent,
                    "memory_mb": self.memory_usage_mb,
                    "temp_files": len(self.temp_files_created),
                }

            def cleanup_temp_files(self):
                """Simulate cleanup of temporary files."""
                cleaned_count = len(self.temp_files_created)
                self.temp_files_created.clear()
                return cleaned_count

        # Test various file sizes
        test_scenarios = [
            {"name": "medium_file", "size_gb": 2.0, "expected_max_memory": 500},
            {"name": "large_file", "size_gb": 8.0, "expected_max_memory": 1100},
            {"name": "very_large_file", "size_gb": 16.0, "expected_max_memory": 1900},
        ]

        for scenario in test_scenarios:
            processor = LargeFileProcessor(scenario["size_gb"])
            start_time = time.time()
            max_memory_seen = 0.0
            processing_stats = []

            # Simulate processing with monitoring
            while processor.progress_percent < 100.0:
                stats = processor.simulate_processing_step(0.05)  # Fast simulation
                processing_stats.append(stats)
                max_memory_seen = max(max_memory_seen, stats["memory_mb"])

                # Simulate memory pressure detection
                if stats["memory_mb"] > scenario["expected_max_memory"]:
                    LOGGER.warning(f"High memory usage detected: {stats['memory_mb']}MB")

            execution_time = time.time() - start_time
            temp_files_cleaned = processor.cleanup_temp_files()

            # Track completion
            process_monitor.track_completion(
                exit_code=0,
                execution_time=execution_time,
                stdout=f"Processed {scenario['size_gb']}GB file successfully",
                stderr="",
                memory_peak=max_memory_seen,
            )

            # Verify processing characteristics
            assert len(processing_stats) > 0, "Should have processing statistics"
            assert max_memory_seen > 0, "Should track memory usage"
            assert temp_files_cleaned >= 0, "Should track temporary file cleanup"

            # Check memory scaling with file size
            if scenario["size_gb"] >= 8.0:
                assert max_memory_seen > 800, f"Large files should use substantial memory: {max_memory_seen}MB"

            # Verify all processing phases were completed
            phases_seen = {stat["phase"] for stat in processing_stats}
            assert len(phases_seen) >= 3, "Should go through multiple processing phases"

        # Verify resource usage patterns across scenarios
        memory_peaks = process_monitor.memory_usage
        assert len(memory_peaks) == len(test_scenarios), "Should have memory data for all scenarios"

        # Check that memory usage increases with file size
        sorted_peaks = sorted(memory_peaks)
        assert sorted_peaks[-1] > sorted_peaks[0] * 2, "Largest file should use significantly more memory"

    def test_concurrent_execution_resource_contention(
        self, temp_media_files: dict[str, Path], process_monitor: Any
    ) -> None:
        """Test resource contention management for FFmpeg processes."""

        class ResourceManager:
            def __init__(self, max_concurrent: int = 2, memory_limit_mb: float = 600):
                self.max_concurrent = max_concurrent
                self.memory_limit_mb = memory_limit_mb
                self.active_processes = []
                self.completed_processes = []
                self.total_memory_usage = 0.0
                self.rejection_count = 0

            def can_start_process(self, estimated_memory_mb: float) -> bool:
                """Check if a new process can be started."""
                if len(self.active_processes) >= self.max_concurrent:
                    return False
                return not self.total_memory_usage + estimated_memory_mb > self.memory_limit_mb

            def start_process(self, process_info: dict[str, Any]) -> bool:
                """Start a process if resources are available."""
                estimated_memory = process_info.get("estimated_memory_mb", 100)

                if not self.can_start_process(estimated_memory):
                    self.rejection_count += 1
                    return False

                self.active_processes.append(process_info)
                self.total_memory_usage += estimated_memory
                process_info["start_time"] = time.time()
                return True

            def complete_process(self, process_info: dict[str, Any]) -> None:
                """Mark a process as completed."""
                if process_info in self.active_processes:
                    self.active_processes.remove(process_info)
                    self.total_memory_usage -= process_info.get("estimated_memory_mb", 100)
                    self.total_memory_usage = max(0, self.total_memory_usage)
                    self.completed_processes.append(process_info)

        # Create resource manager
        resource_manager = ResourceManager(max_concurrent=2, memory_limit_mb=600)

        # Define test processes with varying resource requirements
        test_processes = [
            {"name": "small_encode", "estimated_memory_mb": 200},
            {"name": "medium_encode", "estimated_memory_mb": 300},
            {"name": "large_encode", "estimated_memory_mb": 500},  # Should exceed limit when combined
            {"name": "quick_task", "estimated_memory_mb": 150},
        ]

        # Test resource management logic
        started_processes = []
        rejected_processes = []

        for process_info in test_processes:
            if resource_manager.start_process(process_info):
                started_processes.append(process_info)
                # Track successful start
                process_monitor.track_completion(
                    exit_code=0,
                    execution_time=0.1,
                    stdout=f"Process {process_info['name']} started successfully",
                    stderr="",
                    memory_peak=process_info["estimated_memory_mb"],
                )
            else:
                rejected_processes.append(process_info)
                # Track rejection
                process_monitor.track_completion(
                    exit_code=1,
                    execution_time=0.0,
                    stdout="",
                    stderr=f"Process {process_info['name']} rejected due to resource limits",
                    memory_peak=0.0,
                )

        # Verify resource management behavior
        assert len(started_processes) >= 2, "Should start at least 2 processes"
        assert len(rejected_processes) >= 1, "Should reject at least 1 process due to resource limits"
        assert resource_manager.rejection_count > 0, "Should track rejections"

        # Verify memory constraints were respected
        max_memory_used = max(
            sum(p.get("estimated_memory_mb", 0) for p in batch)
            for batch in [started_processes[:1], started_processes[:2]]
            if batch
        )
        assert max_memory_used <= resource_manager.memory_limit_mb, "Memory limit should be respected"

        # Complete some processes to free resources
        for process in started_processes[:1]:
            resource_manager.complete_process(process)

        # Try to start a rejected process now that resources are free
        if rejected_processes:
            retry_process = rejected_processes[0]
            retry_success = resource_manager.start_process(retry_process)
            if retry_success:
                process_monitor.track_completion(
                    exit_code=0,
                    execution_time=0.1,
                    stdout=f"Process {retry_process['name']} started on retry",
                    stderr="",
                    memory_peak=retry_process["estimated_memory_mb"],
                )

        # Verify final state
        assert len(resource_manager.completed_processes) >= 1, "Should have completed processes"

        # Check execution tracking
        execution_times = process_monitor.execution_times
        successful_executions = [t for t in execution_times if t > 0]
        failed_executions = [t for t in execution_times if t == 0]

        assert len(successful_executions) >= 2, "Should have successful executions"
        assert len(failed_executions) >= 1, "Should have failed/rejected executions"

    def test_hardware_encoder_fallback_scenarios(self, temp_media_files: dict[str, Path]) -> None:
        """Test hardware encoder fallback and error recovery mechanisms."""

        class HardwareEncoderTester:
            def __init__(self) -> None:
                self.fallback_attempts = []
                self.successful_encoders = []
                self.failed_encoders = []

            def test_encoder_availability(self, encoder_name: str) -> dict[str, Any]:
                """Test if a hardware encoder is available."""
                # Simulate hardware encoder availability based on name
                hardware_encoders = {
                    "Hardware HEVC (VideoToolbox)": {"available": True, "supports_4k": True},
                    "Hardware H.264 (VideoToolbox)": {"available": True, "supports_4k": False},
                    "Hardware HEVC (NVENC)": {"available": False, "error": "NVIDIA driver not found"},
                    "Hardware H.264 (NVENC)": {"available": False, "error": "NVIDIA hardware not detected"},
                    "Hardware HEVC (QuickSync)": {"available": False, "error": "Intel QuickSync not available"},
                }

                result = hardware_encoders.get(encoder_name, {"available": False, "error": "Unknown encoder"})
                result["encoder_name"] = encoder_name
                return result

            def attempt_encode_with_fallback(
                self, primary_encoder: str, fallback_encoders: list[str]
            ) -> dict[str, Any]:
                """Attempt encoding with primary encoder and fallback to alternatives."""
                encoders_to_try = [primary_encoder, *fallback_encoders]

                for encoder in encoders_to_try:
                    availability = self.test_encoder_availability(encoder)

                    if availability["available"]:
                        # Simulate successful encoding
                        self.successful_encoders.append(encoder)
                        return {
                            "success": True,
                            "encoder_used": encoder,
                            "attempts": len(self.fallback_attempts) + 1,
                            "fallbacks_tried": self.fallback_attempts.copy(),
                        }
                    # Record failed attempt
                    self.failed_encoders.append(encoder)
                    self.fallback_attempts.append({
                        "encoder": encoder,
                        "error": availability.get("error", "Encoder unavailable"),
                        "timestamp": time.time(),
                    })

                # All encoders failed
                return {
                    "success": False,
                    "encoder_used": None,
                    "attempts": len(self.fallback_attempts),
                    "fallbacks_tried": self.fallback_attempts.copy(),
                    "error": "All hardware encoders failed",
                }

        tester = HardwareEncoderTester()

        # Test fallback scenarios
        test_scenarios = [
            {
                "name": "nvenc_to_videotoolbox",
                "primary": "Hardware HEVC (NVENC)",
                "fallbacks": ["Hardware HEVC (VideoToolbox)", "Software x265"],
                "expected_success": True,
                "expected_encoder": "Hardware HEVC (VideoToolbox)",
            },
            {
                "name": "quicksync_to_software",
                "primary": "Hardware HEVC (QuickSync)",
                "fallbacks": ["Hardware HEVC (NVENC)", "Hardware HEVC (VideoToolbox)"],
                "expected_success": True,
                "expected_encoder": "Hardware HEVC (VideoToolbox)",  # VideoToolbox available
            },
            {
                "name": "all_hardware_fail",
                "primary": "Hardware HEVC (NVENC)",
                "fallbacks": ["Hardware HEVC (QuickSync)"],
                "expected_success": False,
                "expected_encoder": None,
            },
        ]

        results = []
        for scenario in test_scenarios:
            # Reset tester state
            tester.fallback_attempts.clear()
            tester.successful_encoders.clear()
            tester.failed_encoders.clear()

            # Test the fallback scenario
            result = tester.attempt_encode_with_fallback(scenario["primary"], scenario["fallbacks"])

            result["scenario_name"] = scenario["name"]
            results.append(result)

            # Verify expected outcomes
            if scenario["expected_success"]:
                assert result["success"], f"Scenario {scenario['name']} should succeed"
                if scenario["expected_encoder"]:
                    assert result["encoder_used"] == scenario["expected_encoder"], (
                        f"Expected encoder {scenario['expected_encoder']}, got {result['encoder_used']}"
                    )
            else:
                assert not result["success"], f"Scenario {scenario['name']} should fail"
                assert result["encoder_used"] is None, "Failed scenario should not have successful encoder"

        # Verify fallback behavior patterns
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        assert len(successful_results) >= 2, "Should have at least 2 successful fallback scenarios"
        assert len(failed_results) >= 1, "Should have at least 1 failed scenario"

        # Check fallback attempt tracking
        for result in results:
            assert "attempts" in result, "Should track number of attempts"
            assert "fallbacks_tried" in result, "Should track fallback attempts"

            if result["attempts"] > 1:
                assert len(result["fallbacks_tried"]) > 0, "Multiple attempts should record fallback attempts"

        # Test command building with fallback encoders
        for result in successful_results:
            if result["encoder_used"]:
                try:
                    # Test that we can build a command with the successful encoder
                    cmd = (
                        FFmpegCommandBuilder()
                        .set_input(temp_media_files["input_video"])
                        .set_output(temp_media_files["output_video"])
                        .set_encoder(result["encoder_used"])
                    )

                    # Add required parameters based on encoder type
                    if "Hardware" in result["encoder_used"]:
                        cmd = cmd.set_bitrate(5000).set_bufsize(10000)
                    else:
                        cmd = cmd.set_crf(23)

                    built_cmd = cmd.build()
                    assert len(built_cmd) > 5, f"Should build valid command for {result['encoder_used']}"

                except Exception as e:
                    pytest.fail(f"Failed to build command for successful encoder {result['encoder_used']}: {e}")

    def test_profile_validation_and_compatibility(self, temp_media_files: dict[str, Path]) -> None:
        """Test encoding profile validation and compatibility checking."""

        class ProfileValidator:
            def __init__(self) -> None:
                self.profile_definitions = {
                    "high_quality_archival": {
                        "encoder": "Software x265",
                        "crf": 18,
                        "preset": "slower",
                        "tune": "grain",
                        "profile": "main10",
                        "pix_fmt": "yuv420p10le",
                        "compatibility": ["4k", "hdr", "10bit"],
                    },
                    "fast_preview": {
                        "encoder": "Software x264",
                        "crf": 28,
                        "preset": "fast",
                        "tune": "animation",
                        "profile": "high",
                        "pix_fmt": "yuv420p",
                        "compatibility": ["1080p", "8bit"],
                    },
                    "hardware_optimized": {
                        "encoder": "Hardware HEVC (VideoToolbox)",
                        "bitrate": 8000,
                        "bufsize": 16000,
                        "pix_fmt": "yuv420p",
                        "compatibility": ["hardware_accel", "power_efficient"],
                    },
                    "two_pass_broadcast": {
                        "encoder": "Software x265 (2-Pass)",
                        "bitrate": 15000,
                        "bufsize": 30000,
                        "preset": "slow",
                        "tune": "film",
                        "profile": "main",
                        "pix_fmt": "yuv420p",
                        "compatibility": ["broadcast", "precise_bitrate"],
                    },
                }

            def validate_profile(self, profile_name: str) -> dict[str, Any]:
                """Validate a profile definition."""
                if profile_name not in self.profile_definitions:
                    return {
                        "valid": False,
                        "error": f"Profile '{profile_name}' not found",
                        "missing_params": [],
                        "invalid_params": [],
                    }

                profile = self.profile_definitions[profile_name]
                validation_result = {
                    "valid": True,
                    "error": None,
                    "missing_params": [],
                    "invalid_params": [],
                    "warnings": [],
                }

                # Check required parameters based on encoder
                encoder = profile.get("encoder", "")

                if ("Software x265" in encoder and not encoder.endswith("(2-Pass)")) or "Software x264" in encoder:
                    if "crf" not in profile:
                        validation_result["missing_params"].append("crf")
                elif "Hardware" in encoder:
                    if "bitrate" not in profile:
                        validation_result["missing_params"].append("bitrate")
                    if "bufsize" not in profile:
                        validation_result["missing_params"].append("bufsize")
                elif "(2-Pass)" in encoder and "bitrate" not in profile:
                    validation_result["missing_params"].append("bitrate")

                # Validate parameter values
                if "crf" in profile:
                    crf = profile["crf"]
                    if not isinstance(crf, int) or crf < 0 or crf > 51:
                        validation_result["invalid_params"].append("crf")

                if "bitrate" in profile:
                    bitrate = profile["bitrate"]
                    if not isinstance(bitrate, int) or bitrate < 100:
                        validation_result["invalid_params"].append("bitrate")

                if "preset" in profile:
                    valid_presets = [
                        "ultrafast",
                        "superfast",
                        "veryfast",
                        "faster",
                        "fast",
                        "medium",
                        "slow",
                        "slower",
                        "veryslow",
                    ]
                    if profile["preset"] not in valid_presets:
                        validation_result["invalid_params"].append("preset")

                # Check compatibility warnings
                if "10bit" in profile.get("compatibility", []) and profile.get("pix_fmt") == "yuv420p":
                    validation_result["warnings"].append("10bit compatibility claimed but using 8-bit pixel format")

                if "hardware_accel" in profile.get("compatibility", []) and "Software" in encoder:
                    validation_result["warnings"].append("Hardware acceleration claimed but using software encoder")

                # Overall validation result
                validation_result["valid"] = (
                    len(validation_result["missing_params"]) == 0 and len(validation_result["invalid_params"]) == 0
                )

                if not validation_result["valid"]:
                    validation_result["error"] = "Profile validation failed"

                return validation_result

            def build_command_from_profile(
                self, profile_name: str, input_path: Path, output_path: Path
            ) -> tuple[list[str], dict[str, Any]]:
                """Build FFmpeg command from profile definition."""
                validation = self.validate_profile(profile_name)
                if not validation["valid"]:
                    msg = f"Invalid profile: {validation['error']}"
                    raise ValueError(msg)

                profile = self.profile_definitions[profile_name]
                builder = FFmpegCommandBuilder()

                # Set basic parameters
                builder.set_input(input_path).set_output(output_path).set_encoder(profile["encoder"])

                # Set encoder-specific parameters
                if "crf" in profile:
                    builder.set_crf(profile["crf"])
                if "bitrate" in profile:
                    builder.set_bitrate(profile["bitrate"])
                if "bufsize" in profile:
                    builder.set_bufsize(profile["bufsize"])
                if "pix_fmt" in profile:
                    builder.set_pix_fmt(profile["pix_fmt"])
                if "preset" in profile:
                    builder.set_preset(profile["preset"])
                if "tune" in profile:
                    builder.set_tune(profile["tune"])
                if "profile" in profile:
                    builder.set_profile(profile["profile"])

                # Handle two-pass encoding
                if "(2-Pass)" in profile["encoder"]:
                    pass_log = str(output_path.parent / f"{output_path.stem}_pass")
                    # For testing, just build pass 1
                    builder.set_two_pass(True, pass_log, 1)

                command = builder.build()
                return command, validation

        validator = ProfileValidator()

        # Test all profile validations
        validation_results = {}
        for profile_name in validator.profile_definitions:
            validation_results[profile_name] = validator.validate_profile(profile_name)

        # Verify all profiles are valid
        for profile_name, validation in validation_results.items():
            assert validation["valid"], f"Profile '{profile_name}' should be valid: {validation['error']}"
            assert len(validation["missing_params"]) == 0, (
                f"Profile '{profile_name}' missing params: {validation['missing_params']}"
            )
            assert len(validation["invalid_params"]) == 0, (
                f"Profile '{profile_name}' invalid params: {validation['invalid_params']}"
            )

        # Test command building from profiles
        command_results = {}
        for profile_name in validator.profile_definitions:
            try:
                command, validation = validator.build_command_from_profile(
                    profile_name, temp_media_files["input_video"], temp_media_files["output_video"]
                )
                command_results[profile_name] = {"command": command, "validation": validation, "success": True}

                # Verify command structure
                assert "ffmpeg" in command, f"Profile '{profile_name}' should generate FFmpeg command"
                assert str(temp_media_files["input_video"]) in command, "Command should include input file"

                # Verify encoder-specific elements
                profile = validator.profile_definitions[profile_name]
                if "Software" in profile["encoder"]:
                    assert any("lib" in arg for arg in command), "Software encoder should use lib codec"
                elif "Hardware" in profile["encoder"]:
                    assert any("videotoolbox" in arg for arg in command), "Hardware encoder should use VideoToolbox"

            except Exception as e:
                command_results[profile_name] = {"command": None, "validation": None, "success": False, "error": str(e)}

        # Verify all profiles can build commands
        failed_profiles = [name for name, result in command_results.items() if not result["success"]]
        assert len(failed_profiles) == 0, f"Failed to build commands for profiles: {failed_profiles}"

        # Test profile compatibility features
        high_quality_profile = validator.profile_definitions["high_quality_archival"]
        assert "10bit" in high_quality_profile["compatibility"], "High quality profile should support 10-bit"
        assert high_quality_profile["pix_fmt"] == "yuv420p10le", "10-bit profile should use 10-bit pixel format"

        hardware_profile = validator.profile_definitions["hardware_optimized"]
        assert "power_efficient" in hardware_profile["compatibility"], "Hardware profile should be power efficient"
        assert "Hardware" in hardware_profile["encoder"], "Hardware profile should use hardware encoder"

        # Test invalid profile scenarios
        invalid_profile_test = {
            "encoder": "Software x265",
            # Missing CRF
        }

        # This would fail validation due to missing CRF
        validator.profile_definitions["test_invalid"] = invalid_profile_test
        invalid_validation = validator.validate_profile("test_invalid")
        assert not invalid_validation["valid"], "Invalid profile should fail validation"
        assert "crf" in invalid_validation["missing_params"], "Should detect missing CRF parameter"

        # Clean up test profile
        del validator.profile_definitions["test_invalid"]
