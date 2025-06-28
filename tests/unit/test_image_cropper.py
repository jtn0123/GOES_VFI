"""Tests for image cropping functionality."""

import numpy as np
import pytest

from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_processing_interfaces import ImageData


class TestImageCropper:
    """Test image cropping functionality."""

    @pytest.fixture()
    def sample_image(self):
        """Create a sample test image array."""
        # Create a 100x100 RGB image with gradient
        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            for j in range(100):
                img_array[i, j] = [i * 2, j * 2, (i + j)]
        return img_array

    @pytest.fixture()
    def cropper(self):
        """Create an ImageCropper instance."""
        return ImageCropper()

    def test_cropper_initialization(self, cropper) -> None:
        """Test ImageCropper initialization."""
        assert hasattr(cropper, "crop")
        assert hasattr(cropper, "load")
        assert hasattr(cropper, "save")
        assert hasattr(cropper, "process")

    def test_basic_crop(self, sample_image, cropper) -> None:
        """Test basic image cropping."""
        # Create ImageData object
        image_data = ImageData(image_data=sample_image, metadata={"width": 100, "height": 100})

        # Crop center region
        rect = (25, 25, 75, 75)
        cropped_data = cropper.crop(image_data, rect)

        assert cropped_data.image_data.shape == (50, 50, 3)
        assert np.array_equal(cropped_data.image_data, sample_image[25:75, 25:75])
        assert cropped_data.metadata["width"] == 50
        assert cropped_data.metadata["height"] == 50
