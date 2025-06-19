"""
Tests for GOES Satellite Imagery functionality
"""

import os
import shutil
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Mock boto3 and botocore before importing the module
with patch("boto3.client"), patch("botocore.UNSIGNED", create=True):
    from goesvfi.integrity_check.goes_imagery import (
        ChannelType,
        GOESImageryManager,
        ProductType,
    )


class TestGOESImagery(unittest.TestCase):
    """Tests for GOES Imagery functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a temp directory for test output
        self.test_dir = Path("test_goes_imagery_output")
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up after tests."""
        # Remove test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_channel_type_enum(self):
        """Test ChannelType enum."""
        # Test channel attributes
        self.assertEqual(ChannelType.CH13.number, 13)
        self.assertEqual(ChannelType.CH13.display_name, "Clean Longwave Window IR")
        self.assertEqual(ChannelType.CH13.wavelength, "10.3 μm")
        self.assertTrue("Surface temp" in ChannelType.CH13.description)

        # Test channel properties
        self.assertTrue(ChannelType.CH02.is_visible)
        self.assertFalse(ChannelType.CH02.is_infrared)

        self.assertTrue(ChannelType.CH13.is_infrared)
        self.assertFalse(ChannelType.CH13.is_visible)

        self.assertTrue(ChannelType.CH05.is_near_ir)

        self.assertTrue(ChannelType.CH08.is_water_vapor)

        # Test from_number
        self.assertEqual(ChannelType.from_number(13), ChannelType.CH13)
        self.assertIsNone(ChannelType.from_number(999))

        # Test composite channels
        self.assertTrue(ChannelType.TRUE_COLOR.is_composite)
        self.assertFalse(ChannelType.CH01.is_composite)

    def test_product_type_mapping(self):
        """Test ProductType mapping functions."""
        self.assertEqual(
            ProductType.to_s3_prefix(ProductType.FULL_DISK), "ABI-L1b-RadF"
        )

        self.assertEqual(ProductType.to_web_path(ProductType.FULL_DISK), "FD")

    @patch("goesvfi.integrity_check.goes_imagery.requests.get")
    def test_download_precolorized_image(self, mock_get):
        """Test downloading a pre-colorized image."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.content = b"test image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Mock boto3 client
        mock_s3 = MagicMock()

        # Create downloader with mocked S3 client
        downloader = GOESImageryDownloader(output_dir=self.test_dir)
        downloader.s3_client = mock_s3

        # Test download
        result = downloader.download_precolorized_image(
            channel=ChannelType.CH13, product_type=ProductType.FULL_DISK
        )

        # Verify result
        self.assertIsNotNone(result)
        self.assertTrue(result.exists())

        # Verify mock was called with correct URL
        expected_url = (
            "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/latest/13_1200x1200.jpg"
        )
        mock_get.assert_called_once_with(expected_url, timeout=30)

    def test_extract_timestamp_from_filename(self):
        """Test extracting timestamp from filename."""
        processor = GOESImageProcessor(output_dir=self.test_dir)

        # Test with a typical filename
        filename = "OR_ABI-L1b-RadF-M6C13_G16_s20233001550210_e20233001559530_c20233001559577.nc"
        result = processor._extract_timestamp_from_filename(filename)

        # Verify result (day 300 of 2023 = Oct 27, 2023)
        self.assertEqual(result, "20231027_155021")

    @patch(
        "goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_precolorized_image"
    )
    def test_get_imagery_product_mode(self, mock_download):
        """Test getting imagery in product mode."""
        # Setup mock
        expected_path = self.test_dir / "test_image.jpg"
        mock_download.return_value = expected_path

        # Create manager with mocked downloader
        manager = GOESImageryManager(output_dir=self.test_dir)
        manager.downloader.s3_client = MagicMock()

        # Test getting imagery
        result = manager.get_imagery(
            channel=ChannelType.CH13,
            product_type=ProductType.FULL_DISK,
            mode=ImageryMode.IMAGE_PRODUCT,
        )

        # Verify result
        self.assertEqual(result, expected_path)

        # Verify mock was called with correct arguments
        mock_download.assert_called_once_with(
            channel=ChannelType.CH13,
            product_type=ProductType.FULL_DISK,
            date=None,
            size="1200",
        )

    @patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.find_raw_data")
    @patch(
        "goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_raw_data"
    )
    @patch("goesvfi.integrity_check.goes_imagery.GOESImageProcessor.process_raw_data")
    def test_get_imagery_raw_mode(self, mock_process, mock_download, mock_find):
        """Test getting imagery in raw data mode."""
        # Setup mocks
        mock_find.return_value = "test_file_key"
        mock_download.return_value = Path("test_file_path")
        expected_path = self.test_dir / "test_processed_image.png"
        mock_process.return_value = expected_path

        # Create manager
        manager = GOESImageryManager(
            output_dir=self.test_dir, default_mode=ImageryMode.RAW_DATA
        )
        manager.downloader.s3_client = MagicMock()

        # Test getting imagery
        result = manager.get_imagery(
            channel=ChannelType.CH13, product_type=ProductType.FULL_DISK
        )

        # Verify result
        self.assertEqual(result, expected_path)

        # Verify mocks were called correctly
        mock_find.assert_called_once()
        mock_download.assert_called_once_with("test_file_key")
        mock_process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
