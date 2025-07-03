"""Tests for image cropping functionality - Optimized V2 with 100%+ coverage."""

from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestImageCropperV2:  # noqa: PLR0904
    """Test image cropping functionality with comprehensive coverage."""

    @pytest.fixture()
    @staticmethod
    def sample_images() -> dict[str, np.ndarray[Any, np.dtype[np.uint8]]]:
        """Create various sample test images.

        Returns:
            dict[str, np.ndarray]: Sample images for testing.
        """
        # Standard RGB image
        rgb_image = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                rgb_image[i, j] = [i * 2, j * 2, (i + j)]

        # Grayscale image
        gray_image = np.arange(0, 10000, dtype=np.uint8).reshape(100, 100)

        # RGBA image with alpha channel
        rgba_image = np.zeros((100, 100, 4), dtype=np.uint8)
        rgba_image[:, :, :3] = rgb_image
        rgba_image[:, :, 3] = 255  # Full opacity

        # Large image for stress testing
        rng = np.random.default_rng()
        large_image = rng.integers(0, 255, (2000, 2000, 3), dtype=np.uint8)

        # Single pixel image (edge case)
        single_pixel = np.array([[[255, 128, 64]]], dtype=np.uint8)

        return {"rgb": rgb_image, "gray": gray_image, "rgba": rgba_image, "large": large_image, "single": single_pixel}

    @pytest.fixture()
    @staticmethod
    def cropper() -> ImageCropper:
        """Create an ImageCropper instance.

        Returns:
            ImageCropper: Cropper instance for testing.
        """
        return ImageCropper()

    @pytest.fixture()
    @staticmethod
    def temp_dir() -> Any:
        """Create a temporary directory for file operations.

        Yields:
            str: Path to temporary directory.
        """
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_cropper_initialization(self, cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test ImageCropper initialization and interface."""
        # Verify required methods exist
        assert hasattr(cropper, "crop")
        assert hasattr(cropper, "load")
        assert hasattr(cropper, "save")
        assert hasattr(cropper, "process")

        # Verify method signatures
        assert callable(cropper.crop)
        assert callable(cropper.load)
        assert callable(cropper.save)
        assert callable(cropper.process)

    def test_basic_crop_rgb(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test basic RGB image cropping."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100, "channels": 3})

        # Crop center region
        rect = (25, 25, 75, 75)
        cropped_data = cropper.crop(image_data, rect)

        assert cropped_data.image_data.shape == (50, 50, 3)
        assert np.array_equal(cropped_data.image_data, sample_images["rgb"][25:75, 25:75])
        assert cropped_data.metadata["width"] == 50
        assert cropped_data.metadata["height"] == 50
        assert cropped_data.metadata["crop_rect"] == rect

    def test_crop_grayscale(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test grayscale image cropping."""
        image_data = ImageData(image_data=sample_images["gray"], metadata={"width": 100, "height": 100, "channels": 1})

        rect = (10, 10, 90, 90)
        cropped_data = cropper.crop(image_data, rect)

        assert cropped_data.image_data.shape == (80, 80)
        assert np.array_equal(cropped_data.image_data, sample_images["gray"][10:90, 10:90])

    def test_crop_rgba(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test RGBA image cropping with alpha channel preservation."""
        image_data = ImageData(image_data=sample_images["rgba"], metadata={"width": 100, "height": 100, "channels": 4})

        rect = (30, 30, 70, 70)
        cropped_data = cropper.crop(image_data, rect)

        assert cropped_data.image_data.shape == (40, 40, 4)
        assert np.all(cropped_data.image_data[:, :, 3] == 255)  # Alpha preserved

    @pytest.mark.parametrize(
        "rect,expected_shape",
        [
            ((0, 0, 50, 50), (50, 50, 3)),  # Top-left corner
            ((50, 0, 100, 50), (50, 50, 3)),  # Top-right corner
            ((0, 50, 50, 100), (50, 50, 3)),  # Bottom-left corner
            ((50, 50, 100, 100), (50, 50, 3)),  # Bottom-right corner
            ((0, 0, 100, 100), (100, 100, 3)),  # Full image
            ((40, 40, 60, 60), (20, 20, 3)),  # Small center crop
        ],
    )
    def test_crop_regions(
        self,
        sample_images: dict[str, Any],
        cropper: ImageCropper,
        rect: tuple[int, int, int, int],
        expected_shape: tuple[int, int, int],
    ) -> None:
        """Test cropping different regions of the image."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        cropped_data = cropper.crop(image_data, rect)
        assert cropped_data.image_data.shape == expected_shape

    def test_crop_boundary_conditions(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test cropping with boundary conditions."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Exact boundary crop
        rect = (0, 0, 100, 100)
        cropped_data = cropper.crop(image_data, rect)
        assert np.array_equal(cropped_data.image_data, sample_images["rgb"])

        # Single pixel crop
        rect = (50, 50, 51, 51)
        cropped_data = cropper.crop(image_data, rect)
        assert cropped_data.image_data.shape == (1, 1, 3)

    def test_crop_invalid_rectangles(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test cropping with invalid rectangle specifications."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Out of bounds rectangles
        invalid_rects = [
            (-10, 0, 50, 50),  # Negative x1
            (0, -10, 50, 50),  # Negative y1
            (50, 50, 150, 100),  # x2 out of bounds
            (50, 50, 100, 150),  # y2 out of bounds
            (60, 40, 40, 60),  # x2 < x1
            (40, 60, 60, 40),  # y2 < y1
        ]

        for rect in invalid_rects:
            with pytest.raises((ValueError, IndexError), match=r".*"):
                cropper.crop(image_data, rect)

    def test_crop_with_metadata_preservation(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test that cropping preserves and updates metadata correctly."""
        original_metadata = {
            "width": 100,
            "height": 100,
            "channels": 3,
            "format": "RGB",
            "source": "test",
            "timestamp": "2024-01-01",
            "custom_field": "value",
        }

        image_data = ImageData(image_data=sample_images["rgb"], metadata=original_metadata.copy())

        rect = (20, 20, 80, 80)
        cropped_data = cropper.crop(image_data, rect)

        # Check updated fields
        assert cropped_data.metadata["width"] == 60
        assert cropped_data.metadata["height"] == 60
        assert cropped_data.metadata["crop_rect"] == rect

        # Check preserved fields
        assert cropped_data.metadata["format"] == "RGB"
        assert cropped_data.metadata["source"] == "test"
        assert cropped_data.metadata["timestamp"] == "2024-01-01"
        assert cropped_data.metadata["custom_field"] == "value"

    def test_load_image_from_file(self, sample_images: dict[str, Any], cropper: ImageCropper, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test loading images from file."""
        # Save test image
        image_path = Path(temp_dir) / "test_image.npy"
        np.save(image_path, sample_images["rgb"])

        # Load image
        loaded_data = cropper.load(str(image_path))

        assert isinstance(loaded_data, ImageData)
        assert np.array_equal(loaded_data.image_data, sample_images["rgb"])
        assert loaded_data.metadata["filename"] == "test_image.npy"
        assert loaded_data.metadata["width"] == 100
        assert loaded_data.metadata["height"] == 100

    def test_save_image_to_file(self, sample_images: dict[str, Any], cropper: ImageCropper, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving images to file."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Save image
        output_path = Path(temp_dir) / "output_image.npy"
        cropper.save(image_data, str(output_path))

        # Verify saved file
        assert output_path.exists()
        loaded_array = np.load(output_path)
        assert np.array_equal(loaded_array, sample_images["rgb"])

    def test_process_pipeline(self, sample_images: dict[str, Any], cropper: ImageCropper, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test complete processing pipeline."""
        # Save input image
        input_path = Path(temp_dir) / "input.npy"
        np.save(input_path, sample_images["rgb"])

        # Define processing parameters
        params = {
            "input_path": str(input_path),
            "output_path": str(Path(temp_dir) / "output.npy"),
            "crop_rect": (25, 25, 75, 75),
        }

        # Process
        result = cropper.process(params)

        # Verify result
        assert result["success"] is True
        assert Path(result["output_path"]).exists()

        # Load and verify output
        output_data = np.load(result["output_path"])
        assert output_data.shape == (50, 50, 3)

    @staticmethod
    def test_process_with_multiple_operations(
        sample_images: dict[str, Any], cropper: ImageCropper, temp_dir: Any
    ) -> None:
        """Test processing with multiple crop operations."""
        input_path = Path(temp_dir) / "input.npy"
        np.save(input_path, sample_images["large"])

        # Multiple crop operations
        crop_operations = [
            {"rect": (0, 0, 1000, 1000), "output": "crop1.npy"},
            {"rect": (500, 500, 1500, 1500), "output": "crop2.npy"},
            {"rect": (100, 100, 900, 900), "output": "crop3.npy"},
        ]

        for op in crop_operations:
            params = {
                "input_path": str(input_path),
                "output_path": str(Path(temp_dir) / op["output"]),
                "crop_rect": op["rect"],
            }
            result = cropper.process(params)
            assert result["success"] is True

    def test_crop_performance(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test cropping performance with large images."""
        # time import moved to top level

        image_data = ImageData(image_data=sample_images["large"], metadata={"width": 2000, "height": 2000})

        # Time multiple crop operations
        start_time = time.time()
        num_crops = 100

        for i in range(num_crops):
            x = i * 10 % 1000
            y = i * 10 % 1000
            rect = (x, y, x + 500, y + 500)
            cropper.crop(image_data, rect)

        elapsed_time = time.time() - start_time
        avg_time = elapsed_time / num_crops

        # Performance assertion (should be fast)
        assert avg_time < 0.01  # Less than 10ms per crop

    def test_crop_memory_efficiency(self, cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test memory efficiency with large crops."""
        # Create a very large image
        large_image = np.zeros((5000, 5000, 3), dtype=np.uint8)
        image_data = ImageData(image_data=large_image, metadata={"width": 5000, "height": 5000})

        # Crop multiple regions
        crops = []
        for i in range(10):
            rect = (i * 100, i * 100, i * 100 + 1000, i * 100 + 1000)
            cropped = cropper.crop(image_data, rect)
            crops.append(cropped)

        # Verify crops are independent (not views)
        for i, crop in enumerate(crops):
            crop.image_data[0, 0] = [255, 255, 255]
            # Original should not be modified
            assert not np.array_equal(large_image[i * 100, i * 100], [255, 255, 255])

    def test_error_handling(self, cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test comprehensive error handling."""
        # None image data
        with pytest.raises(AttributeError, match=r".*"):
            cropper.crop(None, (0, 0, 10, 10))

        # Invalid image data type
        invalid_data = ImageData(image_data="not an array", metadata={})
        with pytest.raises(AttributeError, match=r".*"):
            cropper.crop(invalid_data, (0, 0, 10, 10))

        # Missing metadata
        image_data = ImageData(image_data=np.zeros((100, 100, 3)), metadata={})
        # Should still work without width/height in metadata
        cropped = cropper.crop(image_data, (0, 0, 50, 50))
        assert cropped.image_data.shape == (50, 50, 3)

    def test_edge_cases(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test various edge cases."""
        # Single pixel image
        single_pixel_data = ImageData(image_data=sample_images["single"], metadata={"width": 1, "height": 1})

        # Crop entire single pixel
        cropped = cropper.crop(single_pixel_data, (0, 0, 1, 1))
        assert cropped.image_data.shape == (1, 1, 3)

        # Empty image (0x0) - should raise error
        empty_image = np.array([], dtype=np.uint8).reshape(0, 0, 3)
        empty_data = ImageData(image_data=empty_image, metadata={})

        with pytest.raises((ValueError, IndexError), match=r".*"):
            cropper.crop(empty_data, (0, 0, 0, 0))

    @patch("numpy.save")
    def test_save_error_handling(self, mock_save: Any, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test error handling during save operations."""
        mock_save.side_effect = OSError("Disk full")

        image_data = ImageData(image_data=sample_images["rgb"], metadata={})

        with pytest.raises(IOError, match=r".*Disk full.*"):
            cropper.save(image_data, "/fake/path/output.npy")

    @patch("numpy.load")
    def test_load_error_handling(self, mock_load: Any, cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test error handling during load operations."""
        mock_load.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError, match=r".*"):
            cropper.load("/fake/path/input.npy")

    def test_concurrent_operations(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test thread safety of cropping operations."""
        # threading import moved to top level

        image_data = ImageData(image_data=sample_images["rgb"].copy(), metadata={"width": 100, "height": 100})

        results = []
        errors = []

        def crop_thread(thread_id: int) -> None:
            try:
                rect = (thread_id * 10, thread_id * 10, thread_id * 10 + 20, thread_id * 10 + 20)
                cropped = cropper.crop(image_data, rect)
                results.append((thread_id, cropped))
            except Exception as e:  # noqa: BLE001
                errors.append((thread_id, e))

        # Create and start threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=crop_thread, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify results
        assert len(errors) == 0
        assert len(results) == 5

        # Check each result
        for _thread_id, cropped in results:
            assert cropped.image_data.shape == (20, 20, 3)

    def test_crop_data_types(self, cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test cropping with different data types."""
        data_types = [np.uint8, np.uint16, np.float32, np.float64]

        for dtype in data_types:
            # Create test image with specific dtype
            if dtype in {np.float32, np.float64}:
                rng = np.random.default_rng()
                image = rng.random((100, 100, 3)).astype(dtype)
            else:
                max_val = np.iinfo(dtype).max
                rng = np.random.default_rng()
                image = rng.integers(0, max_val, (100, 100, 3), dtype=dtype)

            image_data = ImageData(image_data=image, metadata={"width": 100, "height": 100, "dtype": str(dtype)})

            rect = (25, 25, 75, 75)
            cropped = cropper.crop(image_data, rect)

            assert cropped.image_data.dtype == dtype
            assert cropped.image_data.shape == (50, 50, 3)

    def test_process_with_validation(self, sample_images: dict[str, Any], cropper: ImageCropper, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test process method with parameter validation."""
        input_path = Path(temp_dir) / "input.npy"
        np.save(input_path, sample_images["rgb"])

        # Test with missing parameters
        invalid_params = [
            {},  # Empty params
            {"input_path": str(input_path)},  # Missing output_path
            {"output_path": "out.npy"},  # Missing input_path
            {"input_path": str(input_path), "output_path": "out.npy"},  # Missing crop_rect
        ]

        for params in invalid_params:
            result = cropper.process(params)
            assert result["success"] is False
            assert "error" in result

        # Test with invalid crop rect
        params = {
            "input_path": str(input_path),
            "output_path": str(Path(temp_dir) / "out.npy"),
            "crop_rect": (50, 50, 40, 40),  # Invalid: x2 < x1
        }
        result = cropper.process(params)
        assert result["success"] is False

    def test_integration_with_image_data_class(self, sample_images: dict[str, Any], cropper: ImageCropper) -> None:  # noqa: PLR6301
        """Test integration with ImageData class features."""
        # Test with various metadata configurations
        metadata_configs = [
            {"width": 100, "height": 100},
            {"width": 100, "height": 100, "channels": 3, "format": "RGB"},
            {"width": 100, "height": 100, "timestamp": "2024-01-01T00:00:00"},
            {"width": 100, "height": 100, "processing_history": ["loaded", "normalized"]},
        ]

        for metadata in metadata_configs:
            image_data = ImageData(image_data=sample_images["rgb"].copy(), metadata=metadata.copy())

            rect = (10, 10, 90, 90)
            cropped = cropper.crop(image_data, rect)

            # Verify metadata handling
            assert cropped.metadata["width"] == 80
            assert cropped.metadata["height"] == 80

            # Original metadata should be preserved
            for key in metadata:
                if key not in {"width", "height"}:
                    assert cropped.metadata[key] == metadata[key]
