"""Tests for VFI image processing functionality."""

import pathlib
from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest

from goesvfi.pipeline.vfi_crop_handler import VFICropHandler
from goesvfi.pipeline.vfi_image_processor import VFIImageProcessor


def create_test_image(width=100, height=100, color=(255, 0, 0)):
    """Create a test PIL Image."""
    array = np.full((height, width, 3), color, dtype=np.uint8)
    return Image.fromarray(array)


def save_test_image(path: pathlib.Path, width=100, height=100, color=(255, 0, 0)):
    """Save a test image to disk."""
    img = create_test_image(width, height, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


class TestVFIImageProcessor:
    """Test the VFIImageProcessor class."""

    @pytest.fixture()
    def crop_handler(self):
        """Create a crop handler instance."""
        return VFICropHandler()

    @pytest.fixture()
    def image_processor(self, crop_handler):
        """Create an image processor instance."""
        return VFIImageProcessor(crop_handler)

    @pytest.fixture()
    def test_image_path(self, tmp_path):
        """Create a test image file."""
        img_path = tmp_path / "test_image.png"
        return save_test_image(img_path, 200, 150, (255, 0, 0))

    @pytest.fixture()
    def sanchez_temp_dir(self, tmp_path):
        """Create a temporary directory for Sanchez."""
        return tmp_path / "sanchez_temp"

    @pytest.fixture()
    def output_dir(self, tmp_path):
        """Create an output directory."""
        output = tmp_path / "output"
        output.mkdir()
        return output

    def test_image_processor_initialization(self, image_processor, crop_handler) -> None:
        """Test image processor initializes correctly."""
        assert image_processor.crop_handler is crop_handler

    def test_process_single_image_basic(self, image_processor, test_image_path, output_dir, sanchez_temp_dir) -> None:
        """Test basic image processing without crop or false color."""
        result = image_processor.process_single_image(
            test_image_path,
            crop_rect_pil=None,
            false_colour=False,
            res_km=2,
            sanchez_temp_dir=sanchez_temp_dir,
            output_dir=output_dir
        )

        # Check result
        assert result.exists()
        assert result.parent == output_dir
        assert "processed_" in result.name
        assert result.suffix == ".png"

        # Check output image
        with Image.open(result) as img:
            assert img.size == (200, 150)  # Same as input

    def test_process_single_image_with_crop(self, image_processor, test_image_path, output_dir, sanchez_temp_dir) -> None:
        """Test image processing with cropping."""
        crop_rect = (10, 20, 110, 120)  # 100x100 crop

        result = image_processor.process_single_image(
            test_image_path,
            crop_rect_pil=crop_rect,
            false_colour=False,
            res_km=2,
            sanchez_temp_dir=sanchez_temp_dir,
            output_dir=output_dir
        )

        # Check output image is cropped
        with Image.open(result) as img:
            assert img.size == (100, 100)

    @patch("goesvfi.pipeline.vfi_image_processor.colourise")
    def test_process_single_image_with_sanchez(self, mock_colourise, image_processor, test_image_path, output_dir, sanchez_temp_dir) -> None:
        """Test image processing with Sanchez false coloring."""
        sanchez_temp_dir.mkdir(parents=True)

        # Mock colourise to create a blue output image
        def create_blue_image(input_path, output_path, res_km=None) -> None:
            blue_img = create_test_image(200, 150, (0, 0, 255))
            blue_img.save(output_path, "PNG")

        mock_colourise.side_effect = create_blue_image

        result = image_processor.process_single_image(
            test_image_path,
            crop_rect_pil=None,
            false_colour=True,
            res_km=4,
            sanchez_temp_dir=sanchez_temp_dir,
            output_dir=output_dir
        )

        # Check colourise was called
        mock_colourise.assert_called_once()
        call_args = mock_colourise.call_args
        assert "test_image.png" in call_args[0][0]  # Input path
        assert "_fc.png" in call_args[0][1]  # Output path
        assert call_args.kwargs["res_km"] == 4

        # Check result exists
        assert result.exists()

    @patch("goesvfi.pipeline.vfi_image_processor.colourise")
    def test_process_single_image_sanchez_failure(self, mock_colourise, image_processor, test_image_path, output_dir, sanchez_temp_dir) -> None:
        """Test image processing when Sanchez fails."""
        sanchez_temp_dir.mkdir(parents=True)

        # Mock colourise to raise exception
        mock_colourise.side_effect = RuntimeError("Sanchez failed")

        # Should still succeed but use original image
        result = image_processor.process_single_image(
            test_image_path,
            crop_rect_pil=None,
            false_colour=True,
            res_km=4,
            sanchez_temp_dir=sanchez_temp_dir,
            output_dir=output_dir
        )

        # Check result exists (should have original color)
        assert result.exists()
        with Image.open(result) as img:
            # Should have original dimensions
            assert img.size == (200, 150)

    def test_process_single_image_invalid_crop(self, image_processor, test_image_path, output_dir, sanchez_temp_dir) -> None:
        """Test image processing with invalid crop rectangle."""
        # Crop exceeds image bounds
        crop_rect = (10, 20, 300, 200)  # Right edge > image width

        with pytest.raises(ValueError, match="exceeds image dimensions"):
            image_processor.process_single_image(
                test_image_path,
                crop_rect_pil=crop_rect,
                false_colour=False,
                res_km=2,
                sanchez_temp_dir=sanchez_temp_dir,
                output_dir=output_dir
            )

    def test_process_single_image_nonexistent_file(self, image_processor, tmp_path, output_dir, sanchez_temp_dir) -> None:
        """Test processing nonexistent image file."""
        bad_path = tmp_path / "nonexistent.png"

        with pytest.raises(Exception):  # Could be FileNotFoundError or other
            image_processor.process_single_image(
                bad_path,
                crop_rect_pil=None,
                false_colour=False,
                res_km=2,
                sanchez_temp_dir=sanchez_temp_dir,
                output_dir=output_dir
            )

    def test_apply_sanchez_coloring(self, image_processor, test_image_path, sanchez_temp_dir) -> None:
        """Test Sanchez coloring method directly."""
        sanchez_temp_dir.mkdir(parents=True)

        with patch("goesvfi.pipeline.vfi_image_processor.colourise") as mock_colourise:
            # Mock to create output
            def create_output(input_path, output_path, res_km=None) -> None:
                blue_img = create_test_image(200, 150, (0, 0, 255))
                blue_img.save(output_path, "PNG")

            mock_colourise.side_effect = create_output

            # Test
            img = Image.open(test_image_path)
            result = image_processor._apply_sanchez_coloring(
                img, test_image_path, 2, sanchez_temp_dir
            )

            # Should return a PIL Image
            assert isinstance(result, Image.Image)

            # Check temporary files were cleaned up
            temp_files = list(sanchez_temp_dir.glob("*.png"))
            assert len(temp_files) == 0

    def test_apply_crop(self, image_processor) -> None:
        """Test crop application method."""
        img = create_test_image(200, 150)
        crop_rect = (10, 20, 110, 120)

        result = image_processor._apply_crop(img, crop_rect, "test.png")

        assert isinstance(result, Image.Image)
        assert result.size == (100, 100)

    def test_apply_crop_invalid(self, image_processor) -> None:
        """Test crop with invalid rectangle."""
        img = create_test_image(100, 100)
        crop_rect = (50, 50, 40, 40)  # Invalid: right < left

        with pytest.raises(ValueError, match="Crop failed"):
            image_processor._apply_crop(img, crop_rect, "test.png")

    def test_save_processed_image(self, image_processor, output_dir) -> None:
        """Test saving processed image."""
        img = create_test_image(100, 100)

        result = image_processor._save_processed_image(
            img, "test_stem", output_dir
        )

        assert result.exists()
        assert result.parent == output_dir
        assert "processed_test_stem_" in result.name
        assert result.suffix == ".png"

    def test_get_image_dimensions(self, image_processor, test_image_path) -> None:
        """Test getting image dimensions."""
        width, height = image_processor.get_image_dimensions(test_image_path)

        assert width == 200
        assert height == 150

    def test_get_image_dimensions_nonexistent(self, image_processor, tmp_path) -> None:
        """Test getting dimensions of nonexistent file."""
        bad_path = tmp_path / "nonexistent.png"

        with pytest.raises(OSError, match="Cannot read image dimensions"):
            image_processor.get_image_dimensions(bad_path)

    def test_validate_image_format_valid_png(self, image_processor, test_image_path) -> None:
        """Test validating a valid PNG image."""
        assert image_processor.validate_image_format(test_image_path) is True

    def test_validate_image_format_invalid_file(self, image_processor, tmp_path) -> None:
        """Test validating a non-image file."""
        # Create a text file
        text_file = tmp_path / "not_an_image.txt"
        text_file.write_text("This is not an image")

        assert image_processor.validate_image_format(text_file) is False

    def test_validate_image_format_nonexistent(self, image_processor, tmp_path) -> None:
        """Test validating nonexistent file."""
        bad_path = tmp_path / "nonexistent.png"

        assert image_processor.validate_image_format(bad_path) is False
