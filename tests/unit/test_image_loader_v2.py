"""Tests for pipeline.image_loader module.

This module tests the ImageLoader class which loads images from disk
using Pillow and converts them to ImageData objects for the pipeline.
"""

from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import pytest

from goesvfi.pipeline.exceptions import InputError, ProcessingError
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestImageLoaderInitialization:
    """Test ImageLoader initialization and configuration."""

    def test_default_initialization(self) -> None:
        """Test ImageLoader with default parameters."""
        loader = ImageLoader()
        assert loader.optimize_memory is True
        assert loader.max_image_size_mb is None
        assert loader.memory_optimizer is not None

    def test_initialization_with_memory_optimization_disabled(self) -> None:
        """Test ImageLoader with memory optimization disabled."""
        loader = ImageLoader(optimize_memory=False)
        assert loader.optimize_memory is False
        assert loader.memory_optimizer is None

    def test_initialization_with_size_limit(self) -> None:
        """Test ImageLoader with maximum image size limit."""
        max_size = 100
        loader = ImageLoader(max_image_size_mb=max_size)
        assert loader.max_image_size_mb == max_size
        assert loader.optimize_memory is True

    def test_initialization_with_all_parameters(self) -> None:
        """Test ImageLoader with all parameters specified."""
        loader = ImageLoader(optimize_memory=False, max_image_size_mb=50)
        assert loader.optimize_memory is False
        assert loader.max_image_size_mb == 50
        assert loader.memory_optimizer is None


class TestImageLoaderFileHandling:
    """Test ImageLoader file handling and error cases."""

    def test_load_nonexistent_file(self) -> None:
        """Test loading a file that doesn't exist."""
        loader = ImageLoader()
        nonexistent_path = "/path/that/does/not/exist.png"

        with pytest.raises(InputError) as exc_info:
            loader.load(nonexistent_path)

        assert "Image file not found" in str(exc_info.value)
        assert nonexistent_path in str(exc_info.value)

    def test_load_directory_instead_of_file(self, tmp_path) -> None:
        """Test loading a directory path instead of a file."""
        loader = ImageLoader()

        with pytest.raises(InputError):
            loader.load(str(tmp_path))

    def test_load_corrupted_image_file(self, tmp_path) -> None:
        """Test loading a corrupted image file."""
        loader = ImageLoader()

        # Create a file with invalid image data
        corrupted_file = tmp_path / "corrupted.png"
        corrupted_file.write_bytes(b"This is not an image file")

        with pytest.raises(InputError) as exc_info:
            loader.load(str(corrupted_file))

        assert "Error reading image file" in str(exc_info.value)

    def test_load_unsupported_format(self, tmp_path) -> None:
        """Test loading an unsupported file format."""
        loader = ImageLoader()

        # Create a text file with .bmp extension
        unsupported_file = tmp_path / "fake.bmp"
        unsupported_file.write_text("This is not a bitmap")

        with pytest.raises(InputError):
            loader.load(str(unsupported_file))


