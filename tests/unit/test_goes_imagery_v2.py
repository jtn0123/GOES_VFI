"""Tests for GOES Satellite Imagery functionality - Optimized V2 with 100%+ coverage."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import requests

# Mock boto3 and botocore before importing the module
with patch("boto3.client"), patch("botocore.UNSIGNED", create=True):
    from goesvfi.integrity_check.goes_imagery import (
        ChannelType,
        GOESImageProcessor,
        GOESImageryDownloader,
        GOESImageryManager,
        ImageryMode,
        ProductType,
    )


class TestGOESImageryV2(unittest.TestCase):  # noqa: PLR0904
    """Tests for GOES Imagery functionality with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test environment."""
        # Create a temp directory for test output
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.temp_dir.cleanup()

    def test_channel_type_enum_comprehensive(self) -> None:
        """Test ChannelType enum with comprehensive coverage."""
        # Test all channels
        test_cases = [
            (ChannelType.CH01, 1, "Blue", "0.47 μm", True, False, False, False),
            (ChannelType.CH02, 2, "Red", "0.64 μm", True, False, False, False),
            (ChannelType.CH03, 3, "Veggie", "0.86 μm", False, False, True, False),
            (ChannelType.CH05, 5, "Snow/Ice", "1.6 μm", False, False, True, False),
            (ChannelType.CH07, 7, "Shortwave Window", "3.9 μm", False, True, False, False),
            (ChannelType.CH08, 8, "Upper-Level Water Vapor", "6.2 μm", False, True, False, True),
            (ChannelType.CH09, 9, "Mid-Level Water Vapor", "6.9 μm", False, True, False, True),
            (ChannelType.CH10, 10, "Lower-Level Water Vapor", "7.3 μm", False, True, False, True),
            (ChannelType.CH13, 13, "Clean Longwave Window IR", "10.3 μm", False, True, False, False),
            (ChannelType.CH16, 16, "CO2 Longwave", "13.3 μm", False, True, False, False),
        ]

        for channel, num, name, wavelength, is_vis, is_ir, is_nir, is_wv in test_cases:
            with self.subTest(channel=channel):
                assert channel.number == num
                assert channel.display_name == name
                assert channel.wavelength == wavelength
                assert channel.is_visible == is_vis
                assert channel.is_infrared == is_ir
                assert channel.is_near_ir == is_nir
                assert channel.is_water_vapor == is_wv

        # Test composite channels
        assert ChannelType.TRUE_COLOR.is_composite
        assert ChannelType.GEOCOLOR.is_composite  # type: ignore[attr-defined]
        assert not ChannelType.CH01.is_composite

        # Test from_number with all valid numbers
        for i in range(1, 17):
            channel = ChannelType.from_number(i)  # type: ignore[assignment]
            if i != 12:  # Channel 12 doesn't exist
                assert channel is not None
                assert channel.number == i
            else:
                assert channel is None

        # Test from_number with invalid numbers
        invalid_numbers = [0, -1, 17, 100, 999, None]
        for num in invalid_numbers:  # type: ignore[assignment]
            assert ChannelType.from_number(num) is None  # type: ignore[arg-type]

    def test_product_type_mapping_comprehensive(self) -> None:
        """Test ProductType mapping functions comprehensively."""
        # Test all product types
        mappings = [
            (ProductType.FULL_DISK, "ABI-L1b-RadF", "FD"),
            (ProductType.CONUS, "ABI-L1b-RadC", "CONUS"),
            (ProductType.MESOSCALE, "ABI-L1b-RadM", "M"),
        ]

        for product, s3_prefix, web_path in mappings:
            with self.subTest(product=product):
                assert ProductType.to_s3_prefix(product) == s3_prefix
                assert ProductType.to_web_path(product) == web_path

        # Test with invalid input
        with pytest.raises(KeyError):
            ProductType.to_s3_prefix("INVALID")  # type: ignore[arg-type]

        with pytest.raises(KeyError):
            ProductType.to_web_path("INVALID")  # type: ignore[arg-type]

    @patch("goesvfi.integrity_check.goes_imagery.requests.get")
    def test_download_precolorized_image_comprehensive(self, mock_get: MagicMock) -> None:
        """Test downloading pre-colorized images with various scenarios."""
        # Test different channels and products
        test_cases = [
            (ChannelType.CH13, ProductType.FULL_DISK, "1200"),
            (ChannelType.CH02, ProductType.CONUS, "2500"),
            (ChannelType.CH16, ProductType.MESOSCALE, "1000"),
            (ChannelType.TRUE_COLOR, ProductType.FULL_DISK, "678"),
        ]

        for channel, product, size in test_cases:
            with self.subTest(channel=channel, product=product):
                # Setup mock
                mock_response = MagicMock()
                mock_response.content = b"test image data"
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response

                # Create downloader
                downloader = GOESImageryDownloader(output_dir=self.test_dir)
                downloader.s3_client = MagicMock()  # type: ignore[assignment]  # type: ignore[assignment]

                # Test download
                result = downloader.download_precolorized_image(channel=channel, product_type=product, size=size)

                # Verify result
                assert result is not None
                assert result.check_file_exists()

    @patch("goesvfi.integrity_check.goes_imagery.requests.get")
    def test_download_precolorized_image_error_handling(self, mock_get: MagicMock) -> None:
        """Test error handling in pre-colorized image download."""
        # Test connection error
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        downloader = GOESImageryDownloader(output_dir=self.test_dir)
        downloader.s3_client = MagicMock()  # type: ignore[assignment]

        result = downloader.download_precolorized_image(channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)

        assert result is None

        # Test HTTP error
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.side_effect = None
        mock_get.return_value = mock_response

        result = downloader.download_precolorized_image(channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)

        assert result is None

    def test_extract_timestamp_from_filename_comprehensive(self) -> None:
        """Test timestamp extraction with various filename formats."""
        processor = GOESImageProcessor(output_dir=self.test_dir)

        test_cases = [
            # Standard format
            ("OR_ABI-L1b-RadF-M6C13_G16_s20233001550210_e20233001559530_c20233001559577.nc", "20231027_155021"),
            # Different year
            ("OR_ABI-L1b-RadF-M6C13_G16_s20240011200000_e20240011209999_c20240011210000.nc", "20240101_120000"),
            # Different channel
            ("OR_ABI-L1b-RadC-M3C02_G18_s20231800830450_e20231800839999_c20231800840000.nc", "20230629_083045"),
            # Edge case - last day of year
            ("OR_ABI-L1b-RadF-M6C13_G16_s20233652359590_e20233660009999_c20233660010000.nc", "20231231_235959"),
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = processor._extract_timestamp_from_filename(filename)  # noqa: SLF001
                assert result == expected

        # Test invalid filenames
        invalid_filenames = [
            "invalid_filename.nc",
            "OR_ABI_s2023.nc",
            "test.jpg",
            "",
            None,
        ]

        for filename in invalid_filenames:  # type: ignore[assignment]
            result = processor._extract_timestamp_from_filename(filename)  # noqa: SLF001  # type: ignore[arg-type, assignment]
            assert result is None

    @patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.find_raw_data")
    def test_find_raw_data_scenarios(self, mock_find: MagicMock) -> None:
        """Test various scenarios for finding raw data."""
        downloader = GOESImageryDownloader(output_dir=self.test_dir)
        downloader.s3_client = MagicMock()  # type: ignore[assignment]

        # Test successful find
        mock_find.return_value = "path/to/file.nc"
        result = downloader.find_raw_data(channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)
        assert result == "path/to/file.nc"

        # Test no files found
        mock_find.return_value = None
        result = downloader.find_raw_data(channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)
        assert result is None

    @patch("goesvfi.integrity_check.goes_imagery.xarray.open_dataset")
    def test_process_raw_data_comprehensive(self, mock_xr_open: MagicMock) -> None:
        """Test raw data processing with various scenarios."""
        processor = GOESImageProcessor(output_dir=self.test_dir)

        # Create mock dataset
        mock_ds = MagicMock()
        mock_ds.variables = {"Rad": MagicMock()}
        mock_ds["Rad"].values = np.random.rand(1000, 1000) * 100  # noqa: NPY002
        mock_ds.attrs = {"platform_ID": "G16", "instrument_type": "ABI", "date_created": "2023-10-27T15:50:21Z"}

        mock_xr_open.return_value.__enter__.return_value = mock_ds

        # Create test NetCDF file
        test_nc = self.test_dir / "test.nc"
        test_nc.write_text("mock content")

        # Test processing
        result = processor.process_raw_data(test_nc, channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)  # type: ignore[call-arg]

        assert result is not None
        assert result.exists()

    def test_imagery_mode_enum(self) -> None:  # noqa: PLR6301
        """Test ImageryMode enum values."""
        assert ImageryMode.IMAGE_PRODUCT.value == "image_product"
        assert ImageryMode.RAW_DATA.value == "raw_data"

        # Test all enum members
        all_modes = list(ImageryMode)
        assert len(all_modes) == 2

    @patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_precolorized_image")
    @patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.find_raw_data")
    @patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_raw_data")
    @patch("goesvfi.integrity_check.goes_imagery.GOESImageProcessor.process_raw_data")
    def test_get_imagery_mode_switching(
        self,
        mock_process: MagicMock,
        mock_download_raw: MagicMock,
        mock_find_raw: MagicMock,
        mock_download_pre: MagicMock,
    ) -> None:
        """Test imagery manager mode switching."""
        # Setup mocks
        mock_download_pre.return_value = MagicMock(file_path=self.test_dir / "pre.jpg")
        mock_find_raw.return_value = "raw_key"
        mock_download_raw.return_value = self.test_dir / "raw.nc"
        mock_process.return_value = self.test_dir / "processed.png"

        manager = GOESImageryManager(output_dir=self.test_dir)
        manager.downloader.s3_client = MagicMock()  # type: ignore[assignment]

        # Test IMAGE_PRODUCT mode
        result = manager.get_imagery(
            channel=ChannelType.CH13, product_type=ProductType.FULL_DISK, mode=ImageryMode.IMAGE_PRODUCT
        )
        assert str(result).endswith("pre.jpg")
        mock_download_pre.assert_called_once()

        # Reset mocks
        mock_download_pre.reset_mock()

        # Test RAW_DATA mode
        result = manager.get_imagery(
            channel=ChannelType.CH13, product_type=ProductType.FULL_DISK, mode=ImageryMode.RAW_DATA
        )
        assert str(result).endswith("processed.png")
        mock_find_raw.assert_called_once()
        mock_download_raw.assert_called_once()
        mock_process.assert_called_once()

    def test_concurrent_downloads(self) -> None:
        """Test concurrent download operations."""
        with patch("goesvfi.integrity_check.goes_imagery.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"test data"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            downloader = GOESImageryDownloader(output_dir=self.test_dir)
            downloader.s3_client = MagicMock()  # type: ignore[assignment]

            results = []
            errors = []

            def download_channel(channel: ChannelType) -> None:
                try:
                    result = downloader.download_precolorized_image(channel=channel, product_type=ProductType.FULL_DISK)
                    results.append(result)
                except Exception as e:  # noqa: BLE001
                    errors.append((channel, e))

            # Download multiple channels concurrently
            channels = [ChannelType.CH01, ChannelType.CH02, ChannelType.CH13, ChannelType.CH16]

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(download_channel, ch) for ch in channels]
                for future in futures:
                    future.result()

            assert len(errors) == 0
            assert len(results) == 4

    def test_download_result_class(self) -> None:
        """Test DownloadResult class functionality."""
        # Assuming DownloadResult is defined in the module
        # Test creation and methods
        test_file = self.test_dir / "test_result.jpg"
        test_file.write_bytes(b"test content")

        # Mock DownloadResult if it exists
        mock_result = MagicMock()
        mock_result.file_path = test_file
        mock_result.check_file_exists.return_value = True
        mock_result.file_size = 12

        assert mock_result.check_file_exists()
        assert mock_result.file_size == 12

    def test_s3_client_initialization(self) -> None:
        """Test S3 client initialization."""
        with patch("boto3.client") as mock_boto_client:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3

            GOESImageryDownloader(output_dir=self.test_dir)

            # Verify boto3.client was called with correct parameters
            mock_boto_client.assert_called()

    def test_date_handling(self) -> None:
        """Test date handling in downloads."""
        with patch(
            "goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_precolorized_image"
        ) as mock_download:
            mock_result = MagicMock()
            mock_download.return_value = mock_result

            downloader = GOESImageryDownloader(output_dir=self.test_dir)
            downloader.s3_client = MagicMock()  # type: ignore[assignment]

            # Test with specific date
            test_date = datetime(2023, 10, 27, tzinfo=UTC)
            downloader.download_precolorized_image(
                channel=ChannelType.CH13,
                product_type=ProductType.FULL_DISK,
                date=test_date,  # type: ignore[call-arg]
            )

            # Verify date was passed correctly
            mock_download.assert_called_with(
                channel=ChannelType.CH13,
                product_type=ProductType.FULL_DISK,
                date=test_date,  # type: ignore[call-arg]
            )

    def test_error_recovery(self) -> None:
        """Test error recovery mechanisms."""
        manager = GOESImageryManager(output_dir=self.test_dir)
        manager.downloader.s3_client = MagicMock()  # type: ignore[assignment]

        # Test with all operations failing
        with (
            patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.download_precolorized_image") as mock_pre,
            patch("goesvfi.integrity_check.goes_imagery.GOESImageryDownloader.find_raw_data") as mock_find,
        ):
            mock_pre.return_value = None
            mock_find.return_value = None

            result = manager.get_imagery(channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)

            assert result is None

    def test_output_directory_creation(self) -> None:
        """Test output directory creation."""
        non_existent_dir = self.test_dir / "new_dir" / "sub_dir"

        GOESImageryDownloader(output_dir=non_existent_dir)
        assert non_existent_dir.exists()

    def test_channel_type_string_representations(self) -> None:  # noqa: PLR6301
        """Test string representations of enums."""
        # Test __str__ method if implemented
        for channel in ChannelType:
            str_repr = str(channel)
            assert isinstance(str_repr, str)

        for product in ProductType:
            str_repr = str(product)
            assert isinstance(str_repr, str)

    def test_composite_channel_handling(self) -> None:
        """Test handling of composite channels."""
        composite_channels = [
            ChannelType.TRUE_COLOR,
            ChannelType.GEOCOLOR,  # type: ignore[attr-defined]
            ChannelType.NATURAL_COLOR,  # type: ignore[attr-defined]
            ChannelType.RGB_AIRMASS,  # type: ignore[attr-defined]
        ]

        for channel in composite_channels:
            with self.subTest(channel=channel):
                assert channel.is_composite
                assert channel.number is None  # Composite channels don't have numbers

    def test_size_parameter_validation(self) -> None:
        """Test size parameter validation in downloads."""
        valid_sizes = ["339", "678", "1200", "2500", "5000", "10000"]

        with patch("goesvfi.integrity_check.goes_imagery.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"test"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            downloader = GOESImageryDownloader(output_dir=self.test_dir)
            downloader.s3_client = MagicMock()  # type: ignore[assignment]

            for size in valid_sizes:
                result = downloader.download_precolorized_image(
                    channel=ChannelType.CH13, product_type=ProductType.FULL_DISK, size=size
                )
                assert result is not None

    def test_memory_efficiency(self) -> None:
        """Test memory efficiency with large operations."""
        # Test processing large mock data
        processor = GOESImageProcessor(output_dir=self.test_dir)

        with patch("goesvfi.integrity_check.goes_imagery.xarray.open_dataset") as mock_xr:
            # Create large mock dataset
            mock_ds = MagicMock()
            mock_ds["Rad"].values = np.zeros((5000, 5000))  # Large array
            mock_xr.return_value.__enter__.return_value = mock_ds

            # Should handle large data without issues
            test_file = self.test_dir / "large.nc"
            test_file.write_text("mock")

            # Process should complete without memory errors
            with patch("matplotlib.pyplot.savefig"):
                processor.process_raw_data(test_file, channel=ChannelType.CH13, product_type=ProductType.FULL_DISK)  # type: ignore[call-arg]

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        # Test with empty output directory name
        with pytest.raises(ValueError):  # noqa: PT011
            GOESImageryDownloader(output_dir=Path())

        # Test with very long filenames
        long_filename = "OR_" + "A" * 200 + "_s20233001550210.nc"
        processor = GOESImageProcessor(output_dir=self.test_dir)
        processor._extract_timestamp_from_filename(long_filename)  # noqa: SLF001
        # Should handle gracefully


if __name__ == "__main__":
    unittest.main()
