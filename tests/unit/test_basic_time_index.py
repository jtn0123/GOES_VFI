"""Unit tests for TimeIndex core functionality."""

from datetime import datetime, timedelta
from pathlib import Path
import unittest

from goesvfi.integrity_check.time_index import (
    DEFAULT_CDN_RESOLUTION,
    SatellitePattern,
    is_recent,
    to_cdn_url,
    to_local_path,
    to_s3_key,
)


class TestBasicTimeIndex(unittest.TestCase):
    """Test cases for core TimeIndex functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Sample dates for testing
        self.test_date_recent = datetime(2023, 6, 15, 12, 30, 0)  # Recent date
        self.test_date_old = datetime(2022, 1, 1, 0, 0, 0)  # Old date

        # Test satellites
        self.goes16 = SatellitePattern.GOES_16
        self.goes18 = SatellitePattern.GOES_18

    def test_to_cdn_url(self) -> None:
        """Test generating CDN URLs."""
        # GOES-16 URL
        url = to_cdn_url(self.test_date_recent, self.goes16)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/13/"
            f"2023166123000_GOES16-ABI-FD-13-{DEFAULT_CDN_RESOLUTION}.jpg"
        )
        assert url == expected

        # GOES-18 URL
        url = to_cdn_url(self.test_date_recent, self.goes18)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/13/"
            f"2023166123000_GOES18-ABI-FD-13-{DEFAULT_CDN_RESOLUTION}.jpg"
        )
        assert url == expected

        # With custom resolution
        custom_res = "250m"
        url = to_cdn_url(self.test_date_recent, self.goes16, custom_res)
        expected = f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/13/2023166123000_GOES16-ABI-FD-13-{custom_res}.jpg"
        assert url == expected

    def test_to_s3_key(self) -> None:
        """Test generating S3 keys."""
        # Test GOES-16 RadF pattern
        key_radf_g16 = to_s3_key(self.test_date_old, self.goes16, product_type="RadF", band=13)
        # Make sure key matches expected pattern format
        assert key_radf_g16.startswith("ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C13_G16_s20220010")
        assert key_radf_g16.endswith("*_e*_c*.nc")

        # Test GOES-18 RadF pattern
        key_radf_g18 = to_s3_key(self.test_date_old, self.goes18, product_type="RadF", band=13)
        assert key_radf_g18.startswith("ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C13_G18_s20220010")
        assert key_radf_g18.endswith("*_e*_c*.nc")

        # Test GOES-16 RadC pattern
        key_radc_g16 = to_s3_key(self.test_date_old, self.goes16, product_type="RadC", band=13)
        assert key_radc_g16.startswith("ABI-L1b-RadC/2022/001/00/OR_ABI-L1b-RadC-M6C13_G16_s20220010")
        assert key_radc_g16.endswith("*_e*_c*.nc")

        # Test different band
        key_band1 = to_s3_key(self.test_date_old, self.goes16, product_type="RadF", band=1)
        assert key_band1.startswith("ABI-L1b-RadF/2022/001/00/OR_ABI-L1b-RadF-M6C01_G16_s20220010")
        assert key_band1.endswith("*_e*_c*.nc")

    def test_to_local_path(self) -> None:
        """Test generating local paths."""
        # GOES-16 path
        path = to_local_path(self.test_date_recent, self.goes16)
        expected = Path("2023/06/15/goes16_20230615_123000_band13.png")
        assert path == expected

        # GOES-18 path
        path = to_local_path(self.test_date_recent, self.goes18)
        expected = Path("2023/06/15/goes18_20230615_123000_band13.png")
        assert path == expected

    def test_is_recent(self) -> None:
        """Test the is_recent function."""
        # Set up a known cutoff time
        now = datetime(2023, 6, 20, 0, 0, 0)

        # Test dates
        recent_date = now - timedelta(days=3)  # Within window
        now - timedelta(days=7)  # At the window edge
        old_date = now - timedelta(days=14)  # Outside window

        # Test with monkeypatching datetime.now in the correct module
        with unittest.mock.patch("goesvfi.integrity_check.time_utils.timestamp.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = datetime

            # Test recent date
            assert is_recent(recent_date)

            # Test old date
            assert not is_recent(old_date)


if __name__ == "__main__":
    unittest.main()
