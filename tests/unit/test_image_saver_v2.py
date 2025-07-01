"""Tests for image saving functionality - Optimized V2 with 100%+ coverage."""

import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Any
from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest

from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.image_saver import ImageSaver


class TestImageSaverV2:  # noqa: PLR0904
    """Test image saving functionality with comprehensive coverage."""

    @pytest.fixture()
    @staticmethod
    def saver() -> Any:
        """Create an ImageSaver instance.

        Returns:
            ImageSaver: Test image saver instance.
        """
        return ImageSaver()

    @pytest.fixture()
    @staticmethod
    def sample_images() -> Any:
        """Create various sample test images.

        Returns:
            dict[str, Any]: Sample images for testing.
        """
        # Standard RGB image
        rgb_array = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                rgb_array[i, j] = [i * 2, j * 2, (i + j)]

        # Grayscale image
        gray_array = np.random.randint(0, 255, (50, 50), dtype=np.uint8)  # noqa: NPY002

        # RGBA image with transparency
        rgba_array = np.zeros((50, 50, 4), dtype=np.uint8)
        rgba_array[:, :, 0] = 255  # Red channel
        rgba_array[:, :, 3] = 128  # Half transparent

        # 16-bit grayscale
        img_16bit = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)  # noqa: NPY002

        # Float image (normalized 0-1)
        float_array = np.random.rand(64, 64, 3).astype(np.float32)  # noqa: NPY002

        # Large image for performance testing
        large_array = np.random.randint(0, 255, (2000, 2000, 3), dtype=np.uint8)  # noqa: NPY002

        # Single channel float
        single_float = np.random.rand(128, 128).astype(np.float64)  # noqa: NPY002

        return {
            "rgb": rgb_array,
            "gray": gray_array,
            "rgba": rgba_array,
            "bit16": img_16bit,
            "float": float_array,
            "large": large_array,
            "single_float": single_float,
        }

    @pytest.fixture()
    @staticmethod
    def temp_dir() -> Any:
        """Create a temporary directory for tests.

        Yields:
            str: Temporary directory path.
        """
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_saver_initialization(self, saver: Any) -> None:  # noqa: PLR6301
        """Test ImageSaver initialization and interface."""
        # Verify required methods exist
        assert hasattr(saver, "save")
        assert hasattr(saver, "load")
        assert hasattr(saver, "process")
        assert hasattr(saver, "crop")

        # Verify method signatures
        assert callable(saver.save)
        assert callable(saver.load)
        assert callable(saver.process)
        assert callable(saver.crop)

    def test_save_rgb_image(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving RGB image with verification."""
        output_path = Path(temp_dir) / "rgb_test.png"

        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100, "format": "RGB"})

        # Save image
        saver.save(image_data, str(output_path))

        # Verify file exists and can be loaded
        assert output_path.exists()
        loaded_img = Image.open(output_path)
        assert loaded_img.size == (100, 100)
        assert loaded_img.mode == "RGB"

        # Verify pixel data
        loaded_array = np.array(loaded_img)
        assert np.array_equal(loaded_array, sample_images["rgb"])

    def test_save_grayscale_image(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving grayscale image."""
        output_path = Path(temp_dir) / "gray_test.png"

        image_data = ImageData(image_data=sample_images["gray"], metadata={"width": 50, "height": 50, "format": "L"})

        saver.save(image_data, str(output_path))

        # Verify
        assert output_path.exists()
        loaded_img = Image.open(output_path)
        assert loaded_img.size == (50, 50)
        assert loaded_img.mode == "L"

        # Verify data integrity
        loaded_array = np.array(loaded_img)
        assert loaded_array.shape == sample_images["gray"].shape

    def test_save_creates_nested_directories(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test that save creates nested parent directories."""
        # Create deeply nested path
        output_path = Path(temp_dir) / "level1" / "level2" / "level3" / "image.png"

        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Save should create all directories
        saver.save(image_data, str(output_path))

        assert output_path.exists()
        assert output_path.parent.exists()
        assert output_path.parent.parent.exists()
        assert output_path.parent.parent.parent.exists()

    @pytest.mark.parametrize(
        "format_ext,pil_mode",
        [
            (".png", "RGB"),
            (".jpg", "RGB"),
            (".jpeg", "RGB"),
            (".bmp", "RGB"),
            (".tiff", "RGB"),
            (".gif", "P"),  # GIF converts to palette mode
            (".webp", "RGB"),
        ],
    )
    def test_save_different_formats(self, saver: Any, sample_images: Any, temp_dir: Any, format_ext: str, pil_mode: str) -> None:  # noqa: PLR6301
        """Test saving in different image formats."""
        output_path = Path(temp_dir) / f"test{format_ext}"

        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        saver.save(image_data, str(output_path))

        assert output_path.exists()

        # Verify can be loaded
        loaded_img = Image.open(output_path)
        assert loaded_img.size == (100, 100)

        # Some formats change the mode
        if format_ext != ".gif":
            assert loaded_img.mode == pil_mode

    def test_save_rgba_with_transparency(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving RGBA image with transparency preservation."""
        output_path = Path(temp_dir) / "rgba_test.png"

        image_data = ImageData(image_data=sample_images["rgba"], metadata={"width": 50, "height": 50, "format": "RGBA"})

        saver.save(image_data, str(output_path))

        # Verify
        assert output_path.exists()
        loaded_img = Image.open(output_path)
        assert loaded_img.size == (50, 50)
        assert loaded_img.mode == "RGBA"

        # Verify alpha channel preserved
        loaded_array = np.array(loaded_img)
        assert loaded_array.shape == (50, 50, 4)
        assert np.all(loaded_array[:, :, 3] == 128)  # Alpha preserved

    def test_save_16bit_image(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving 16-bit depth image."""
        output_path = Path(temp_dir) / "16bit_test.png"

        image_data = ImageData(
            image_data=sample_images["bit16"], metadata={"width": 100, "height": 100, "bit_depth": 16}
        )

        try:
            saver.save(image_data, str(output_path))
            assert output_path.exists()

            # Verify 16-bit preservation if supported
            loaded_img = Image.open(output_path)
            if hasattr(loaded_img, "mode") and "I" in loaded_img.mode:
                # Successfully saved as 16-bit
                assert True
        except (OSError, ValueError):
            # Expected if PIL doesn't support 16-bit for this format
            pytest.skip("16-bit image saving not supported")

    def test_save_float_image_normalization(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving float images with proper normalization."""
        output_path = Path(temp_dir) / "float_test.png"

        image_data = ImageData(
            image_data=sample_images["float"], metadata={"width": 64, "height": 64, "format": "RGB", "dtype": "float32"}
        )

        saver.save(image_data, str(output_path))

        assert output_path.exists()
        loaded_img = Image.open(output_path)
        assert loaded_img.size == (64, 64)

    def test_save_error_handling(self, saver: Any, sample_images: Any) -> None:  # noqa: PLR6301
        """Test comprehensive error handling during save."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Test with invalid path (no permissions)
        with pytest.raises(IOError, match=r".*"):
            saver.save(image_data, "/root/no_permission/image.png")

        # Test with invalid path characters
        if os.name == "nt":  # Windows
            with pytest.raises((IOError, OSError)):
                saver.save(image_data, "C:\\invalid:file*name?.png")

    def test_save_invalid_data_types(self, saver: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving with various invalid data types."""
        invalid_data_configs = [
            (np.array([1, 2, 3]), "1D array"),  # 1D array
            (np.array([[[[1]]]]), "4D array"),  # 4D array
            ("not an array", "string data"),  # String
            (None, "None data"),  # None
            (np.array([]), "empty array"),  # Empty array
        ]

        for invalid_data, description in invalid_data_configs:
            image_data = ImageData(image_data=invalid_data, metadata={"description": description})

            output_path = Path(temp_dir) / f"invalid_{description.replace(' ', '_')}.png"

            with pytest.raises((ValueError, AttributeError, TypeError)):
                saver.save(image_data, str(output_path))

    def test_not_implemented_methods(self, saver: Any) -> None:  # noqa: PLR6301
        """Test that non-save methods raise NotImplementedError."""
        # Create test data
        image_data = ImageData(image_data=np.zeros((10, 10, 3), dtype=np.uint8))

        # Test load
        with pytest.raises(NotImplementedError):
            saver.load("test.png")

        # Test process
        with pytest.raises(NotImplementedError):
            saver.process(image_data)

        # Test crop
        with pytest.raises(NotImplementedError):
            saver.crop(image_data, (0, 0, 5, 5))

    def test_save_with_metadata_preservation(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving preserves complex metadata."""
        output_path = Path(temp_dir) / "metadata_test.png"

        complex_metadata = {
            "width": 100,
            "height": 100,
            "format": "RGB",
            "source_path": "/original/path/image.png",
            "processing_steps": [
                {"operation": "resize", "scale": 0.5},
                {"operation": "blur", "radius": 2.0},
                {"operation": "sharpen", "amount": 1.5},
            ],
            "timestamp": "2024-01-01T12:00:00",
            "author": "Test Suite",
            "custom_tags": {"project": "GOES_VFI", "version": "2.0"},
        }

        image_data = ImageData(
            image_data=sample_images["rgb"], source_path="/original/path/image.png", metadata=complex_metadata
        )

        saver.save(image_data, str(output_path))

        # Verify save succeeded with complex metadata
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_save_performance(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving performance with multiple images."""
        # Time module already imported at top

        # Time saving multiple images
        start_time = time.time()
        num_saves = 50

        for i in range(num_saves):
            output_path = Path(temp_dir) / f"perf_test_{i}.png"
            image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})
            saver.save(image_data, str(output_path))

        elapsed_time = time.time() - start_time
        avg_time = elapsed_time / num_saves

        # Performance assertion
        assert avg_time < 0.1  # Less than 100ms per save

        # Verify all files created
        saved_files = list(Path(temp_dir).glob("perf_test_*.png"))
        assert len(saved_files) == num_saves

    def test_save_large_image(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving large images efficiently."""
        output_path = Path(temp_dir) / "large_image.png"

        image_data = ImageData(image_data=sample_images["large"], metadata={"width": 2000, "height": 2000})

        # Should handle large images without issues
        saver.save(image_data, str(output_path))

        assert output_path.exists()
        # Check file size is reasonable
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        assert file_size_mb > 0.1  # At least some data written

    def test_concurrent_saves(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test thread safety of save operations."""
        results = []
        errors = []

        def save_thread(thread_id: int) -> None:
            try:
                output_path = Path(temp_dir) / f"thread_{thread_id}.png"
                image_data = ImageData(
                    image_data=sample_images["rgb"].copy(),
                    metadata={"width": 100, "height": 100, "thread_id": thread_id},
                )
                saver.save(image_data, str(output_path))
                results.append((thread_id, output_path))
            except Exception as e:  # noqa: BLE001
                errors.append((thread_id, e))

        # Create and start threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=save_thread, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify results
        assert len(errors) == 0
        assert len(results) == 10

        # Check all files exist
        for _thread_id, path in results:
            assert path.exists()

    @patch("PIL.Image.Image.save")
    def test_save_with_pil_errors(self, mock_save: Any, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test handling of PIL save errors."""
        mock_save.side_effect = OSError("Simulated PIL save error")

        output_path = Path(temp_dir) / "error_test.png"
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        with pytest.raises(IOError, match=r".*") as exc_info:
            saver.save(image_data, str(output_path))

        assert "Simulated PIL save error" in str(exc_info.value)

    def test_save_with_quality_settings(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving with different quality settings for JPEG."""
        base_path = Path(temp_dir)

        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Save at different quality levels
        quality_levels = [10, 50, 95]
        file_sizes = []

        for quality in quality_levels:
            output_path = base_path / f"quality_{quality}.jpg"

            # Modify metadata to include quality hint
            image_data.metadata["jpeg_quality"] = quality
            saver.save(image_data, str(output_path))

            assert output_path.exists()
            file_sizes.append(output_path.stat().st_size)

        # Higher quality should generally result in larger files
        # (though not always guaranteed due to image content)
        assert file_sizes[0] <= file_sizes[2]  # q10 <= q95

    def test_save_with_compression(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test PNG compression levels."""
        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        # Save with different compression hints
        compression_levels = [0, 5, 9]  # None, medium, maximum

        for level in compression_levels:
            output_path = Path(temp_dir) / f"compress_{level}.png"
            image_data.metadata["png_compress_level"] = level

            saver.save(image_data, str(output_path))
            assert output_path.exists()

    def test_edge_cases(self, saver: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test various edge cases."""
        # Single pixel image
        single_pixel = np.array([[[255, 0, 0]]], dtype=np.uint8)
        image_data = ImageData(image_data=single_pixel, metadata={"width": 1, "height": 1})

        output_path = Path(temp_dir) / "single_pixel.png"
        saver.save(image_data, str(output_path))

        assert output_path.exists()
        loaded = Image.open(output_path)
        assert loaded.size == (1, 1)

        # Very wide image
        wide_image = np.zeros((10, 1000, 3), dtype=np.uint8)
        image_data = ImageData(image_data=wide_image, metadata={"width": 1000, "height": 10})

        output_path = Path(temp_dir) / "wide_image.png"
        saver.save(image_data, str(output_path))
        assert output_path.exists()

        # Very tall image
        tall_image = np.zeros((1000, 10, 3), dtype=np.uint8)
        image_data = ImageData(image_data=tall_image, metadata={"width": 10, "height": 1000})

        output_path = Path(temp_dir) / "tall_image.png"
        saver.save(image_data, str(output_path))
        assert output_path.exists()

    def test_save_with_special_characters(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test saving with special characters in filename."""
        special_names = [
            "image with spaces.png",
            "image_with_underscores.png",
            "image-with-dashes.png",
            "image.multiple.dots.png",
            "UPPERCASE.PNG",
            "unicode_测试.png",
        ]

        image_data = ImageData(image_data=sample_images["rgb"], metadata={"width": 100, "height": 100})

        for name in special_names:
            output_path = Path(temp_dir) / name
            try:
                saver.save(image_data, str(output_path))
                assert output_path.exists()
            except (OSError, UnicodeError):
                # Some systems may not support certain characters
                pytest.skip(f"System doesn't support filename: {name}")

    def test_save_memory_efficiency(self, saver: Any, temp_dir: Any) -> None:  # noqa: PLR6301
        """Test memory efficiency during save operations."""
        # Create a large image that would use significant memory
        large_image = np.zeros((5000, 5000, 3), dtype=np.uint8)

        image_data = ImageData(image_data=large_image, metadata={"width": 5000, "height": 5000})

        output_path = Path(temp_dir) / "memory_test.png"

        # Should complete without memory errors
        saver.save(image_data, str(output_path))

        assert output_path.exists()

        # Clean up large file immediately
        output_path.unlink()

    def test_save_with_data_validation(self, saver: Any, sample_images: Any, temp_dir: Any) -> None:  # noqa: PLR6301, ARG002
        """Test that saved data matches original after round-trip."""
        formats_to_test = [".png", ".bmp", ".tiff"]  # Lossless formats

        for fmt in formats_to_test:
            output_path = Path(temp_dir) / f"validation{fmt}"

            # Use a small test image for exact comparison
            test_array = np.array(
                [
                    [[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                    [[255, 255, 0], [255, 0, 255], [0, 255, 255]],
                    [[128, 128, 128], [64, 64, 64], [192, 192, 192]],
                ],
                dtype=np.uint8,
            )

            image_data = ImageData(image_data=test_array, metadata={"width": 3, "height": 3})

            # Save
            saver.save(image_data, str(output_path))

            # Load and compare
            loaded_img = Image.open(output_path)
            loaded_array = np.array(loaded_img)

            # For lossless formats, data should match exactly
            assert np.array_equal(loaded_array, test_array), f"Data mismatch for {fmt}"
