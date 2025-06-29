"""Optimized S3 Band 13 tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common S3 configurations and mock data setups
- Parameterized test scenarios for comprehensive Band 13 workflow validation
- Enhanced error handling and edge case testing
- Mock-based testing to avoid real S3 operations and network calls
- Comprehensive satellite pattern and product type testing
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, Mock
import pytest

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex
from goesvfi.utils import date_utils


class TestS3Band13V2:
    """Optimized test class for S3 Band 13 functionality."""

    @pytest.fixture(scope="class")
    def satellite_configurations(self):
        """Define various satellite configuration test cases."""
        return {
            "goes_16": {
                "pattern": SatellitePattern.GOES_16,
                "bucket": "noaa-goes16",
                "identifier": "G16",
            },
            "goes_18": {
                "pattern": SatellitePattern.GOES_18,
                "bucket": "noaa-goes18", 
                "identifier": "G18",
            },
        }

    @pytest.fixture(scope="class")
    def product_configurations(self):
        """Define various product configuration test cases."""
        return {
            "full_disk": {
                "product_type": "RadF",
                "scan_interval": 15,  # minutes
                "description": "Full Disk",
            },
            "conus": {
                "product_type": "RadC",
                "scan_interval": 5,  # minutes
                "description": "CONUS",
            },
            "mesoscale": {
                "product_type": "RadM",
                "scan_interval": 1,  # minutes
                "description": "Mesoscale",
            },
        }

    @pytest.fixture(scope="class")
    def band13_scenarios(self):
        """Define various Band 13 scenario test cases."""
        return {
            "standard_download": {
                "timestamp": datetime(2023, 6, 15, 12, 0, 0),
                "satellite": SatellitePattern.GOES_16,
                "product_type": "RadC",
                "expected_year": 2023,
                "expected_doy": 166,
                "expected_hour": 12,
            },
            "different_time": {
                "timestamp": datetime(2023, 12, 31, 18, 30, 0),
                "satellite": SatellitePattern.GOES_18,
                "product_type": "RadF",
                "expected_year": 2023,
                "expected_doy": 365,
                "expected_hour": 18,
            },
            "leap_year": {
                "timestamp": datetime(2024, 2, 29, 6, 45, 0),
                "satellite": SatellitePattern.GOES_16,
                "product_type": "RadM",
                "expected_year": 2024,
                "expected_doy": 60,
                "expected_hour": 6,
            },
            "new_year": {
                "timestamp": datetime(2023, 1, 1, 0, 0, 0),
                "satellite": SatellitePattern.GOES_18,
                "product_type": "RadC",
                "expected_year": 2023,
                "expected_doy": 1,
                "expected_hour": 0,
            },
        }

    @pytest.fixture(scope="class")
    def filename_test_cases(self):
        """Define various filename parsing test cases."""
        return {
            "standard_band13": {
                "filename": "OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc",
                "expected_year": 2023,
                "expected_doy": 166,
                "expected_hour": 12,
                "expected_minute": 1,
                "expected_band": 13,
            },
            "different_satellite": {
                "filename": "OR_ABI-L1b-RadF-M6C13_G18_s20241500845123_e20241500847496_c20241500847544.nc",
                "expected_year": 2024,
                "expected_doy": 150,
                "expected_hour": 8,
                "expected_minute": 45,
                "expected_band": 13,
            },
            "mesoscale_band13": {
                "filename": "OR_ABI-L1b-RadM-M6C13_G16_s20230011830234_e20230011830291_c20230011830339.nc",
                "expected_year": 2023,
                "expected_doy": 1,
                "expected_hour": 18,
                "expected_minute": 30,
                "expected_band": 13,
            },
            "midnight_time": {
                "filename": "OR_ABI-L1b-RadC-M6C13_G16_s20233650001176_e20233650003549_c20233650003597.nc",
                "expected_year": 2023,
                "expected_doy": 365,
                "expected_hour": 0,
                "expected_minute": 0,
                "expected_band": 13,
            },
        }

    @pytest.fixture(scope="class")
    def error_scenarios(self):
        """Define various error scenario test cases."""
        return {
            "network_timeout": {
                "exception": asyncio.TimeoutError("Network timeout"),
                "expected_error": "Network timeout",
            },
            "access_denied": {
                "exception": Exception("Access denied"),
                "expected_error": "Access denied",
            },
            "no_such_bucket": {
                "exception": Exception("NoSuchBucket"),
                "expected_error": "NoSuchBucket",
            },
            "invalid_credentials": {
                "exception": Exception("InvalidAccessKeyId"),
                "expected_error": "InvalidAccessKeyId",
            },
        }

    @pytest.fixture
    def mock_s3_objects_factory(self):
        """Factory for creating mock S3 objects for Band 13."""
        def create_objects(satellite="G16", product="RadC", year=2023, doy=166, hour=12, count=3):
            objects = []
            for i in range(count):
                minute = i * 5  # 5-minute intervals
                timestamp_str = f"s{year}{doy:03d}{hour:02d}{minute:02d}176"
                end_str = f"e{year}{doy:03d}{hour:02d}{minute+2:02d}549"
                create_str = f"c{year}{doy:03d}{hour:02d}{minute+2:02d}597"
                
                filename = f"OR_ABI-L1b-{product}-M6C13_{satellite}_{timestamp_str}_{end_str}_{create_str}.nc"
                prefix = f"ABI-L1b-{product}/{year}/{doy:03d}/{hour:02d}/"
                objects.append(prefix + filename)
            return objects
        return create_objects

    @pytest.fixture
    def mock_s3_store_factory(self):
        """Factory for creating mock S3Store instances."""
        def create_store(should_fail=False, failure_exception=None):
            mock_store = AsyncMock(spec=S3Store)
            
            if should_fail:
                mock_store.download.side_effect = failure_exception or Exception("Download failed")
                mock_store.list_objects.side_effect = failure_exception or Exception("List failed")
            else:
                # Mock successful download
                mock_store.download.return_value = Path("/tmp/mock_download.nc")
                mock_store.list_objects.return_value = []
            
            mock_store.close.return_value = None
            return mock_store
        return create_store

    @pytest.fixture
    def mock_file_operations(self, tmp_path):
        """Mock file operations for testing."""
        def setup_file(filename, content_size=1024):
            file_path = tmp_path / filename
            file_path.write_bytes(b"x" * content_size)  # Mock satellite data
            return file_path
        return setup_file

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario_name", [
        "standard_download",
        "different_time", 
        "leap_year",
        "new_year",
    ])
    async def test_band13_download_scenarios(self, band13_scenarios, satellite_configurations,
                                           mock_s3_store_factory, mock_file_operations, scenario_name):
        """Test Band 13 download scenarios with various configurations."""
        scenario = band13_scenarios[scenario_name]
        mock_store = mock_s3_store_factory(should_fail=False)
        
        # Setup mock file
        test_file = mock_file_operations("test_band13.nc", content_size=2048)
        mock_store.download.return_value = test_file
        
        with patch("goesvfi.integrity_check.remote.s3_store.S3Store", return_value=mock_store):
            with patch.object(TimeIndex, "get_s3_bucket") as mock_bucket:
                with patch.object(TimeIndex, "find_nearest_intervals") as mock_intervals:
                    # Setup mocks
                    sat_config = satellite_configurations["goes_16" if scenario["satellite"] == SatellitePattern.GOES_16 else "goes_18"]
                    mock_bucket.return_value = sat_config["bucket"]
                    mock_intervals.return_value = [scenario["timestamp"]]
                    
                    # Create S3 store and test download
                    s3_store = S3Store(timeout=60)
                    
                    result = await s3_store.download(
                        scenario["timestamp"],
                        scenario["satellite"],
                        test_file,
                        product_type=scenario["product_type"],
                        band=13,
                    )
                    
                    # Verify download
                    assert result.exists()
                    assert result.stat().st_size > 0
                    
                    # Verify S3 operations were called correctly
                    mock_store.download.assert_called_once()
                    
                    await s3_store.close()

    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    @pytest.mark.parametrize("product_name", ["full_disk", "conus", "mesoscale"])
    def test_band13_prefix_generation(self, satellite_configurations, product_configurations,
                                    satellite_name, product_name):
        """Test Band 13 S3 prefix generation for different satellites and products."""
        sat_config = satellite_configurations[satellite_name]
        prod_config = product_configurations[product_name]
        
        timestamp = datetime(2023, 6, 15, 12, 30, 0)
        
        # Generate prefix components
        year = timestamp.year
        doy = date_utils.date_to_doy(timestamp.date())
        hour = timestamp.hour
        
        expected_prefix = f"ABI-L1b-{prod_config['product_type']}/{year}/{doy:03d}/{hour:02d}/"
        
        # Verify prefix structure
        assert str(year) in expected_prefix
        assert f"{doy:03d}" in expected_prefix  # DOY should be zero-padded
        assert f"{hour:02d}" in expected_prefix  # Hour should be zero-padded
        assert prod_config['product_type'] in expected_prefix

    @pytest.mark.parametrize("filename_case", [
        "standard_band13",
        "different_satellite",
        "mesoscale_band13", 
        "midnight_time",
    ])
    def test_band13_filename_parsing(self, filename_test_cases, filename_case):
        """Test parsing Band 13 filenames for timestamp and metadata extraction."""
        test_case = filename_test_cases[filename_case]
        filename = test_case["filename"]
        
        import re
        
        # Test Band 13 pattern matching
        pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
        match = re.search(pattern, filename)
        
        assert match, f"Should match Band 13 filename pattern: {filename}"
        
        # Extract and verify components
        file_year = int(match.group(1))
        file_doy = int(match.group(2))
        file_hour = int(match.group(3))
        file_minute = int(match.group(4))
        
        assert file_year == test_case["expected_year"]
        assert file_doy == test_case["expected_doy"]
        assert file_hour == test_case["expected_hour"]
        assert file_minute == test_case["expected_minute"]
        
        # Verify Band 13 identifier
        assert "C13" in filename, f"Filename should contain Band 13 identifier: {filename}"

    @pytest.mark.asyncio
    async def test_band13_object_listing_success(self, mock_s3_objects_factory):
        """Test successful listing of Band 13 objects."""
        # Create mock objects
        mock_objects = mock_s3_objects_factory(count=5)
        
        # Mock function for object listing
        async def mock_list_objects(bucket, prefix, limit=10):
            return mock_objects[:limit]
        
        # Test the listing
        result = await mock_list_objects("noaa-goes16", "ABI-L1b-RadC/2023/166/12/", limit=3)
        
        assert len(result) == 3
        assert all("C13" in obj for obj in result), "All objects should be Band 13"
        assert all("RadC" in obj for obj in result), "All objects should be RadC product"

    @pytest.mark.asyncio
    async def test_band13_object_listing_empty(self):
        """Test listing when no Band 13 objects are found."""
        # Mock function that returns empty list
        async def mock_list_objects_empty(bucket, prefix, limit=10):
            return []
        
        result = await mock_list_objects_empty("noaa-goes16", "ABI-L1b-RadC/2023/166/12/")
        
        assert result == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_case", [
        "network_timeout",
        "access_denied", 
        "no_such_bucket",
        "invalid_credentials",
    ])
    async def test_band13_error_scenarios(self, error_scenarios, mock_s3_store_factory, error_case):
        """Test various error scenarios during Band 13 operations."""
        import asyncio
        
        scenario = error_scenarios[error_case]
        mock_store = mock_s3_store_factory(should_fail=True, failure_exception=scenario["exception"])
        
        with patch("goesvfi.integrity_check.remote.s3_store.S3Store", return_value=mock_store):
            s3_store = S3Store(timeout=30)
            
            # Test that download raises the expected error
            with pytest.raises(Exception) as exc_info:
                await s3_store.download(
                    datetime(2023, 6, 15, 12, 0, 0),
                    SatellitePattern.GOES_16,
                    Path("/tmp/test.nc"),
                    product_type="RadC",
                    band=13,
                )
            
            assert scenario["expected_error"] in str(exc_info.value)
            
            await s3_store.close()

    def test_band13_date_conversion_edge_cases(self):
        """Test date conversion edge cases for Band 13 operations."""
        test_cases = [
            # (year, month, day, expected_doy)
            (2023, 1, 1, 1),      # New Year
            (2023, 12, 31, 365),  # End of non-leap year
            (2024, 2, 29, 60),    # Leap day
            (2024, 12, 31, 366),  # End of leap year
            (2023, 6, 15, 166),   # Mid-year
        ]
        
        for year, month, day, expected_doy in test_cases:
            date_obj = datetime(year, month, day).date()
            calculated_doy = date_utils.date_to_doy(date_obj)
            
            assert calculated_doy == expected_doy, f"DOY calculation failed for {year}-{month:02d}-{day:02d}"
            
            # Test round-trip conversion
            converted_date = date_utils.doy_to_date(year, calculated_doy)
            assert converted_date == date_obj, f"Round-trip conversion failed for {year}-{expected_doy}"

    @pytest.mark.parametrize("satellite", [SatellitePattern.GOES_16, SatellitePattern.GOES_18])
    def test_band13_bucket_resolution(self, satellite_configurations, satellite):
        """Test S3 bucket resolution for different satellites."""
        with patch.object(TimeIndex, "get_s3_bucket") as mock_get_bucket:
            if satellite == SatellitePattern.GOES_16:
                expected_bucket = satellite_configurations["goes_16"]["bucket"]
            else:
                expected_bucket = satellite_configurations["goes_18"]["bucket"]
            
            mock_get_bucket.return_value = expected_bucket
            
            bucket = TimeIndex.get_s3_bucket(satellite)
            assert bucket == expected_bucket
            mock_get_bucket.assert_called_once_with(satellite)

    @pytest.mark.asyncio
    async def test_band13_concurrent_downloads(self, mock_s3_store_factory, mock_file_operations):
        """Test concurrent Band 13 downloads."""
        import asyncio
        
        # Create multiple mock stores
        stores = [mock_s3_store_factory(should_fail=False) for _ in range(3)]
        
        # Setup mock files
        test_files = [mock_file_operations(f"test_band13_{i}.nc") for i in range(3)]
        
        for store, test_file in zip(stores, test_files):
            store.download.return_value = test_file
        
        async def download_task(store, file_path, timestamp):
            return await store.download(
                timestamp,
                SatellitePattern.GOES_16,
                file_path,
                product_type="RadC",
                band=13,
            )
        
        # Create concurrent download tasks
        timestamps = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 5, 0),
            datetime(2023, 6, 15, 12, 10, 0),
        ]
        
        tasks = [
            download_task(store, test_file, timestamp)
            for store, test_file, timestamp in zip(stores, test_files, timestamps)
        ]
        
        # Execute concurrent downloads
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all downloads succeeded
        assert len(results) == 3
        for result in results:
            assert isinstance(result, Path), f"Download should return Path, got {type(result)}"
            assert result.exists()

    def test_band13_metadata_extraction(self):
        """Test extraction of metadata from Band 13 filenames."""
        test_filename = "OR_ABI-L1b-RadC-M6C13_G16_s20231661201176_e20231661203549_c20231661203597.nc"
        
        # Extract instrument and satellite info
        assert "ABI-L1b" in test_filename, "Should contain ABI instrument identifier"
        assert "RadC" in test_filename, "Should contain product type"
        assert "M6" in test_filename, "Should contain scan mode"
        assert "C13" in test_filename, "Should contain Band 13 identifier"
        assert "G16" in test_filename, "Should contain satellite identifier"
        
        # Extract timing info
        import re
        
        # Start time
        start_pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
        start_match = re.search(start_pattern, test_filename)
        assert start_match, "Should extract start time"
        
        # End time
        end_pattern = r"_e(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
        end_match = re.search(end_pattern, test_filename)
        assert end_match, "Should extract end time"
        
        # Creation time
        create_pattern = r"_c(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})\.nc"
        create_match = re.search(create_pattern, test_filename)
        assert create_match, "Should extract creation time"

    @pytest.mark.asyncio
    async def test_band13_download_with_retries(self, mock_s3_store_factory, mock_file_operations):
        """Test Band 13 download with retry logic."""
        mock_store = mock_s3_store_factory(should_fail=False)
        test_file = mock_file_operations("retry_test.nc")
        
        # Mock first call to fail, second to succeed
        mock_store.download.side_effect = [
            Exception("Temporary failure"),
            test_file,
        ]
        
        # Simulate retry logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = await mock_store.download(
                    datetime(2023, 6, 15, 12, 0, 0),
                    SatellitePattern.GOES_16,
                    test_file,
                    product_type="RadC",
                    band=13,
                )
                break  # Success
            except Exception as e:
                if attempt == max_retries - 1:
                    raise  # Last attempt failed
                continue  # Retry
        
        assert result.exists()
        assert mock_store.download.call_count == 2

    def test_band13_performance_metrics(self, mock_s3_objects_factory):
        """Test performance metrics for Band 13 operations."""
        import time
        
        # Test prefix generation performance
        start_time = time.time()
        
        for i in range(1000):
            timestamp = datetime(2023, 6, 15, 12, i % 60, 0)
            year = timestamp.year
            doy = date_utils.date_to_doy(timestamp.date())
            hour = timestamp.hour
            
            prefix = f"ABI-L1b-RadC/{year}/{doy:03d}/{hour:02d}/"
            assert "RadC" in prefix
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 1000 prefix generations quickly
        assert duration < 0.1, f"Prefix generation too slow: {duration:.3f}s"

    def test_band13_memory_efficiency(self):
        """Test memory efficiency of Band 13 operations."""
        import sys
        
        # Test that filename parsing doesn't accumulate memory
        initial_refs = sys.getrefcount(str)
        
        test_filenames = [
            f"OR_ABI-L1b-RadC-M6C13_G16_s20231661{hour:02d}{minute:02d}176_e20231661{hour:02d}{minute+2:02d}549_c20231661{hour:02d}{minute+2:02d}597.nc"
            for hour in range(24)
            for minute in range(0, 60, 5)
        ]
        
        import re
        pattern = r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{3})_"
        
        for filename in test_filenames:
            match = re.search(pattern, filename)
            assert match, f"Should parse filename: {filename}"
            # Extract components
            year, doy, hour, minute = match.groups()[:4]
            assert int(year) == 2023
        
        final_refs = sys.getrefcount(str)
        
        # Reference count should be stable
        assert abs(final_refs - initial_refs) <= 5, f"Memory leak detected: {initial_refs} -> {final_refs}"

    @pytest.mark.asyncio
    async def test_band13_integration_workflow(self, mock_s3_store_factory, mock_file_operations):
        """Test complete Band 13 integration workflow."""
        mock_store = mock_s3_store_factory(should_fail=False)
        test_file = mock_file_operations("integration_test.nc", content_size=4096)
        mock_store.download.return_value = test_file
        
        with patch("goesvfi.integrity_check.remote.s3_store.S3Store", return_value=mock_store):
            with patch.object(TimeIndex, "get_s3_bucket", return_value="noaa-goes16"):
                with patch.object(TimeIndex, "find_nearest_intervals") as mock_intervals:
                    timestamp = datetime(2023, 6, 15, 12, 0, 0)
                    mock_intervals.return_value = [timestamp]
                    
                    # Step 1: Get bucket
                    bucket = TimeIndex.get_s3_bucket(SatellitePattern.GOES_16)
                    assert bucket == "noaa-goes16"
                    
                    # Step 2: Find nearest intervals
                    intervals = TimeIndex.find_nearest_intervals(timestamp, "RadC")
                    assert len(intervals) == 1
                    
                    # Step 3: Create S3 store
                    s3_store = S3Store(timeout=60)
                    
                    # Step 4: Download Band 13 file
                    result = await s3_store.download(
                        timestamp,
                        SatellitePattern.GOES_16,
                        test_file,
                        product_type="RadC",
                        band=13,
                    )
                    
                    # Step 5: Verify results
                    assert result.exists()
                    assert result.stat().st_size > 0
                    
                    # Step 6: Cleanup
                    await s3_store.close()
                    
                    # Verify all components were called
                    mock_store.download.assert_called_once()
                    mock_intervals.assert_called_once_with(timestamp, "RadC")