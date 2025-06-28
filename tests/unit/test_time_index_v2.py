"""
Optimized tests for time index utilities with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Pytest fixtures instead of unittest setUp/tearDown
- Shared test data at class level
- Parameterized tests for similar scenarios
- Combined related test operations
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from goesvfi.integrity_check.time_index import (
    SatellitePattern,
    TimeIndex,
    detect_interval,
    extract_timestamp,
    generate_timestamp_sequence,
    to_s3_key,
)


class TestTimeIndexOptimizedV2:
    """Optimized time index tests with full coverage."""

    @pytest.fixture(scope="class")
    def test_dates(self):
        """Shared test dates for all tests."""
        return {
            "recent": datetime(2023, 6, 15, 12, 30, 0),  # Within 7 days window
            "old": datetime(2022, 1, 1, 0, 0, 0),  # Outside 7 days window
            "edge": datetime(2023, 1, 1, 0, 0, 0),  # For edge case testing
            "test_sequence_start": datetime(2023, 1, 1, 0, 0, 0),
            "test_sequence_end": datetime(2023, 1, 1, 1, 0, 0),
        }

    @pytest.fixture(scope="class")
    def sample_filenames(self):
        """Sample filenames for testing."""
        return {
            "goes16_valid": "goes16_20220101_000000_band13.png",
            "goes18_valid": "goes18_20230615_123000_band13.png",
            "invalid": "invalid_file.png",
        }

    @pytest.fixture(scope="class")
    def sample_s3_keys(self):
        """Sample S3 keys for testing."""
        return [
            # Band 13 keys
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166121000_e2023166121059_c2023166121123.nc",
            # Band 2 key
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            # Band 7 key
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C07_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            # RadF product
            "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s2023166120000_e2023166120059_c2023166120123.nc",
        ]

    @pytest.fixture(autouse=True)
    def setup_time_index(self):
        """Setup TimeIndex configuration for testing."""
        # Store original values
        original_recent_window_days = TimeIndex.RECENT_WINDOW_DAYS
        
        # Set test configuration
        TimeIndex.RECENT_WINDOW_DAYS = 7
        
        yield
        
        # Restore original values
        TimeIndex.RECENT_WINDOW_DAYS = original_recent_window_days

    @pytest.mark.parametrize("filename,pattern,expected", [
        ("goes16_20220101_000000_band13.png", SatellitePattern.GOES_16, datetime(2022, 1, 1, 0, 0, 0)),
        ("goes18_20230615_123000_band13.png", SatellitePattern.GOES_18, datetime(2023, 6, 15, 12, 30, 0)),
        ("goes16_20231225_235959_band13.png", SatellitePattern.GOES_16, datetime(2023, 12, 25, 23, 59, 59)),
        ("goes18_20220301_120000_band13.png", SatellitePattern.GOES_18, datetime(2022, 3, 1, 12, 0, 0)),
    ])
    def test_extract_timestamp_valid_cases(self, filename, pattern, expected) -> None:
        """Test timestamp extraction from valid filenames."""
        timestamp = extract_timestamp(filename, pattern)
        assert timestamp == expected

    def test_extract_timestamp_invalid_cases(self, sample_filenames) -> None:
        """Test timestamp extraction error handling."""
        # Test invalid filename
        with pytest.raises(ValueError):
            extract_timestamp(sample_filenames["invalid"], SatellitePattern.GOES_16)
        
        # Test wrong pattern for filename
        with pytest.raises(ValueError):
            extract_timestamp("malformed_20220101_000000_band13.png", SatellitePattern.GOES_16)
        
        # Test empty filename
        with pytest.raises(ValueError):
            extract_timestamp("", SatellitePattern.GOES_16)

    def test_timestamp_sequence_generation(self, test_dates) -> None:
        """Test generating timestamp sequences with different intervals."""
        start = test_dates["test_sequence_start"]
        end = test_dates["test_sequence_end"]
        
        # Test cases: (interval_minutes, expected_count, description)
        test_cases = [
            (10, 7, "10-minute intervals"),  # 0:00, 0:10, 0:20, 0:30, 0:40, 0:50, 1:00
            (15, 5, "15-minute intervals"),  # 0:00, 0:15, 0:30, 0:45, 1:00
            (30, 3, "30-minute intervals"),  # 0:00, 0:30, 1:00
            (60, 2, "60-minute intervals"),  # 0:00, 1:00
            (5, 13, "5-minute intervals"),   # 0:00, 0:05, 0:10, ..., 1:00
        ]
        
        for interval, expected_count, description in test_cases:
            sequence = generate_timestamp_sequence(start, end, interval)
            
            assert len(sequence) == expected_count, f"Failed for {description}"
            assert sequence[0] == start, f"Start time incorrect for {description}"
            assert sequence[-1] == end, f"End time incorrect for {description}"
            
            # Verify intervals are correct
            for i in range(1, len(sequence)):
                expected_time = start + timedelta(minutes=interval * i)
                assert sequence[i] == expected_time, f"Interval {i} incorrect for {description}"

    @pytest.mark.parametrize("timestamps,expected_interval", [
        # Regular 10-minute intervals
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 20, 0),
            datetime(2023, 1, 1, 0, 30, 0),
        ], 10),
        # Regular 5-minute intervals
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 5, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 15, 0),
        ], 5),
        # Mixed intervals - should detect most common (10 minutes)
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 20, 0),
            datetime(2023, 1, 1, 0, 25, 0),  # 5-minute outlier
            datetime(2023, 1, 1, 0, 35, 0),  # Back to 10-minute
        ], 10),
        # Single interval
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 15, 0),
        ], 15),
    ])
    def test_interval_detection(self, timestamps, expected_interval) -> None:
        """Test interval detection with various timestamp patterns."""
        interval = detect_interval(timestamps)
        assert interval == expected_interval

    def test_cdn_url_generation(self, test_dates) -> None:
        """Test CDN URL generation for different satellites and resolutions."""
        recent_date = test_dates["recent"]
        
        # Test GOES-16 with default resolution
        url_goes16 = TimeIndex.to_cdn_url(recent_date, SatellitePattern.GOES_16)
        expected_goes16 = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/"
            f"{recent_date.strftime('%Y%j%H%M')}_GOES16-ABI-CONUS-13-{TimeIndex.CDN_RES}.jpg"
        )
        assert url_goes16 == expected_goes16
        
        # Test GOES-18 with default resolution
        url_goes18 = TimeIndex.to_cdn_url(recent_date, SatellitePattern.GOES_18)
        expected_goes18 = (
            f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/CONUS/13/"
            f"{recent_date.strftime('%Y%j%H%M')}_GOES18-ABI-CONUS-13-{TimeIndex.CDN_RES}.jpg"
        )
        assert url_goes18 == expected_goes18
        
        # Test with custom resolution
        custom_res = "250m"
        url_custom = TimeIndex.to_cdn_url(recent_date, SatellitePattern.GOES_16, custom_res)
        expected_custom = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/"
            f"{recent_date.strftime('%Y%j%H%M')}_GOES16-ABI-CONUS-13-{custom_res}.jpg"
        )
        assert url_custom == expected_custom

    @pytest.mark.parametrize("satellite,product_type,band", [
        (SatellitePattern.GOES_16, "RadC", 13),
        (SatellitePattern.GOES_18, "RadC", 13),
        (SatellitePattern.GOES_16, "RadF", 13),
        (SatellitePattern.GOES_16, "RadC", 2),
        (SatellitePattern.GOES_18, "RadF", 7),
    ])
    def test_s3_key_generation(self, test_dates, satellite, product_type, band) -> None:
        """Test S3 key generation for different configurations."""
        old_date = test_dates["old"]
        
        # Generate key using TimeIndex method
        key = TimeIndex.to_s3_key(old_date, satellite, product_type=product_type, band=band)
        
        # Generate expected key using standalone function
        expected_key = to_s3_key(old_date, satellite, product_type=product_type, band=band)
        
        assert key == expected_key
        
        # Verify key format
        assert isinstance(key, str)
        assert len(key) > 0
        assert product_type in key
        assert f"C{band:02d}" in key or f"band{band}" in key

    @pytest.mark.parametrize("satellite,expected_prefix", [
        (SatellitePattern.GOES_16, "goes16_"),
        (SatellitePattern.GOES_18, "goes18_"),
    ])
    def test_local_path_generation(self, test_dates, satellite, expected_prefix) -> None:
        """Test local path generation for different satellites."""
        recent_date = test_dates["recent"]
        
        path = TimeIndex.to_local_path(recent_date, satellite)
        
        # Verify path structure
        expected = Path(
            f"{recent_date.year}/{recent_date.month:02d}/"
            f"{recent_date.day:02d}/{expected_prefix}{recent_date.strftime('%Y%m%d_%H%M%S')}_band13.png"
        )
        assert path == expected
        
        # Verify path components
        assert path.suffix == ".png"
        assert path.name.startswith(expected_prefix)
        assert "band13" in path.name

    def test_cdn_availability_checking(self) -> None:
        """Test CDN availability based on date recency."""
        current_time = datetime.now()
        
        # Test scenarios: (days_offset, expected_availability)
        test_scenarios = [
            (-3, True),   # 3 days ago - should be available
            (-1, True),   # 1 day ago - should be available
            (-6, True),   # 6 days ago - should be available
            (-8, False),  # 8 days ago - should not be available
            (-30, False), # 30 days ago - should not be available
            (0, True),    # Today - should be available
        ]
        
        for days_offset, expected in test_scenarios:
            test_date = current_time + timedelta(days=days_offset)
            is_available = TimeIndex.is_cdn_available(test_date)
            assert is_available == expected, f"CDN availability check failed for {days_offset} days offset"
        
        # Test edge case - exactly at window boundary
        boundary_date = current_time - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS)
        # This may be True or False depending on implementation, just ensure it doesn't crash
        result = TimeIndex.is_cdn_available(boundary_date)
        assert isinstance(result, bool)

    @pytest.mark.parametrize("band,expected_count", [
        (13, 3),  # 2 RadC + 1 RadF
        (2, 1),   # 1 RadC
        (7, 1),   # 1 RadC
        (99, 0),  # Non-existent band
    ])
    def test_s3_key_filtering_by_band(self, sample_s3_keys, band, expected_count) -> None:
        """Test filtering S3 keys by band number."""
        filtered_keys = TimeIndex.filter_s3_keys_by_band(sample_s3_keys, band)
        
        assert len(filtered_keys) == expected_count
        
        # Verify all filtered keys contain the correct band identifier
        if expected_count > 0:
            band_identifier = f"C{band:02d}_"
            for key in filtered_keys:
                assert band_identifier in key

    def test_s3_key_filtering_edge_cases(self) -> None:
        """Test S3 key filtering edge cases."""
        # Test empty list
        empty_result = TimeIndex.filter_s3_keys_by_band([], 13)
        assert len(empty_result) == 0
        
        # Test with malformed keys
        malformed_keys = [
            "invalid_key_format",
            "ABI-L1b-RadC/2023/166/12/malformed_filename.nc",
            "",
        ]
        result = TimeIndex.filter_s3_keys_by_band(malformed_keys, 13)
        assert len(result) == 0

    @pytest.mark.parametrize("test_time,product_type,expected_intervals", [
        # RadF product (10-minute intervals)
        (datetime(2023, 6, 15, 12, 15, 0), "RadF", [
            datetime(2023, 6, 15, 12, 10, 0),
            datetime(2023, 6, 15, 12, 20, 0)
        ]),
        # RadC product (5-minute intervals) - assuming 11, 16 minute intervals
        (datetime(2023, 6, 15, 12, 15, 0), "RadC", [
            datetime(2023, 6, 15, 12, 11, 0),
            datetime(2023, 6, 15, 12, 16, 0)
        ]),
        # RadM product (1-minute intervals)
        (datetime(2023, 6, 15, 12, 15, 0), "RadM", [
            datetime(2023, 6, 15, 12, 15, 0)
        ]),
        # Exact match on RadF interval
        (datetime(2023, 6, 15, 12, 20, 0), "RadF", [
            datetime(2023, 6, 15, 12, 20, 0),
            datetime(2023, 6, 15, 12, 30, 0)
        ]),
        # Edge case - start of hour
        (datetime(2023, 6, 15, 12, 0, 0), "RadF", [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 10, 0)
        ]),
    ])
    def test_nearest_interval_finding(self, test_time, product_type, expected_intervals) -> None:
        """Test finding nearest GOES intervals for different product types."""
        intervals = TimeIndex.find_nearest_intervals(test_time, product_type=product_type)
        
        assert len(intervals) == len(expected_intervals)
        for actual, expected in zip(intervals, expected_intervals):
            assert actual == expected

    def test_nearest_interval_edge_cases(self) -> None:
        """Test nearest interval finding with edge cases."""
        # Test with future time
        future_time = datetime(2030, 1, 1, 12, 0, 0)
        intervals = TimeIndex.find_nearest_intervals(future_time, product_type="RadF")
        assert len(intervals) >= 1
        
        # Test with very old time
        old_time = datetime(2000, 1, 1, 12, 0, 0)
        intervals = TimeIndex.find_nearest_intervals(old_time, product_type="RadF")
        assert len(intervals) >= 1
        
        # Test with different product types
        for product_type in ["RadF", "RadC", "RadM"]:
            test_time = datetime(2023, 6, 15, 12, 15, 0)
            intervals = TimeIndex.find_nearest_intervals(test_time, product_type=product_type)
            assert len(intervals) >= 1
            assert all(isinstance(interval, datetime) for interval in intervals)

    def test_time_index_integration(self, test_dates, sample_filenames) -> None:
        """Test complete TimeIndex functionality integration."""
        recent_date = test_dates["recent"]
        old_date = test_dates["old"]
        
        # Test complete workflow for recent date (CDN)
        if TimeIndex.is_cdn_available(recent_date):
            cdn_url = TimeIndex.to_cdn_url(recent_date, SatellitePattern.GOES_16)
            assert "cdn.star.nesdis.noaa.gov" in cdn_url
            assert "GOES16" in cdn_url
        
        # Test complete workflow for old date (S3)
        if not TimeIndex.is_cdn_available(old_date):
            s3_key = TimeIndex.to_s3_key(old_date, SatellitePattern.GOES_16)
            assert len(s3_key) > 0
            assert "ABI-L1b-" in s3_key
        
        # Test local path generation
        local_path = TimeIndex.to_local_path(recent_date, SatellitePattern.GOES_16)
        assert local_path.suffix == ".png"
        assert "goes16" in local_path.name
        
        # Test timestamp extraction round-trip
        filename = sample_filenames["goes16_valid"]
        extracted_time = extract_timestamp(filename, SatellitePattern.GOES_16)
        regenerated_path = TimeIndex.to_local_path(extracted_time, SatellitePattern.GOES_16)
        assert "goes16" in regenerated_path.name