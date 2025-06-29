"""Tests for VFI crop parameter handling."""

import pytest

from goesvfi.pipeline.vfi_crop_handler import VFICropHandler


class TestVFICropHandler:
    """Test the VFICropHandler class."""

    @pytest.fixture()
    def crop_handler(self):
        """Create a crop handler instance."""
        return VFICropHandler()

    def test_crop_handler_initialization(self, crop_handler) -> None:
        """Test crop handler initializes correctly."""
        assert isinstance(crop_handler, VFICropHandler)

    def test_validate_crop_parameters_none_input(self, crop_handler) -> None:
        """Test validation with None input."""
        result = crop_handler.validate_crop_parameters(None)
        assert result is None

    def test_validate_crop_parameters_valid_input(self, crop_handler) -> None:
        """Test validation with valid crop parameters."""
        # Test case: x=10, y=20, width=100, height=200
        crop_rect_xywh = (10, 20, 100, 200)
        expected = (10, 20, 110, 220)  # (left, upper, right, bottom)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result == expected

    def test_validate_crop_parameters_zero_coordinates(self, crop_handler) -> None:
        """Test validation with zero coordinates (valid)."""
        crop_rect_xywh = (0, 0, 50, 50)
        expected = (0, 0, 50, 50)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result == expected

    def test_validate_crop_parameters_invalid_negative_width(self, crop_handler) -> None:
        """Test validation with negative width."""
        crop_rect_xywh = (10, 20, -50, 100)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        # Should return None (disable cropping) rather than raise
        assert result is None

    def test_validate_crop_parameters_invalid_negative_height(self, crop_handler) -> None:
        """Test validation with negative height."""
        crop_rect_xywh = (10, 20, 100, -50)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result is None

    def test_validate_crop_parameters_invalid_zero_width(self, crop_handler) -> None:
        """Test validation with zero width."""
        crop_rect_xywh = (10, 20, 0, 100)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result is None

    def test_validate_crop_parameters_invalid_zero_height(self, crop_handler) -> None:
        """Test validation with zero height."""
        crop_rect_xywh = (10, 20, 100, 0)

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result is None

    def test_validate_crop_parameters_wrong_tuple_size(self, crop_handler) -> None:
        """Test validation with wrong tuple size."""
        crop_rect_xywh = (10, 20, 100)  # Missing height

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        assert result is None

    def test_validate_crop_parameters_non_tuple_input(self, crop_handler) -> None:
        """Test validation with non-tuple input."""
        crop_rect_xywh = [10, 20, 100, 200]  # List instead of tuple

        result = crop_handler.validate_crop_parameters(crop_rect_xywh)
        # Should still work since it unpacks to x, y, w, h
        expected = (10, 20, 110, 220)
        assert result == expected

    def test_validate_crop_against_image_valid(self, crop_handler) -> None:
        """Test crop validation against image dimensions - valid case."""
        crop_rect_pil = (10, 20, 110, 220)  # 100x200 crop at (10,20)
        image_width = 500
        image_height = 400

        # Should not raise any exception
        crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_validate_crop_against_image_exceeds_width(self, crop_handler) -> None:
        """Test crop validation when crop exceeds image width."""
        crop_rect_pil = (10, 20, 600, 220)  # right=600 > image_width=500
        image_width = 500
        image_height = 400

        with pytest.raises(ValueError, match="exceeds image dimensions"):
            crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_validate_crop_against_image_exceeds_height(self, crop_handler) -> None:
        """Test crop validation when crop exceeds image height."""
        crop_rect_pil = (10, 20, 110, 500)  # bottom=500 > image_height=400
        image_width = 500
        image_height = 400

        with pytest.raises(ValueError, match="exceeds image dimensions"):
            crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_validate_crop_against_image_negative_coordinates(self, crop_handler) -> None:
        """Test crop validation with negative coordinates."""
        crop_rect_pil = (-10, 20, 110, 220)  # left=-10 < 0
        image_width = 500
        image_height = 400

        with pytest.raises(ValueError, match="negative coordinates"):
            crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_validate_crop_against_image_invalid_rectangle(self, crop_handler) -> None:
        """Test crop validation with invalid rectangle (right <= left)."""
        crop_rect_pil = (110, 20, 100, 220)  # right=100 <= left=110
        image_width = 500
        image_height = 400

        with pytest.raises(ValueError, match="right <= left"):
            crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_validate_crop_against_image_zero_height(self, crop_handler) -> None:
        """Test crop validation with zero height rectangle."""
        crop_rect_pil = (10, 220, 110, 220)  # bottom=220 <= upper=220
        image_width = 500
        image_height = 400

        with pytest.raises(ValueError, match="bottom <= upper"):
            crop_handler.validate_crop_against_image(crop_rect_pil, image_width, image_height, "test_image")

    def test_get_crop_info_none(self, crop_handler) -> None:
        """Test get_crop_info with None input."""
        result = crop_handler.get_crop_info(None)

        expected = {"enabled": False, "rectangle": None, "width": None, "height": None}
        assert result == expected

    def test_get_crop_info_valid_crop(self, crop_handler) -> None:
        """Test get_crop_info with valid crop rectangle."""
        crop_rect_pil = (10, 20, 110, 220)  # 100x200 crop at (10,20)

        result = crop_handler.get_crop_info(crop_rect_pil)

        expected = {
            "enabled": True,
            "rectangle": (10, 20, 110, 220),
            "left": 10,
            "upper": 20,
            "right": 110,
            "bottom": 220,
            "width": 100,
            "height": 200,
        }
        assert result == expected

    def test_format_crop_for_logging_none(self, crop_handler) -> None:
        """Test crop formatting for logging with None input."""
        result = crop_handler.format_crop_for_logging(None)
        assert result == "no crop"

    def test_format_crop_for_logging_valid_crop(self, crop_handler) -> None:
        """Test crop formatting for logging with valid crop."""
        crop_rect_pil = (10, 20, 110, 220)  # 100x200 crop at (10,20)

        result = crop_handler.format_crop_for_logging(crop_rect_pil)
        expected = "crop(10,20)+100x200"
        assert result == expected

    def test_format_crop_for_logging_edge_case(self, crop_handler) -> None:
        """Test crop formatting for logging with edge case."""
        crop_rect_pil = (0, 0, 1, 1)  # 1x1 crop at origin

        result = crop_handler.format_crop_for_logging(crop_rect_pil)
        expected = "crop(0,0)+1x1"
        assert result == expected
