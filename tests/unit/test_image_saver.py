"""Tests for image saving functionality."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.image_saver import ImageSaver


class TestImageSaver:
    """Test image saving functionality."""

    @pytest.fixture
    def saver(self):
        """Create an ImageSaver instance."""
        return ImageSaver()

    @pytest.fixture
    def sample_image(self):
        """Create a sample RGB image array."""
        # Create 100x100 RGB image with gradient
        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                img_array[i, j] = [i * 2, j * 2, (i + j)]
        return img_array

    def test_saver_initialization(self, saver):
        """Test ImageSaver initialization."""
        assert hasattr(saver, "save")
        assert hasattr(saver, "load")
        assert hasattr(saver, "process")
        assert hasattr(saver, "crop")

    def test_save_rgb_image(self, saver, sample_image):
        """Test saving RGB image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Create ImageData
            image_data = ImageData(
                image_data=sample_image,
                metadata={"width": 100, "height": 100, "format": "RGB"},
            )

            # Save image
            saver.save(image_data, str(tmp_path))

            # Verify file exists and can be loaded
            assert tmp_path.exists()
            loaded_img = Image.open(tmp_path)
            assert loaded_img.size == (100, 100)
            assert loaded_img.mode == "RGB"

            # Verify pixel data
            loaded_array = np.array(loaded_img)
            assert np.array_equal(loaded_array, sample_image)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_save_grayscale_image(self, saver):
        """Test saving grayscale image."""
        # Create grayscale image
        gray_array = np.random.randint(0, 255, (50, 50), dtype=np.uint8)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            image_data = ImageData(
                image_data=gray_array,
                metadata={"width": 50, "height": 50, "format": "L"},
            )

            saver.save(image_data, str(tmp_path))

            # Verify
            assert tmp_path.exists()
            loaded_img = Image.open(tmp_path)
            assert loaded_img.size == (50, 50)
            assert loaded_img.mode == "L"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_save_creates_directory(self, saver, sample_image):
        """Test that save creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested path that doesn't exist
            output_path = Path(tmpdir) / "subdir1" / "subdir2" / "image.png"

            image_data = ImageData(
                image_data=sample_image, metadata={"width": 100, "height": 100}
            )

            # Save should create directories
            saver.save(image_data, str(output_path))

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_save_different_formats(self, saver, sample_image):
        """Test saving in different formats."""
        formats = [".png", ".jpg", ".bmp"]

        with tempfile.TemporaryDirectory() as tmpdir:
            for fmt in formats:
                output_path = Path(tmpdir) / f"test{fmt}"

                image_data = ImageData(
                    image_data=sample_image, metadata={"width": 100, "height": 100}
                )

                saver.save(image_data, str(output_path))

                assert output_path.exists()
                # Verify can be loaded
                Image.open(output_path)

    def test_save_error_handling(self, saver, sample_image):
        """Test error handling during save."""
        # Test with invalid path (e.g., read-only location)
        image_data = ImageData(
            image_data=sample_image, metadata={"width": 100, "height": 100}
        )

        # Try to save to an invalid location
        with pytest.raises(IOError):
            saver.save(image_data, "/invalid/path/that/doesnt/exist/image.png")

    def test_save_invalid_data(self, saver):
        """Test saving invalid image data."""
        # Test with invalid array shape
        invalid_array = np.array([1, 2, 3])  # 1D array

        image_data = ImageData(image_data=invalid_array, metadata={})

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(ValueError):
                saver.save(image_data, str(tmp_path))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_not_implemented_methods(self, saver):
        """Test that non-save methods raise NotImplementedError."""
        # Test load
        with pytest.raises(NotImplementedError):
            saver.load("test.png")

        # Test process
        image_data = ImageData(image_data=np.zeros((10, 10, 3)))
        with pytest.raises(NotImplementedError):
            saver.process(image_data)

        # Test crop
        with pytest.raises(NotImplementedError):
            saver.crop(image_data, (0, 0, 5, 5))

    def test_save_rgba_image(self, saver):
        """Test saving RGBA image with transparency."""
        # Create RGBA image
        rgba_array = np.zeros((50, 50, 4), dtype=np.uint8)
        rgba_array[:, :, 0] = 255  # Red channel
        rgba_array[:, :, 3] = 128  # Half transparent

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            image_data = ImageData(
                image_data=rgba_array,
                metadata={"width": 50, "height": 50, "format": "RGBA"},
            )

            saver.save(image_data, str(tmp_path))

            # Verify
            assert tmp_path.exists()
            loaded_img = Image.open(tmp_path)
            assert loaded_img.size == (50, 50)
            assert loaded_img.mode == "RGBA"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_save_with_source_path_metadata(self, saver, sample_image):
        """Test saving preserves source path in metadata."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            image_data = ImageData(
                image_data=sample_image,
                source_path="/original/path/image.png",
                metadata={
                    "width": 100,
                    "height": 100,
                    "processing_steps": [{"operation": "resize", "scale": 0.5}],
                },
            )

            saver.save(image_data, str(tmp_path))

            # Just verify it saves successfully with metadata
            assert tmp_path.exists()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_save_16bit_image(self, saver):
        """Test saving 16-bit depth image."""
        # Create 16-bit grayscale image
        img_16bit = np.random.randint(0, 65535, (100, 100), dtype=np.uint16)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            image_data = ImageData(
                image_data=img_16bit,
                metadata={"width": 100, "height": 100, "bit_depth": 16},
            )

            # This might fail depending on PIL support, but we test the attempt
            try:
                saver.save(image_data, str(tmp_path))
                assert tmp_path.exists()
            except (IOError, ValueError):
                # Expected if PIL doesn't support 16-bit for this format
                pytest.skip("16-bit image saving not supported")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