class TestImageLoaderValidImages:
    """Test ImageLoader with valid image files."""

    def create_test_image(self, tmp_path, format_name="PNG", mode="RGB", size=(100, 100)):
        """Create a test image file.

        Args:
            tmp_path: Temporary path from pytest fixture
            format_name: Image format (PNG, JPEG, etc.)
            mode: PIL image mode (RGB, RGBA, L, etc.)
            size: Image dimensions (width, height)

        Returns:
            Path to the created image file
        """
        # Create a test image
        img = Image.new(mode, size, color="red")

        # Add some pattern to make it more realistic
        pixels = np.array(img)
        if len(pixels.shape) == 3:  # RGB/RGBA
            channels = pixels.shape[2]
            if channels == 3:  # RGB
                pixels[10:20, 10:20] = [0, 255, 0]  # Green square
                pixels[30:40, 30:40] = [0, 0, 255]  # Blue square
            elif channels == 4:  # RGBA
                pixels[10:20, 10:20] = [0, 255, 0, 255]  # Green square with alpha
                pixels[30:40, 30:40] = [0, 0, 255, 255]  # Blue square with alpha
        else:  # Grayscale
            pixels[10:20, 10:20] = 128
            pixels[30:40, 30:40] = 255

        img = Image.fromarray(pixels)

        # Save with appropriate extension
        extension = "png" if format_name == "PNG" else format_name.lower()
        image_path = tmp_path / f"test_image.{extension}"
        img.save(str(image_path), format=format_name)

        return str(image_path)

    def test_load_rgb_png_image(self, tmp_path) -> None:
        """Test loading a valid RGB PNG image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, "PNG", "RGB", (200, 150))

        result = loader.load(image_path)

        assert isinstance(result, ImageData)
        assert isinstance(result.image_data, np.ndarray)
        assert result.source_path == image_path
        assert result.metadata["format"] == "PNG"
        assert result.metadata["mode"] == "RGB"
        assert result.metadata["width"] == 200
        assert result.metadata["height"] == 150
        assert result.image_data.shape == (150, 200, 3)

    def test_load_rgba_png_image(self, tmp_path) -> None:
        """Test loading a valid RGBA PNG image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, "PNG", "RGBA", (100, 100))

        result = loader.load(image_path)

        assert isinstance(result, ImageData)
        assert result.metadata["mode"] == "RGBA"
        assert result.image_data.shape == (100, 100, 4)

    def test_load_grayscale_image(self, tmp_path) -> None:
        """Test loading a grayscale image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, "PNG", "L", (50, 75))

        result = loader.load(image_path)

        assert isinstance(result, ImageData)
        assert result.metadata["mode"] == "L"
        assert result.image_data.shape == (75, 50)

    def test_load_jpeg_image(self, tmp_path) -> None:
        """Test loading a JPEG image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, "JPEG", "RGB", (300, 200))

        result = loader.load(image_path)

        assert isinstance(result, ImageData)
        assert result.metadata["format"] == "JPEG"
        assert result.metadata["mode"] == "RGB"
        assert result.image_data.shape == (200, 300, 3)

    def test_metadata_completeness(self, tmp_path) -> None:
        """Test that all expected metadata is present."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, "PNG", "RGB", (100, 100))

        result = loader.load(image_path)

        required_metadata = ["format", "mode", "width", "height", "source_path", "memory_optimized", "dtype", "size_mb"]

        for key in required_metadata:
            assert key in result.metadata

        assert result.metadata["source_path"] == image_path
        assert result.metadata["memory_optimized"] is True
        assert isinstance(result.metadata["size_mb"], float)
        assert result.metadata["size_mb"] > 0


class TestImageLoaderMemoryOptimization:
    """Test ImageLoader memory optimization features."""

    def create_test_image(self, tmp_path, size=(100, 100)):
        """Helper to create a test image."""
        img = Image.new("RGB", size, color="red")
        image_path = tmp_path / "test.png"
        img.save(str(image_path))
        return str(image_path)

    def test_memory_optimization_enabled(self, tmp_path) -> None:
        """Test loading with memory optimization enabled."""
        loader = ImageLoader(optimize_memory=True)
        image_path = self.create_test_image(tmp_path)

        with patch("goesvfi.pipeline.image_loader.log_memory_usage") as mock_log:
            result = loader.load(image_path)

            # Should log memory before and after loading
            assert mock_log.call_count == 2
            mock_log.assert_any_call("Before loading image")
            mock_log.assert_any_call("After loading image")

        assert result.metadata["memory_optimized"] is True

    def test_memory_optimization_disabled(self, tmp_path) -> None:
        """Test loading with memory optimization disabled."""
        loader = ImageLoader(optimize_memory=False)
        image_path = self.create_test_image(tmp_path)

        with patch("goesvfi.pipeline.image_loader.log_memory_usage") as mock_log:
            result = loader.load(image_path)

            # Should not log memory
            mock_log.assert_not_called()

        assert result.metadata["memory_optimized"] is False

    def test_image_size_limit_enforcement(self, tmp_path) -> None:
        """Test that image size limits are enforced."""
        # Create a loader with very small size limit
        loader = ImageLoader(optimize_memory=True, max_image_size_mb=0.001)  # 1KB limit
        image_path = self.create_test_image(tmp_path, size=(1000, 1000))  # Large image

        # The ValueError should be caught and re-raised as ProcessingError
        with pytest.raises(ProcessingError) as exc_info:
            loader.load(image_path)

        assert "Image too large" in str(exc_info.value)
        assert "exceeds limit" in str(exc_info.value)

    def test_image_size_limit_not_enforced_when_disabled(self, tmp_path) -> None:
        """Test that images load when size limit is disabled."""
        loader = ImageLoader(optimize_memory=True, max_image_size_mb=None)
        image_path = self.create_test_image(tmp_path, size=(500, 500))

        # Should load successfully without size limit
        result = loader.load(image_path)
        assert isinstance(result, ImageData)

    @patch("goesvfi.pipeline.image_loader.MemoryOptimizer")
    def test_insufficient_memory_handling(self, mock_memory_optimizer, tmp_path) -> None:
        """Test handling when insufficient memory is available."""
        # Mock memory optimizer to report insufficient memory
        mock_optimizer_instance = Mock()
        mock_optimizer_instance.check_available_memory.return_value = (False, "Not enough memory")
        mock_memory_optimizer.return_value = mock_optimizer_instance

        loader = ImageLoader(optimize_memory=True)
        image_path = self.create_test_image(tmp_path)

        with pytest.raises(MemoryError) as exc_info:
            loader.load(image_path)

        assert "Insufficient memory to load image" in str(exc_info.value)

    @patch("goesvfi.pipeline.image_loader.MemoryOptimizer")
    def test_array_dtype_optimization(self, mock_memory_optimizer, tmp_path) -> None:
        """Test that array dtype optimization is applied."""
        # Mock memory optimizer
        mock_optimizer_instance = Mock()
        mock_optimizer_instance.check_available_memory.return_value = (True, "OK")
        # Mock optimize_array_dtype to return different dtype
        mock_optimizer_instance.optimize_array_dtype.return_value = np.array([1, 2, 3], dtype=np.uint16)
        mock_memory_optimizer.return_value = mock_optimizer_instance

        loader = ImageLoader(optimize_memory=True)
        image_path = self.create_test_image(tmp_path)

        result = loader.load(image_path)

        # Should call optimize_array_dtype
        mock_optimizer_instance.optimize_array_dtype.assert_called_once()
        assert isinstance(result, ImageData)


class TestImageLoaderUnimplementedMethods:
    """Test that unimplemented methods raise appropriate exceptions."""

    def test_process_method_not_implemented(self, tmp_path) -> None:
        """Test that process method raises NotImplementedError."""
        loader = ImageLoader()

        # Create dummy ImageData
        image_data = ImageData(image_data=np.array([[1, 2], [3, 4]]), source_path="test.png")

        with pytest.raises(NotImplementedError) as exc_info:
            loader.process(image_data)

        assert "does not implement the process method" in str(exc_info.value)

    def test_crop_method_not_implemented(self, tmp_path) -> None:
        """Test that crop method raises NotImplementedError."""
        loader = ImageLoader()

        # Create dummy ImageData
        image_data = ImageData(image_data=np.array([[1, 2], [3, 4]]), source_path="test.png")

        with pytest.raises(NotImplementedError) as exc_info:
            loader.crop(image_data, (0, 0, 10, 10))

        assert "does not implement the crop method" in str(exc_info.value)

    def test_save_method_not_implemented(self, tmp_path) -> None:
        """Test that save method raises NotImplementedError."""
        loader = ImageLoader()

        # Create dummy ImageData
        image_data = ImageData(image_data=np.array([[1, 2], [3, 4]]), source_path="test.png")

        with pytest.raises(NotImplementedError) as exc_info:
            loader.save(image_data, "output.png")

        assert "does not implement the save method" in str(exc_info.value)


class TestImageLoaderEdgeCases:
    """Test ImageLoader edge cases and error scenarios."""

    def create_test_image(self, tmp_path, size=(100, 100), mode="RGB"):
        """Helper to create a test image."""
        img = Image.new(mode, size, color="red")
        image_path = tmp_path / "test.png"
        img.save(str(image_path))
        return str(image_path)

    def test_very_small_image(self, tmp_path) -> None:
        """Test loading a very small image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, size=(1, 1))

        result = loader.load(image_path)

        assert isinstance(result, ImageData)
        assert result.image_data.shape == (1, 1, 3)
        assert result.metadata["width"] == 1
        assert result.metadata["height"] == 1

    def test_square_image(self, tmp_path) -> None:
        """Test loading a square image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, size=(100, 100))

        result = loader.load(image_path)

        assert result.image_data.shape == (100, 100, 3)
        assert result.metadata["width"] == 100
        assert result.metadata["height"] == 100

    def test_wide_image(self, tmp_path) -> None:
        """Test loading a wide image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, size=(300, 100))

        result = loader.load(image_path)

        assert result.image_data.shape == (100, 300, 3)
        assert result.metadata["width"] == 300
        assert result.metadata["height"] == 100

    def test_tall_image(self, tmp_path) -> None:
        """Test loading a tall image."""
        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path, size=(100, 300))

        result = loader.load(image_path)

        assert result.image_data.shape == (300, 100, 3)
        assert result.metadata["width"] == 100
        assert result.metadata["height"] == 300

    def test_image_with_special_characters_in_path(self, tmp_path) -> None:
        """Test loading image with special characters in path."""
        loader = ImageLoader()

        # Create image with special characters in filename
        special_dir = tmp_path / "special-dir_123"
        special_dir.mkdir()
        img = Image.new("RGB", (50, 50), color="blue")
        image_path = special_dir / "test-image_special.png"
        img.save(str(image_path))

        result = loader.load(str(image_path))

        assert isinstance(result, ImageData)
        assert result.source_path == str(image_path)

    @patch("goesvfi.pipeline.image_loader.Image.open")
    def test_unexpected_pillow_error(self, mock_open, tmp_path) -> None:
        """Test handling of unexpected errors from Pillow."""
        # Mock Pillow to raise an unexpected error
        mock_open.side_effect = RuntimeError("Unexpected PIL error")

        loader = ImageLoader()
        image_path = self.create_test_image(tmp_path)

        with pytest.raises(ProcessingError) as exc_info:
            loader.load(image_path)

        assert "Could not load image" in str(exc_info.value)
        assert "Unexpected PIL error" in str(exc_info.value)

    def test_permission_denied_error(self, tmp_path) -> None:
        """Test handling permission denied errors."""
        loader = ImageLoader()

        # Create image file
        image_path = self.create_test_image(tmp_path)

        # Mock os.path.exists to return True but make Image.open fail with PermissionError
        with patch("goesvfi.pipeline.image_loader.Image.open") as mock_open:
            mock_open.side_effect = PermissionError("Permission denied")

            with pytest.raises(InputError) as exc_info:
                loader.load(image_path)

            assert "Error reading image file" in str(exc_info.value)


