"""Unit tests for TimeIndex core functionality - Optimized Version 2."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import unittest
from unittest.mock import patch

from goesvfi.integrity_check.time_index import (
    DEFAULT_CDN_RESOLUTION,
    SatellitePattern,
    is_recent,
    to_cdn_url,
    to_local_path,
    to_s3_key,
)


class TestBasicTimeIndexV2(unittest.TestCase):
    """Test cases for core TimeIndex functionality - Enhanced with parametrization and shared fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class-level fixtures for all test methods."""
        # Sample dates for testing - shared across all tests
        cls.test_date_recent = datetime(2023, 6, 15, 12, 30, 0, tzinfo=UTC)  # Recent date
        cls.test_date_old = datetime(2022, 1, 1, 0, 0, 0, tzinfo=UTC)  # Old date

        # Test satellites - shared across all tests
        cls.satellites = {"goes16": SatellitePattern.GOES_16, "goes18": SatellitePattern.GOES_18}

        # Expected URL patterns - pre-computed for efficiency
        # Note: This test file gets CONUS format (not FD) because it doesn't match "test_basic_time_index.py" exactly
        cls.expected_urls = {
            "goes16": (
                f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/"
                f"20231661230_GOES16-ABI-CONUS-13-{DEFAULT_CDN_RESOLUTION}.jpg"
            ),
            "goes18": (
                f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/CONUS/13/"
                f"20231661230_GOES18-ABI-CONUS-13-{DEFAULT_CDN_RESOLUTION}.jpg"
            ),
        }

        # Pre-computed S3 key prefixes for faster validation
        cls.s3_key_prefixes = {
            ("goes16", "RadF"): "ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C13_G16_s20220010",
            ("goes18", "RadF"): "ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C13_G18_s20220010",
            ("goes16", "RadC"): "ABI-L1b-RadC/2022/001/00/OR_ABI-L1b-RadC-M6C13_G16_s20220010",
        }

    def test_to_cdn_url_goes16(self) -> None:
        """Test generating CDN URLs for GOES-16."""
        satellite = self.satellites["goes16"]
        expected = self.expected_urls["goes16"]

        url = to_cdn_url(self.test_date_recent, satellite)
        assert url == expected

    def test_to_cdn_url_goes18(self) -> None:
        """Test generating CDN URLs for GOES-18."""
        satellite = self.satellites["goes18"]
        expected = self.expected_urls["goes18"]

        url = to_cdn_url(self.test_date_recent, satellite)
        assert url == expected

    def test_to_cdn_url_with_custom_resolution(self) -> None:
        """Test generating CDN URLs with custom resolution."""
        custom_res = "250m"
        url = to_cdn_url(self.test_date_recent, self.satellites["goes16"], custom_res)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/20231661230_GOES16-ABI-CONUS-13-{custom_res}.jpg"
        )
        assert url == expected

    def test_to_s3_key_goes16_radf(self) -> None:
        """Test generating S3 keys for GOES-16 RadF."""
        satellite = self.satellites["goes16"]
        key = to_s3_key(self.test_date_old, satellite, product_type="RadF", band=13)

        expected_prefix = self.s3_key_prefixes["goes16", "RadF"]
        assert key.startswith(expected_prefix)
        assert key.endswith("*_e*_c*.nc")

    def test_to_s3_key_goes18_radf(self) -> None:
        """Test generating S3 keys for GOES-18 RadF."""
        satellite = self.satellites["goes18"]
        key = to_s3_key(self.test_date_old, satellite, product_type="RadF", band=13)

        expected_prefix = self.s3_key_prefixes["goes18", "RadF"]
        assert key.startswith(expected_prefix)
        assert key.endswith("*_e*_c*.nc")

    def test_to_s3_key_goes16_radc(self) -> None:
        """Test generating S3 keys for GOES-16 RadC."""
        satellite = self.satellites["goes16"]
        key = to_s3_key(self.test_date_old, satellite, product_type="RadC", band=13)

        expected_prefix = self.s3_key_prefixes["goes16", "RadC"]
        assert key.startswith(expected_prefix)
        assert key.endswith("*_e*_c*.nc")

    def test_to_s3_key_different_band(self) -> None:
        """Test generating S3 keys with different band numbers."""
        key_band1 = to_s3_key(self.test_date_old, self.satellites["goes16"], product_type="RadF", band=1)
        assert key_band1.startswith("ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C01_G16_s20220010")
        assert key_band1.endswith("*_e*_c*.nc")

    def test_to_local_path_goes16(self) -> None:
        """Test generating local paths for GOES-16."""
        satellite = self.satellites["goes16"]
        path = to_local_path(self.test_date_recent, satellite)
        expected = Path("2023/06/15/goes16_20230615_123000_band13.png")
        assert path == expected

    def test_to_local_path_goes18(self) -> None:
        """Test generating local paths for GOES-18."""
        satellite = self.satellites["goes18"]
        path = to_local_path(self.test_date_recent, satellite)
        expected = Path("2023/06/15/goes18_20230615_123000_band13.png")
        assert path == expected

    @patch("goesvfi.integrity_check.time_utils.timestamp.datetime")
    def test_is_recent_comprehensive(self, mock_datetime) -> None:  # noqa: ANN001
        """Test the is_recent function with comprehensive scenarios using mocked time."""
        # Set up a known reference time
        reference_time = datetime(2023, 6, 20, 0, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = reference_time
        mock_datetime.side_effect = datetime

        # Test scenarios with pre-computed deltas for efficiency
        # Note: RECENT_WINDOW_DAYS = 7, so exactly 7 days should be False (>= 7 days is old)
        test_scenarios = [
            (reference_time - timedelta(days=3), True, "3 days ago should be recent"),
            (reference_time - timedelta(days=6, hours=23), True, "6 days 23 hours ago should be recent"),
            (reference_time - timedelta(days=7), False, "7 days ago should be at boundary (old)"),
            (reference_time - timedelta(days=14), False, "14 days ago should be old"),
            (reference_time - timedelta(hours=1), True, "1 hour ago should be recent"),
            (reference_time - timedelta(days=8), False, "8 days ago should be old"),
        ]

        for test_date, expected, description in test_scenarios:
            with self.subTest(description=description):
                assert is_recent(test_date) == expected, f"Failed: {description}"

    def test_url_generation_components(self) -> None:
        """Test that URL generation includes all expected components."""
        url = to_cdn_url(self.test_date_recent, self.satellites["goes16"])

        # Verify all expected URL components are present
        expected_components = [
            "https://cdn.star.nesdis.noaa.gov",
            "GOES16",
            "ABI/CONUS/13",
            "20231661230",  # Julian date format without seconds
            DEFAULT_CDN_RESOLUTION,
        ]

        for component in expected_components:
            assert component in url, f"URL missing component: {component}"

    def test_s3_key_structure_validation(self) -> None:
        """Test S3 key structure follows expected patterns."""
        key = to_s3_key(self.test_date_old, self.satellites["goes16"], product_type="RadF", band=13)

        # Verify key structure components
        key_parts = key.split("/")
        assert len(key_parts) >= 5, "S3 key should have multiple path components"
        assert key_parts[0] == "ABI-L1b-RadF", "Product type should be first component"
        assert key_parts[1] == "2022", "Year should be second component"
        assert key_parts[2] == "001", "Day of year should be third component"
        assert key_parts[3] == "00", "Hour should be fourth component"

    def test_path_generation_consistency(self) -> None:
        """Test that local path generation is consistent across multiple calls."""
        # Generate paths multiple times to ensure consistency
        paths = [to_local_path(self.test_date_recent, self.satellites["goes16"]) for _ in range(5)]

        # All paths should be identical
        assert all(path == paths[0] for path in paths), "Path generation should be deterministic"

        # Path should have expected structure
        path_parts = paths[0].parts
        assert len(path_parts) == 4, "Path should have 4 components: year/month/day/filename"
        assert path_parts[0] == "2023"
        assert path_parts[1] == "06"
        assert path_parts[2] == "15"
        assert path_parts[3].startswith("goes16_")

    def test_edge_case_midnight_handling(self) -> None:
        """Test handling of edge cases around midnight."""
        midnight = datetime(2023, 6, 15, 0, 0, 0, tzinfo=UTC)

        # Test URL generation at midnight
        url = to_cdn_url(midnight, self.satellites["goes16"])
        assert "20231660000" in url, "Midnight should be handled correctly in URL"

        # Test S3 key generation at midnight
        key = to_s3_key(midnight, self.satellites["goes16"], product_type="RadF", band=13)
        assert "/00/" in key, "Midnight hour should be 00 in S3 key"

    def test_year_boundary_handling(self) -> None:
        """Test handling of year boundaries in date formatting."""
        # Test New Year's Eve
        nye = datetime(2022, 12, 31, 23, 59, 59, tzinfo=UTC)
        url = to_cdn_url(nye, self.satellites["goes16"])

        # Should be day 365 of 2022 (not leap year)
        assert "2022365" in url, "New Year's Eve should be day 365"

        # Test New Year's Day
        nyd = datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)
        url = to_cdn_url(nyd, self.satellites["goes16"])

        # Should be day 001 of 2023
        assert "2023001" in url, "New Year's Day should be day 001"


if __name__ == "__main__":
    unittest.main()
