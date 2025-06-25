"""Unit tests for S3 key patterns using real GOES data patterns."""

import re
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SatellitePattern,
    TimeIndex,
    filter_s3_keys_by_band,
    to_s3_key,
)


class TestRealS3Patterns(unittest.TestCase):
    """Test case for S3 key patterns using real GOES data samples."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample dates for testing
        self.test_date = datetime(2023, 6, 15, 12, 30, 0)
        self.test_date_2 = datetime(2024, 4, 1, 10, 15, 0)  # April 1, 2024 - day of year 092

    def test_radf_minutes_pattern(self):
        """Test if RadF minutes pattern matches expected schedule."""
        self.assertEqual(RADF_MINUTES, [0, 10, 20, 30, 40, 50])
        # Intervals should be 10 minutes apart
        for i in range(len(RADF_MINUTES) - 1):
            self.assertEqual(RADF_MINUTES[i + 1] - RADF_MINUTES[i], 10)

    def test_radc_minutes_pattern(self):
        """Test if RadC minutes pattern matches expected schedule."""
        self.assertEqual(RADC_MINUTES, [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56])
        # Intervals should be 5 minutes apart
        for i in range(len(RADC_MINUTES) - 1):
            self.assertEqual(RADC_MINUTES[i + 1] - RADC_MINUTES[i], 5)

    def test_radm_minutes_pattern(self):
        """Test if RadM minutes pattern matches expected schedule."""
        # Should include all minutes 0-59
        self.assertEqual(RADM_MINUTES, list(range(60)))
        self.assertEqual(len(RADM_MINUTES), 60)

    def test_to_s3_key_radf_format(self):
        """Test that RadF keys have the correct format."""
        # Test with exact timestamp at a RadF minute (0, 10, 20, 30, 40, 50)
        test_ts = datetime(2023, 6, 15, 12, 0, 0)  # 12:00, which is a RadF time
        key = to_s3_key(test_ts, SatellitePattern.GOES_18, product_type="RadF", band=13)

        # Check that key has the correct basic structure
        self.assertTrue(key.startswith("ABI-L1b-RadF/2023/166/12/"))

        # Check for satellite code and band
        self.assertIn("M6C13_G18_s", key)

        # Check for the correct minute (should use 00 here)
        pattern = re.compile(r"s2023166120([0-9][0-9])")
        match = pattern.search(key)
        if match:
            minute_str = match.group(1)
            self.assertEqual(minute_str, "00")
        else:
            self.fail("Could not find timestamp pattern in key")

    def test_to_s3_key_radc_format(self):
        """Test that RadC keys have the correct format."""
        # Test with timestamp close to a RadC minute (1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)
        test_ts = datetime(2023, 6, 15, 12, 14, 0)  # 12:14, closest is 12:11
        key = to_s3_key(test_ts, SatellitePattern.GOES_16, product_type="RadC", band=13)

        # Check that key has the correct basic structure
        self.assertTrue(key.startswith("ABI-L1b-RadC/2023/166/12/"))

        # Check for satellite code and band
        self.assertIn("M6C13_G16_s", key)

        # Check for the correct minute (should use 11 here, which is the nearest RadC minute before 14)
        pattern = re.compile(r"s2023166121([0-9][0-9])")  # Fixed to use hour 12 (not 20)
        match = pattern.search(key)
        if match:
            minute_str = match.group(1)
            self.assertEqual(minute_str, "11")
        else:
            self.fail(f"Could not find timestamp pattern in key: {key}")

    def test_to_s3_key_band_format(self):
        """Test that keys with different bands have the correct format."""
        # Test band 1
        key_band1 = to_s3_key(self.test_date, SatellitePattern.GOES_18, product_type="RadC", band=1)
        self.assertIn("M6C01_G18_s", key_band1)

        # Test band 13
        key_band13 = to_s3_key(self.test_date, SatellitePattern.GOES_18, product_type="RadC", band=13)
        self.assertIn("M6C13_G18_s", key_band13)

        # Test band 9
        key_band9 = to_s3_key(self.test_date, SatellitePattern.GOES_18, product_type="RadC", band=9)
        self.assertIn("M6C09_G18_s", key_band9)

    def test_to_s3_key_wildcard_handling(self):
        """Test that keys have correct wildcard patterns."""
        # Test with exact_match=False (should include wildcards)
        key_with_wildcards = to_s3_key(
            self.test_date,
            SatellitePattern.GOES_16,
            product_type="RadC",
            band=13,
            exact_match=False,
        )
        self.assertIn("*", key_with_wildcards)

        # Test with exact_match=True (should not include wildcards)
        key_without_wildcards = to_s3_key(
            self.test_date,
            SatellitePattern.GOES_16,
            product_type="RadC",
            band=13,
            exact_match=True,
        )
        self.assertNotIn("*", key_without_wildcards)

    def test_filter_s3_keys_by_band(self):
        """Test filtering S3 keys by band number."""
        # Create test keys with different bands
        keys = [
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166121100_e2023166121159_c20231661212.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C01_G16_s2023166121100_e2023166121159_c20231661212.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G16_s2023166121100_e2023166121159_c20231661212.nc",
            "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s2023166120000_e2023166120590_c20231661206.nc",
        ]

        # Filter for Band 13
        band13_keys = filter_s3_keys_by_band(keys, 13)
        self.assertEqual(len(band13_keys), 2)
        for key in band13_keys:
            self.assertIn("C13_", key)

        # Filter for Band 1
        band1_keys = filter_s3_keys_by_band(keys, 1)
        self.assertEqual(len(band1_keys), 1)
        self.assertIn("C01_", band1_keys[0])

        # Filter for Band 2
        band2_keys = filter_s3_keys_by_band(keys, 2)
        self.assertEqual(len(band2_keys), 1)
        self.assertIn("C02_", band2_keys[0])

    def test_real_file_pattern_examples(self):
        """Test with real file pattern examples from S3."""
        # Example file patterns from real GOES data in S3
        real_patterns = [
            # RadF (Full Disk) examples
            "OR_ABI-L1b-RadF-M6C13_G16_s20230661200000_e20230661209214_c20230661209291.nc",
            "OR_ABI-L1b-RadF-M6C13_G18_s20240920100012_e20240920109307_c20240920109383.nc",
            # RadC (CONUS) examples
            "OR_ABI-L1b-RadC-M6C13_G16_s20231661206190_e20231661208562_c20231661209032.nc",
            "OR_ABI-L1b-RadC-M6C13_G18_s20240920101189_e20240920103562_c20240920104022.nc",
            # RadM (Mesoscale) examples
            "OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
            "OR_ABI-L1b-RadM1-M6C13_G18_s20240920100245_e20240920100302_c20240920100347.nc",
        ]

        # Verify that our band extraction pattern works for these real examples
        for file_pattern in real_patterns:
            if "C13_" in file_pattern:
                filtered = filter_s3_keys_by_band([file_pattern], 13)
                self.assertEqual(len(filtered), 1, f"Failed to filter band 13 from {file_pattern}")
                self.assertEqual(filtered[0], file_pattern)

    def test_doy_handling_in_keys(self):
        """Test that day of year is correctly calculated and formatted in S3 keys."""
        # April 1, 2024 is day of year 92
        test_date = datetime(2024, 4, 1, 12, 0, 0)
        key = to_s3_key(test_date, SatellitePattern.GOES_18, product_type="RadC", band=13)

        # Day of year should be formatted as 092 (3 digits with leading zeros)
        self.assertIn("/092/", key)
        self.assertIn("s2024092", key)

        # Test with a day in November (day of year > 300)
        test_date_2 = datetime(2024, 11, 1, 12, 0, 0)  # November 1 is day 306 in 2024 (leap year)
        key_2 = to_s3_key(test_date_2, SatellitePattern.GOES_18, product_type="RadC", band=13)

        # Day of year should be formatted as 306 (3 digits)
        self.assertIn("/306/", key_2)
        self.assertIn("s2024306", key_2)

        # Test with leap year February 29
        leap_day = datetime(2024, 2, 29, 12, 0, 0)  # February 29 is day 60 in 2024
        key_3 = to_s3_key(leap_day, SatellitePattern.GOES_18, product_type="RadC", band=13)

        # Day of year should be formatted as 060 (3 digits with leading zero)
        self.assertIn("/060/", key_3)
        self.assertIn("s2024060", key_3)

    def test_nearest_valid_minute_selection(self):
        """Test that the nearest valid minute is correctly selected for each product type."""
        # RadF should select 30 for timestamp with minute=32
        test_ts_1 = datetime(2023, 6, 15, 12, 32, 0)
        key_1 = to_s3_key(test_ts_1, SatellitePattern.GOES_18, product_type="RadF", band=13)
        self.assertIn("s20231661230", key_1)

        # RadC should select 31 for timestamp with minute=32
        test_ts_2 = datetime(2023, 6, 15, 12, 32, 0)
        key_2 = to_s3_key(test_ts_2, SatellitePattern.GOES_18, product_type="RadC", band=13)
        self.assertIn("s20231661231", key_2)

        # RadM should select 32 for timestamp with minute=32 (exact same minute)
        test_ts_3 = datetime(2023, 6, 15, 12, 32, 0)
        key_3 = to_s3_key(test_ts_3, SatellitePattern.GOES_18, product_type="RadM", band=13)
        self.assertIn("s20231661232", key_3)

    def test_real_examples_from_logs(self):
        """Test with real S3 keys from application logs."""
        # Example real S3 keys extracted from logs
        real_keys = [
            # These examples should be replaced with actual keys from your logs
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661211190_e20231661213562_c20231661214024.nc",
            "ABI-L1b-RadF/2024/092/10/OR_ABI-L1b-RadF-M6C01_G18_s20240921000012_e20240921009307_c20240921009377.nc",
            "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
        ]

        # Verify that our filter function can correctly identify bands in these keys
        band13_keys = filter_s3_keys_by_band(real_keys, 13)
        self.assertEqual(len(band13_keys), 2)

        band1_keys = filter_s3_keys_by_band(real_keys, 1)
        self.assertEqual(len(band1_keys), 1)

        # Verify that wrong bands don't match
        band2_keys = filter_s3_keys_by_band(real_keys, 2)
        self.assertEqual(len(band2_keys), 0)


if __name__ == "__main__":
    unittest.main()
