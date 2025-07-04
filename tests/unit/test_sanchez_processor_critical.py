"""Critical scenario tests for Sanchez Processor Integration.

This test suite covers high-priority missing areas identified in the testing gap analysis:
1. End-to-end processing workflows with various image types
2. Failure handling and recovery scenarios
3. Resource cleanup under error conditions
4. Memory management with large images
5. Process timeout and cancellation
6. File I/O error handling
7. Performance under concurrent processing
"""

import gc
from pathlib import Path
import tempfile
import time
from typing import Any
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import pytest

from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.sanchez_processor import SanchezProcessor


class TestSanchezProcessorCritical:
    """Critical scenario tests for Sanchez processor integration."""

    @pytest.fixture()
    def temp_dir(self) -> Any:
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture()
    def image_test_generator(self) -> Any:
        """Generate test images of various types and sizes."""

        class ImageTestGenerator:
            @staticmethod
            def create_test_image_data(
                width: int, height: int, channels: int = 1, dtype: type = np.uint8, source_path: str = "test_image.png"
            ) -> ImageData:
                """Create test ImageData with specified parameters."""
                # Generate test image based on channels
                if channels == 1:
                    # Grayscale
                    data = np.random.randint(0, 256, (height, width), dtype=dtype)
                elif channels == 3:
                    # RGB
                    data = np.random.randint(0, 256, (height, width, 3), dtype=dtype)
                else:
                    # Multi-channel
                    data = np.random.randint(0, 256, (height, width, channels), dtype=dtype)

                return ImageData(
                    image_data=data,
                    source_path=source_path,
                    metadata={
                        "width": width,
                        "height": height,
                        "channels": channels,
                        "dtype": str(dtype),
                        "test_image": True,
                    },
                )

            @staticmethod
            def create_float_image_data(width: int, height: int) -> ImageData:
                """Create test ImageData with float values (0-1 range)."""
                data = np.random.random((height, width)).astype(np.float32)
                return ImageData(image_data=data, source_path="float_test.png", metadata={"float_image": True})

            @staticmethod
            def create_pil_image_data(width: int, height: int) -> ImageData:
                """Create test ImageData with PIL Image."""
                pil_img = Image.new("L", (width, height), color=128)
                return ImageData(image_data=pil_img, source_path="pil_test.png", metadata={"pil_image": True})

            @staticmethod
            def create_corrupted_image_data() -> ImageData:
                """Create test ImageData with corrupted/invalid data."""
                # Invalid shape
                data = np.array([1, 2, 3])  # 1D array
                return ImageData(image_data=data, source_path="corrupted.png", metadata={"corrupted": True})

        return ImageTestGenerator()

    @pytest.fixture()
    def progress_tracker(self) -> Any:
        """Create progress tracking mock for tests."""

        class ProgressTracker:
            def __init__(self) -> None:
                self.calls: list[tuple[str, float]] = []
                self.current_progress = 0.0
                self.current_message = ""

            def __call__(self, message: str, progress: float):
                self.calls.append((message, progress))
                self.current_message = message
                self.current_progress = progress

            def reset(self) -> None:
                self.calls.clear()
                self.current_progress = 0.0
                self.current_message = ""

        return ProgressTracker()

    def test_end_to_end_processing_workflow(
        self, temp_dir: Path, image_test_generator: Any, progress_tracker: Any
    ) -> None:
        """Test complete end-to-end processing workflow with various image types."""
        processor = SanchezProcessor(temp_dir, progress_tracker)

        # Test cases with different image types
        test_cases = [
            ("grayscale_uint8", image_test_generator.create_test_image_data(100, 100, 1, np.uint8)),
            ("rgb_uint8", image_test_generator.create_test_image_data(100, 100, 3, np.uint8)),
            ("float32", image_test_generator.create_float_image_data(100, 100)),
            ("pil_image", image_test_generator.create_pil_image_data(100, 100)),
        ]

        for _test_name, image_data in test_cases:
            progress_tracker.reset()

            # Mock the Sanchez colourise function to avoid requiring actual binary
            with patch("goesvfi.pipeline.sanchez_processor.colourise") as mock_colourise, \
                 patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                # Mock the colourise function to create the output file it expects
                def mock_colourise_func(input_path, output_path, **kwargs):
                    # Create the expected output file
                    Path(output_path).touch()
                    return Path(output_path)

                mock_colourise.side_effect = mock_colourise_func

                # Mock PIL Image loading for the result
                with patch("PIL.Image.open") as mock_pil_open:
                    # Create mock PIL image result
                    mock_result_img = Mock()
                    mock_result_img.size = (100, 100)
                    mock_pil_open.return_value = mock_result_img

                    # Mock numpy array conversion
                    result_array = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
                    with patch("numpy.array", return_value=result_array):
                        # Process the image
                        result = processor.process(image_data, res_km=4)

                        # Verify processing completed
                        assert isinstance(result, ImageData)
                        assert result.metadata["processed_by"] == "sanchez"
                        assert result.metadata["sanchez_res_km"] == 4
                        assert "processing_time" in result.metadata

                        # Verify progress was tracked
                        assert len(progress_tracker.calls) > 0
                        assert progress_tracker.current_progress == 1.0
                        assert "completed" in progress_tracker.current_message.lower()

                        # Verify colourise was called
                        mock_colourise.assert_called_once()

    def test_processing_failure_recovery(
        self, temp_dir: Path, image_test_generator: Any, progress_tracker: Any
    ) -> None:
        """Test failure handling and recovery scenarios."""
        processor = SanchezProcessor(temp_dir, progress_tracker)
        image_data = image_test_generator.create_test_image_data(50, 50)

        # Test various failure scenarios
        failure_scenarios = [
            ("colourise_subprocess_error", RuntimeError("Sanchez execution failed")),
            ("colourise_file_not_found", FileNotFoundError("Sanchez binary not found")),
            ("colourise_permission_error", PermissionError("Permission denied")),
            ("colourise_timeout", OSError("Operation timed out")),
        ]

        for _scenario_name, exception in failure_scenarios:
            progress_tracker.reset()

            with patch("goesvfi.pipeline.sanchez_processor.colourise") as mock_colourise, \
                 patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                mock_colourise.side_effect = exception

                # Process should handle error gracefully and return original image
                result = processor.process(image_data)

                # Should return image data with failure metadata when processing fails
                assert result.source_path == image_data.source_path
                assert np.array_equal(result.image_data, image_data.image_data)
                assert result.metadata["processed_by"] == "sanchez"
                assert result.metadata.get("processing_failed") is True

                # Verify error was logged and progress callback was notified
                assert len(progress_tracker.calls) > 0
                final_message = progress_tracker.calls[-1][0]
                assert "failed" in final_message.lower()

    def test_resource_cleanup_under_errors(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test that temporary files are cleaned up even when errors occur."""
        processor = SanchezProcessor(temp_dir)
        image_data = image_test_generator.create_test_image_data(50, 50)

        temp_files_created = []
        original_save = Image.Image.save

        def track_temp_files(self, fp, format=None, **params):
            """Track temporary files as they're created."""
            if hasattr(fp, "__fspath__") or isinstance(fp, str | Path):
                file_path = Path(fp)
                if file_path.parent == temp_dir:
                    temp_files_created.append(file_path)
            return original_save(self, fp, format, **params)

        with patch.object(Image.Image, "save", track_temp_files):
            with patch("goesvfi.pipeline.sanchez_processor.colourise") as mock_colourise, \
                 patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                # Make colourise fail after input file is created
                mock_colourise.side_effect = RuntimeError("Processing failed")

                # Process image (should fail but clean up)
                result = processor.process(image_data)

                # Should return image data with failure metadata due to failure
                assert result.source_path == image_data.source_path
                assert np.array_equal(result.image_data, image_data.image_data)
                assert result.metadata["processed_by"] == "sanchez"
                assert result.metadata.get("processing_failed") is True

                # Verify temporary files were cleaned up
                for temp_file in temp_files_created:
                    assert not temp_file.exists(), f"Temporary file not cleaned up: {temp_file}"

    def test_memory_management_large_images(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test memory management with large images."""
        processor = SanchezProcessor(temp_dir)

        # Create moderately large image (avoid memory issues)
        large_image_data = image_test_generator.create_test_image_data(500, 500, 3, np.uint8)

        with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
            # Create fake output
            fake_output = temp_dir / "large_output.png"
            fake_output.touch()

            with patch("PIL.Image.open") as mock_pil_open:
                # Mock large result image
                mock_result_img = Mock()
                mock_result_img.size = (500, 500)
                mock_pil_open.return_value = mock_result_img

                # Large result array
                large_result = np.random.randint(0, 256, (500, 500, 3), dtype=np.uint8)

                with patch("numpy.array", return_value=large_result):
                    # Measure memory before processing
                    gc.collect()

                    # Process large image
                    result = processor.process(large_image_data)

                    # Verify processing succeeded
                    assert isinstance(result, ImageData)
                    assert result.metadata["processed_by"] == "sanchez"

                    # Force garbage collection
                    gc.collect()

    def test_concurrent_processing_stress(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test concurrent processing scenarios."""
        import concurrent.futures
        import threading

        results = []
        errors = []
        lock = threading.Lock()

        def process_image(processor_id: int) -> None:
            """Process an image concurrently."""
            try:
                # Each processor gets its own temp directory to avoid conflicts
                proc_temp_dir = temp_dir / f"proc_{processor_id}"
                proc_temp_dir.mkdir(exist_ok=True)

                processor = SanchezProcessor(proc_temp_dir)
                image_data = image_test_generator.create_test_image_data(50, 50, 1, np.uint8)

                with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                    fake_output = proc_temp_dir / f"output_{processor_id}.png"
                    fake_output.touch()

                    with patch("PIL.Image.open") as mock_pil_open:
                        mock_result_img = Mock()
                        mock_result_img.size = (50, 50)
                        mock_pil_open.return_value = mock_result_img

                        result_array = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)

                        with patch("numpy.array", return_value=result_array):
                            start_time = time.time()
                            result = processor.process(image_data)
                            end_time = time.time()

                            with lock:
                                results.append({
                                    "processor_id": processor_id,
                                    "processing_time": end_time - start_time,
                                    "success": isinstance(result, ImageData),
                                })

            except Exception as e:
                with lock:
                    errors.append((processor_id, str(e)))

        # Process images concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_image, i) for i in range(6)]
            concurrent.futures.wait(futures)

        # Verify results
        assert len(errors) == 0, f"Concurrent processing errors: {errors}"
        assert len(results) == 6, f"Expected 6 results, got {len(results)}"

        # All should have succeeded
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) == 6, "All concurrent processes should succeed"

    def test_image_format_conversion_edge_cases(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test edge cases in image format conversion."""
        processor = SanchezProcessor(temp_dir)

        # Test cases with different data types and shapes
        edge_cases: list[tuple[str, np.ndarray]] = [
            ("3d_single_channel", np.random.randint(0, 256, (50, 50, 1), dtype=np.uint8)),
            ("float64_range", np.random.random((50, 50)).astype(np.float64)),
            ("int16_data", np.random.randint(-100, 100, (50, 50), dtype=np.int16)),
            ("large_values", np.random.randint(0, 65536, (50, 50), dtype=np.uint16)),
        ]

        for case_name, test_array in edge_cases:
            image_data = ImageData(
                image_data=test_array, source_path=f"{case_name}.png", metadata={"test_case": case_name}
            )

            with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                fake_output = temp_dir / f"{case_name}_output.png"
                fake_output.touch()

                with patch("PIL.Image.open") as mock_pil_open:
                    mock_result_img = Mock()
                    mock_result_img.size = (50, 50)
                    mock_pil_open.return_value = mock_result_img

                    result_array = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)

                    with patch("numpy.array", return_value=result_array):
                        # Should handle conversion without errors
                        result = processor.process(image_data)

                        # Verify processing completed (or gracefully failed)
                        assert isinstance(result, ImageData)

    def test_progress_callback_accuracy(self, temp_dir: Path, image_test_generator: Any, progress_tracker: Any) -> None:
        """Test accuracy and consistency of progress reporting."""
        processor = SanchezProcessor(temp_dir, progress_tracker)
        image_data = image_test_generator.create_test_image_data(100, 100)

        with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
            fake_output = temp_dir / "progress_test.png"
            fake_output.touch()

            with patch("PIL.Image.open") as mock_pil_open:
                mock_result_img = Mock()
                mock_result_img.size = (100, 100)
                mock_pil_open.return_value = mock_result_img

                result_array = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

                with patch("numpy.array", return_value=result_array):
                    processor.process(image_data)

        # Verify progress reporting characteristics
        assert len(progress_tracker.calls) > 0, "Progress should be reported"

        # Check progress values are monotonically increasing
        progress_values = [call[1] for call in progress_tracker.calls]
        for i in range(len(progress_values) - 1):
            assert progress_values[i] <= progress_values[i + 1], "Progress values should be monotonically increasing"

        # Check progress starts at 0 and ends at 1
        assert progress_values[0] == 0.0, "Progress should start at 0.0"
        assert progress_values[-1] == 1.0, "Progress should end at 1.0"

        # Check all progress values are in valid range
        for progress in progress_values:
            assert 0.0 <= progress <= 1.0, f"Progress value {progress} out of range"

    def test_file_io_error_scenarios(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test handling of various file I/O error scenarios."""
        processor = SanchezProcessor(temp_dir)
        image_data = image_test_generator.create_test_image_data(50, 50)

        # Test scenarios where file operations fail
        io_error_scenarios = [
            ("input_save_permission_error", "save", PermissionError("Cannot write input file")),
            ("input_save_disk_full", "save", OSError("No space left on device")),
            ("output_load_missing", "open", FileNotFoundError("Output file not created")),
            ("output_load_corrupted", "open", OSError("Cannot identify image file")),
        ]

        for scenario_name, method_to_patch, exception in io_error_scenarios:
            with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
                fake_output = temp_dir / f"{scenario_name}_output.png"
                fake_output.touch()

                if method_to_patch == "save":
                    # Mock PIL save to raise error
                    with patch("PIL.Image.Image.save", side_effect=exception):
                        result = processor.process(image_data)
                        # Should return image data with failure metadata when save fails
                        assert result.source_path == image_data.source_path
                        assert np.array_equal(result.image_data, image_data.image_data)
                        assert result.metadata["processed_by"] == "sanchez"
                        assert result.metadata.get("processing_failed") is True

                elif method_to_patch == "open":
                    # Mock PIL open to raise error
                    with patch("PIL.Image.open", side_effect=exception):
                        result = processor.process(image_data)
                        # Should return image data with failure metadata when loading output fails
                        assert result.source_path == image_data.source_path
                        assert np.array_equal(result.image_data, image_data.image_data)
                        assert result.metadata["processed_by"] == "sanchez"
                        assert result.metadata.get("processing_failed") is True

    def test_temp_directory_management(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test temporary directory creation and management."""
        # Test with non-existent temp directory
        non_existent_dir = temp_dir / "non_existent"
        processor = SanchezProcessor(non_existent_dir)

        # Directory should be created during initialization
        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()

        # Test processing works with created directory
        image_data = image_test_generator.create_test_image_data(50, 50)

        with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
            fake_output = non_existent_dir / "test_output.png"
            fake_output.touch()

            with patch("PIL.Image.open") as mock_pil_open:
                mock_result_img = Mock()
                mock_result_img.size = (50, 50)
                mock_pil_open.return_value = mock_result_img

                result_array = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)

                with patch("numpy.array", return_value=result_array):
                    result = processor.process(image_data)
                    assert isinstance(result, ImageData)

    def test_metadata_preservation_and_enhancement(self, temp_dir: Path, image_test_generator: Any) -> None:
        """Test that original metadata is preserved and enhanced."""
        processor = SanchezProcessor(temp_dir)

        # Create image data with rich metadata
        original_metadata = {
            "satellite": "GOES-18",
            "band": 13,
            "timestamp": "2024-01-15T12:00:00Z",
            "resolution": "2km",
            "custom_field": "test_value",
        }

        image_data = ImageData(
            image_data=np.random.randint(0, 256, (50, 50), dtype=np.uint8),
            source_path="test_metadata.png",
            metadata=original_metadata,
        )

        with patch("goesvfi.pipeline.sanchez_processor.colourise"), \
             patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor._is_valid_satellite_image", return_value=True):
            fake_output = temp_dir / "metadata_test.png"
            fake_output.touch()

            # Mock Path.exists to return True for any output file
            with patch("pathlib.Path.exists", return_value=True):
                with patch("PIL.Image.open") as mock_pil_open:
                    mock_result_img = Mock()
                    mock_result_img.size = (50, 50)
                    mock_pil_open.return_value = mock_result_img

                    result_array = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)

                    with patch("numpy.array", return_value=result_array):
                        result = processor.process(image_data, res_km=8)

        # Verify original metadata is preserved
        for key, value in original_metadata.items():
            assert result.metadata[key] == value, f"Original metadata {key} not preserved"

        # Verify Sanchez-specific metadata is added
        assert result.metadata["processed_by"] == "sanchez"
        assert result.metadata["sanchez_res_km"] == 8
        assert "processing_time" in result.metadata
        assert "width" in result.metadata
        assert "height" in result.metadata
        assert "channels" in result.metadata

    def test_interface_compliance(self, temp_dir: Path) -> None:
        """Test compliance with ImageProcessor interface."""
        processor = SanchezProcessor(temp_dir)

        # Test that unimplemented methods raise NotImplementedError
        dummy_image_data = ImageData(image_data=np.zeros((10, 10)), source_path="dummy.png", metadata={})

        with pytest.raises(NotImplementedError, match="does not implement load"):
            processor.load("test_path")

        with pytest.raises(NotImplementedError, match="does not implement crop"):
            processor.crop(dummy_image_data, (0, 0, 10, 10))

        with pytest.raises(NotImplementedError, match="does not implement save"):
            processor.save(dummy_image_data, "test_path")

        # Test that process_image is an alias for process
        with patch.object(processor, "process") as mock_process:
            mock_process.return_value = dummy_image_data

            result = processor.process_image(dummy_image_data, test_param="value")

            mock_process.assert_called_once_with(dummy_image_data, test_param="value")
            assert result is dummy_image_data