class TestImageLoaderIntegration:
    """Integration tests for ImageLoader with real image operations."""

    def test_load_multiple_images_sequentially(self, tmp_path) -> None:
        """Test loading multiple images in sequence."""
        loader = ImageLoader()
        image_paths = []

        # Create multiple test images
        for i in range(3):
            img = Image.new("RGB", (50 + i * 10, 50 + i * 10), color=(i * 80, 100, 150))
            image_path = tmp_path / f"image_{i}.png"
            img.save(str(image_path))
            image_paths.append(str(image_path))

        results = []
        for path in image_paths:
            result = loader.load(path)
            results.append(result)

        # Verify all images loaded correctly
        assert len(results) == 3
        for i, result in enumerate(results):
            assert isinstance(result, ImageData)
            assert result.metadata["width"] == 50 + i * 10
            assert result.metadata["height"] == 50 + i * 10

    def test_memory_usage_tracking(self, tmp_path) -> None:
        """Test that memory usage is properly tracked."""
        loader = ImageLoader(optimize_memory=True)

        # Create a moderately sized image
        img = Image.new("RGB", (200, 200), color="green")
        image_path = tmp_path / "memory_test.png"
        img.save(str(image_path))

        with (
            patch("goesvfi.pipeline.image_loader.log_memory_usage") as mock_log,
            patch("goesvfi.pipeline.image_loader.estimate_memory_requirement") as mock_estimate,
        ):
            mock_estimate.return_value = 0.5  # 0.5 MB

            result = loader.load(str(image_path))

            # Should estimate memory and log usage
            mock_estimate.assert_called_once()
            assert mock_log.call_count == 2
            assert isinstance(result, ImageData)
            assert result.metadata["size_mb"] > 0
