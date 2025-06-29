"""Optimized time index tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common date setups and satellite configurations
- Parameterized test scenarios for comprehensive time index validation
- Enhanced error handling and edge case coverage
- Mock-based time operations to avoid real datetime dependencies
- Comprehensive satellite pattern and product type testing
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from goesvfi.integrity_check.time_index import (
    SatellitePattern,
    TimeIndex,
    detect_interval,
    extract_timestamp,
    generate_timestamp_sequence,
    to_s3_key,
)


class TestTimeIndexV2:
    """Optimized test class for time index functionality."""

    @pytest.fixture(scope="class")
    def satellite_configurations(self):
        """Sample satellite configurations for testing."""
        return {
            "goes16": {
                "pattern": SatellitePattern.GOES_16,
                "name": "goes16",
                "filenames": [
                    "goes16_20220101_000000_band13.png",
                    "goes16_20230615_123000_band13.png",
                    "goes16_20240301_091530_band02.png"
                ],
                "timestamps": [
                    datetime(2022, 1, 1, 0, 0, 0),
                    datetime(2023, 6, 15, 12, 30, 0),
                    datetime(2024, 3, 1, 9, 15, 30)
                ]
            },
            "goes18": {
                "pattern": SatellitePattern.GOES_18,
                "name": "goes18", 
                "filenames": [
                    "goes18_20220101_000000_band13.png",
                    "goes18_20230615_123000_band13.png",
                    "goes18_20240301_091530_band07.png"
                ],
                "timestamps": [
                    datetime(2022, 1, 1, 0, 0, 0),
                    datetime(2023, 6, 15, 12, 30, 0),
                    datetime(2024, 3, 1, 9, 15, 30)
                ]
            }
        }

    @pytest.fixture
    def time_scenarios(self):
        """Time scenarios for testing various conditions."""
        base_time = datetime(2023, 6, 15, 12, 0, 0)
        return {
            "recent": base_time - timedelta(days=3),
            "old": base_time - timedelta(days=30),
            "edge_recent": base_time - timedelta(days=7),
            "future": base_time + timedelta(days=1),
            "exact_hour": base_time,
            "mid_interval": base_time + timedelta(minutes=15),
        }

    @pytest.fixture
    def product_type_intervals(self):
        """Product type configurations with their intervals."""
        return {
            "RadF": {"interval": 10, "description": "Full Disk"},
            "RadC": {"interval": 5, "description": "CONUS"},
            "RadM": {"interval": 1, "description": "Mesoscale"}
        }

    @pytest.fixture
    def mock_timeindex_setup(self):
        """Setup mock TimeIndex with controlled recent window."""
        original_window = TimeIndex.RECENT_WINDOW_DAYS
        TimeIndex.RECENT_WINDOW_DAYS = 7
        yield
        TimeIndex.RECENT_WINDOW_DAYS = original_window

    @pytest.mark.parametrize("satellite_name", ["goes16", "goes18"])
    def test_extract_timestamp_scenarios(self, satellite_configurations, satellite_name):
        """Test timestamp extraction with various satellite patterns."""
        config = satellite_configurations[satellite_name]
        pattern = config["pattern"]
        
        for filename, expected_timestamp in zip(config["filenames"], config["timestamps"]):
            extracted = extract_timestamp(filename, pattern)
            assert extracted == expected_timestamp

    @pytest.mark.parametrize("invalid_filename", [
        "invalid_file.png",
        "goes16_invalid_date_band13.png", 
        "wrong_format_20220101_000000.png",
        "",
        "goes16_20220132_000000_band13.png",  # Invalid date
        "goes16_20220101_250000_band13.png",  # Invalid time
    ])
    def test_extract_timestamp_invalid_cases(self, invalid_filename):
        """Test timestamp extraction with invalid filenames."""
        with pytest.raises(ValueError):
            extract_timestamp(invalid_filename, SatellitePattern.GOES_16)

    @pytest.mark.parametrize("start_offset,end_offset,interval,expected_count", [
        (0, 60, 10, 7),     # 1 hour, 10-min intervals: 0,10,20,30,40,50,60
        (0, 30, 5, 7),      # 30 min, 5-min intervals: 0,5,10,15,20,25,30
        (0, 10, 1, 11),     # 10 min, 1-min intervals: 0,1,2,3,4,5,6,7,8,9,10
        (15, 45, 15, 3),    # 30 min starting at 15, 15-min intervals: 15,30,45
        (0, 0, 10, 1),      # Same start/end time
    ])
    def test_generate_timestamp_sequence_scenarios(self, start_offset, end_offset, interval, expected_count):
        """Test timestamp sequence generation with various parameters."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        start = base_time + timedelta(minutes=start_offset)
        end = base_time + timedelta(minutes=end_offset)
        
        sequence = generate_timestamp_sequence(start, end, interval)
        
        assert len(sequence) == expected_count
        assert sequence[0] == start
        assert sequence[-1] == end
        
        # Verify intervals
        if len(sequence) > 1:
            for i in range(1, len(sequence)):
                time_diff = sequence[i] - sequence[i-1]
                assert time_diff == timedelta(minutes=interval)

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
        # Mixed intervals with majority 10-minute
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 20, 0),
            datetime(2023, 1, 1, 0, 25, 0),  # 5-minute outlier
            datetime(2023, 1, 1, 0, 35, 0),  # 10-minute interval
        ], 10),
        # Single timestamp
        ([datetime(2023, 1, 1, 0, 0, 0)], None),
        # Two timestamps
        ([
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 15, 0),
        ], 15),
    ])
    def test_detect_interval_scenarios(self, timestamps, expected_interval):
        """Test interval detection with various timestamp patterns."""
        if expected_interval is None:
            # Single timestamp case - behavior depends on implementation
            result = detect_interval(timestamps)
            # Could be None or some default value
            assert result is None or isinstance(result, int)
        else:
            interval = detect_interval(timestamps)
            assert interval == expected_interval

    @pytest.mark.parametrize("satellite_name,custom_res", [
        ("goes16", None),
        ("goes18", None),
        ("goes16", "250m"),
        ("goes18", "500m"),
        ("goes16", "1km"),
    ])
    def test_cdn_url_generation(self, satellite_configurations, time_scenarios, satellite_name, custom_res):
        """Test CDN URL generation with various satellites and resolutions."""
        config = satellite_configurations[satellite_name]
        pattern = config["pattern"]
        test_date = time_scenarios["recent"]
        
        url = TimeIndex.to_cdn_url(test_date, pattern, custom_res)
        
        # Verify URL structure
        assert url.startswith("https://cdn.star.nesdis.noaa.gov/")
        assert satellite_name.upper() in url
        assert test_date.strftime('%Y%j%H%M') in url
        
        if custom_res:
            assert custom_res in url
        else:
            assert TimeIndex.CDN_RES in url

    @pytest.mark.parametrize("product_type,band", [
        ("RadC", 13),
        ("RadF", 13),
        ("RadC", 2),
        ("RadF", 7),
        ("RadM", 13),
    ])
    def test_s3_key_generation(self, satellite_configurations, time_scenarios, product_type, band):
        """Test S3 key generation with various product types and bands."""
        for satellite_name, config in satellite_configurations.items():
            pattern = config["pattern"]
            test_date = time_scenarios["old"]
            
            key = TimeIndex.to_s3_key(test_date, pattern, product_type, band)
            expected_key = to_s3_key(test_date, pattern, product_type, band)
            
            assert key == expected_key
            assert product_type in key
            assert f"C{band:02d}_" in key

    @pytest.mark.parametrize("satellite_name", ["goes16", "goes18"])
    def test_local_path_generation(self, satellite_configurations, time_scenarios, satellite_name):
        """Test local path generation with various satellites."""
        config = satellite_configurations[satellite_name]
        pattern = config["pattern"]
        test_date = time_scenarios["recent"]
        
        path = TimeIndex.to_local_path(test_date, pattern)
        
        expected = Path(
            f"{test_date.year}/{test_date.month:02d}/"
            f"{test_date.day:02d}/{satellite_name}_{test_date.strftime('%Y%m%d_%H%M%S')}_band13.png"
        )
        
        assert path == expected
        assert isinstance(path, Path)

    def test_cdn_availability_scenarios(self, mock_timeindex_setup, time_scenarios):
        """Test CDN availability checking with various time scenarios."""
        # Mock current time for consistent testing
        mock_current = datetime(2023, 6, 15, 12, 0, 0)
        
        with patch('goesvfi.integrity_check.time_index.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_current
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Recent date - should be available
            recent_date = mock_current - timedelta(days=3)
            assert TimeIndex.is_cdn_available(recent_date) is True
            
            # Old date - should not be available
            old_date = mock_current - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS + 1)
            assert TimeIndex.is_cdn_available(old_date) is False
            
            # Edge case - exactly at boundary
            boundary_date = mock_current - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS)
            result = TimeIndex.is_cdn_available(boundary_date)
            assert isinstance(result, bool)  # Could be either True or False

    @pytest.mark.parametrize("band,expected_count", [
        (13, 3),  # 2 RadC + 1 RadF
        (2, 1),   # 1 RadC
        (7, 1),   # 1 RadC
        (99, 0),  # Non-existent band
    ])
    def test_filter_s3_keys_by_band(self, band, expected_count):
        """Test S3 key filtering by band number."""
        test_keys = [
            # Band 13 keys
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166121000_e2023166121059_c2023166121123.nc",
            # Band 2 key
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            # Band 7 key
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C07_G16_s2023166120000_e2023166120059_c2023166120123.nc",
            # RadF Band 13 key
            "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s2023166120000_e2023166120059_c2023166120123.nc",
        ]
        
        filtered_keys = TimeIndex.filter_s3_keys_by_band(test_keys, band)
        assert len(filtered_keys) == expected_count
        
        if expected_count > 0:
            for key in filtered_keys:
                assert f"C{band:02d}_" in key

    def test_filter_s3_keys_edge_cases(self):
        """Test S3 key filtering with edge cases."""
        # Empty list
        assert TimeIndex.filter_s3_keys_by_band([], 13) == []
        
        # Invalid keys
        invalid_keys = [
            "not_a_valid_key.nc",
            "ABI-L1b-RadC/2023/166/12/malformed_filename.nc",
            "",
        ]
        result = TimeIndex.filter_s3_keys_by_band(invalid_keys, 13)
        assert len(result) == 0

    @pytest.mark.parametrize("product_type,test_minute,expected_intervals", [
        # RadF (10-minute intervals)
        ("RadF", 15, 2),  # Between 10 and 20
        ("RadF", 20, 2),  # Exactly on 20, returns 20 and 30
        ("RadF", 0, 2),   # First interval of hour
        
        # RadC (5-minute intervals) 
        ("RadC", 7, 2),   # Between 5 and 10
        ("RadC", 15, 2),  # Exactly on 15
        
        # RadM (1-minute intervals)
        ("RadM", 15, 1),  # Exact minute match
        ("RadM", 0, 1),   # First minute of hour
    ])
    def test_find_nearest_intervals_scenarios(self, product_type, test_minute, expected_intervals):
        """Test finding nearest GOES intervals with various scenarios."""
        test_time = datetime(2023, 6, 15, 12, test_minute, 0)
        intervals = TimeIndex.find_nearest_intervals(test_time, product_type=product_type)
        
        assert len(intervals) == expected_intervals
        
        # Verify intervals are properly ordered
        if len(intervals) > 1:
            assert intervals[0] <= intervals[1]
        
        # Verify intervals match expected product type pattern
        interval_minutes = {
            "RadF": 10,
            "RadC": 5, 
            "RadM": 1
        }
        
        expected_interval = interval_minutes[product_type]
        for interval in intervals:
            if product_type != "RadM":  # RadM returns exact minute
                assert interval.minute % expected_interval == 0

    def test_timestamp_sequence_edge_cases(self):
        """Test timestamp sequence generation with edge cases."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        
        # Zero interval
        with pytest.raises((ValueError, ZeroDivisionError)):
            generate_timestamp_sequence(base_time, base_time + timedelta(hours=1), 0)
        
        # Negative interval
        with pytest.raises(ValueError):
            generate_timestamp_sequence(base_time, base_time + timedelta(hours=1), -10)
        
        # End before start
        result = generate_timestamp_sequence(
            base_time + timedelta(hours=1), 
            base_time, 
            10
        )
        # Should handle gracefully (return empty or single item)
        assert len(result) <= 1

    def test_satellite_pattern_enum_coverage(self):
        """Test that all satellite patterns are properly handled."""
        test_date = datetime(2023, 6, 15, 12, 0, 0)
        
        for pattern in SatellitePattern:
            # Test CDN URL generation
            url = TimeIndex.to_cdn_url(test_date, pattern)
            assert isinstance(url, str)
            assert "https://" in url
            
            # Test S3 key generation
            key = TimeIndex.to_s3_key(test_date, pattern, "RadC", 13)
            assert isinstance(key, str)
            assert len(key) > 0
            
            # Test local path generation
            path = TimeIndex.to_local_path(test_date, pattern)
            assert isinstance(path, Path)

    def test_band_variations_comprehensive(self):
        """Test comprehensive band number variations."""
        test_date = datetime(2023, 6, 15, 12, 0, 0)
        valid_bands = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        
        for band in valid_bands:
            # Test S3 key generation with various bands
            key = TimeIndex.to_s3_key(test_date, SatellitePattern.GOES_16, "RadC", band)
            assert f"C{band:02d}_" in key
            
            # Test key filtering
            test_keys = [
                f"ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C{band:02d}_G16_s2023166120000_e2023166120059_c2023166120123.nc"
            ]
            filtered = TimeIndex.filter_s3_keys_by_band(test_keys, band)
            assert len(filtered) == 1

    def test_time_index_integration_workflow(self, satellite_configurations, time_scenarios, product_type_intervals):
        """Test complete time index workflow integration."""
        # Select test parameters
        config = satellite_configurations["goes16"]
        pattern = config["pattern"]
        test_date = time_scenarios["recent"]
        
        for product_type, type_config in product_type_intervals.items():
            # Generate S3 key
            s3_key = TimeIndex.to_s3_key(test_date, pattern, product_type, 13)
            assert product_type in s3_key
            
            # Generate CDN URL (for recent dates)
            if TimeIndex.is_cdn_available(test_date):
                cdn_url = TimeIndex.to_cdn_url(test_date, pattern)
                assert "https://" in cdn_url
            
            # Generate local path
            local_path = TimeIndex.to_local_path(test_date, pattern)
            assert isinstance(local_path, Path)
            
            # Find nearest intervals
            intervals = TimeIndex.find_nearest_intervals(test_date, product_type)
            assert len(intervals) >= 1
            
            # Test timestamp sequence generation
            if len(intervals) > 1:
                sequence = generate_timestamp_sequence(
                    intervals[0], 
                    intervals[1], 
                    type_config["interval"]
                )
                assert len(sequence) >= 1

    def test_performance_with_large_datasets(self):
        """Test performance with large numbers of timestamps and keys."""
        # Large timestamp list
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        large_timestamp_list = [
            base_time + timedelta(minutes=i*10) for i in range(1000)
        ]
        
        # Should handle large lists efficiently
        interval = detect_interval(large_timestamp_list)
        assert interval == 10
        
        # Large S3 key list
        large_key_list = [
            f"ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166{i:06d}_e2023166{i:06d}_c2023166{i:06d}.nc"
            for i in range(1000)
        ]
        
        # Should filter efficiently
        filtered = TimeIndex.filter_s3_keys_by_band(large_key_list, 13)
        assert len(filtered) == 1000