"""Optimized real S3 patterns tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common S3 pattern configurations and real data examples
- Parameterized test scenarios for comprehensive pattern validation
- Enhanced pattern matching and timestamp handling testing
- Mock-based testing to avoid real S3 calls while validating realistic patterns
- Comprehensive edge case and boundary condition testing
"""

from datetime import datetime, timedelta
import re
from typing import List, Dict, Any
import pytest

from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SatellitePattern,
    filter_s3_keys_by_band,
    to_s3_key,
)
from goesvfi.utils import date_utils


class TestRealS3PatternsV2:
    """Optimized test class for real S3 patterns functionality."""

    @pytest.fixture(scope="class")
    def scan_schedule_configurations(self):
        """Define various scan schedule configuration test cases."""
        return {
            "full_disk": {
                "product_type": "RadF",
                "minutes": RADF_MINUTES,
                "interval": 10,
                "expected_minutes": [0, 10, 20, 30, 40, 50],
                "description": "Full disk scans every 10 minutes",
            },
            "conus": {
                "product_type": "RadC", 
                "minutes": RADC_MINUTES,
                "interval": 5,
                "expected_minutes": [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56],
                "description": "CONUS scans every 5 minutes",
            },
            "mesoscale": {
                "product_type": "RadM",
                "minutes": RADM_MINUTES,
                "interval": 1,
                "expected_minutes": list(range(60)),
                "description": "Mesoscale scans every minute",
            },
        }

    @pytest.fixture(scope="class")
    def real_file_examples(self):
        """Define real GOES file pattern examples from S3."""
        return {
            "radf_examples": [
                "OR_ABI-L1b-RadF-M6C13_G16_s20230661200000_e20230661209214_c20230661209291.nc",
                "OR_ABI-L1b-RadF-M6C13_G18_s20240920100012_e20240920109307_c20240920109383.nc",
                "OR_ABI-L1b-RadF-M6C01_G16_s20231661200000_e20231661209214_c20231661209291.nc",
                "OR_ABI-L1b-RadF-M6C02_G18_s20240920100012_e20240920109307_c20240920109383.nc",
                "OR_ABI-L1b-RadF-M6C07_G16_s20230661200000_e20230661209214_c20230661209291.nc",
            ],
            "radc_examples": [
                "OR_ABI-L1b-RadC-M6C13_G16_s20231661206190_e20231661208562_c20231661209032.nc",
                "OR_ABI-L1b-RadC-M6C13_G18_s20240920101189_e20240920103562_c20240920104022.nc",
                "OR_ABI-L1b-RadC-M6C01_G16_s20231661206190_e20231661208562_c20231661209032.nc",
                "OR_ABI-L1b-RadC-M6C02_G18_s20240920101189_e20240920103562_c20240920104022.nc",
                "OR_ABI-L1b-RadC-M6C14_G16_s20231661206190_e20231661208562_c20231661209032.nc",
            ],
            "radm_examples": [
                "OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
                "OR_ABI-L1b-RadM1-M6C13_G18_s20240920100245_e20240920100302_c20240920100347.nc",
                "OR_ABI-L1b-RadM2-M6C01_G16_s20231661200245_e20231661200302_c20231661200344.nc",
                "OR_ABI-L1b-RadM2-M6C02_G18_s20240920100245_e20240920100302_c20240920100347.nc",
                "OR_ABI-L1b-RadM1-M6C07_G16_s20231661200245_e20231661200302_c20231661200344.nc",
            ],
        }

    @pytest.fixture(scope="class")
    def band_test_cases(self):
        """Define band-specific test cases."""
        return {
            "visible_bands": [1, 2, 3],
            "near_ir_bands": [4, 5, 6], 
            "infrared_bands": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
            "popular_bands": [1, 2, 7, 13, 14],
            "all_bands": list(range(1, 17)),
        }

    @pytest.fixture(scope="class")
    def timestamp_test_cases(self):
        """Define various timestamp test cases."""
        return {
            "standard_times": [
                datetime(2023, 6, 15, 12, 0, 0),    # Standard noon
                datetime(2023, 6, 15, 0, 0, 0),     # Midnight
                datetime(2023, 6, 15, 18, 30, 0),   # Evening
            ],
            "edge_case_times": [
                datetime(2023, 1, 1, 0, 0, 0),      # New Year
                datetime(2023, 12, 31, 23, 59, 0),  # End of year
                datetime(2024, 2, 29, 12, 0, 0),    # Leap day
            ],
            "various_doy": [
                datetime(2024, 4, 1, 12, 0, 0),     # April 1, DOY 92
                datetime(2024, 11, 1, 12, 0, 0),    # November 1, DOY 306
                datetime(2024, 2, 29, 12, 0, 0),    # Leap day, DOY 60
            ],
            "minute_boundary_cases": [
                datetime(2023, 6, 15, 12, 32, 0),   # Minute 32 for nearest selection
                datetime(2023, 6, 15, 12, 14, 0),   # Minute 14 for RadC selection
                datetime(2023, 6, 15, 12, 7, 30),   # Minute 7:30 for rounding
            ],
        }

    @pytest.fixture(scope="class")
    def wildcard_test_cases(self):
        """Define wildcard pattern test cases."""
        return {
            "exact_match_cases": [
                {"exact_match": True, "should_have_wildcards": False},
                {"exact_match": False, "should_have_wildcards": True},
            ],
            "wildcard_positions": [
                "timestamp_wildcards",  # *s20231661*
                "end_time_wildcards",   # *e20231661*
                "create_time_wildcards", # *c20231661*
            ],
        }

    @pytest.mark.parametrize("schedule_name", ["full_disk", "conus", "mesoscale"])
    def test_scan_schedule_patterns(self, scan_schedule_configurations, schedule_name):
        """Test scan schedule patterns for different product types."""
        config = scan_schedule_configurations[schedule_name]
        
        # Verify schedule matches expected pattern
        assert config["minutes"] == config["expected_minutes"]
        
        # Verify interval consistency
        if len(config["minutes"]) > 1:
            intervals = [config["minutes"][i+1] - config["minutes"][i] 
                        for i in range(len(config["minutes"]) - 1)]
            
            if schedule_name in ["full_disk", "conus"]:
                # Regular intervals
                assert all(interval == config["interval"] for interval in intervals)
            else:
                # Mesoscale has 1-minute intervals (continuous)
                assert all(interval == 1 for interval in intervals)

    @pytest.mark.parametrize("satellite", [SatellitePattern.GOES_16, SatellitePattern.GOES_18])
    @pytest.mark.parametrize("product_type", ["RadF", "RadC", "RadM"])
    @pytest.mark.parametrize("band", [1, 7, 13])
    def test_s3_key_generation_comprehensive(self, satellite, product_type, band):
        """Test comprehensive S3 key generation for different combinations."""
        timestamp = datetime(2023, 6, 15, 12, 30, 0)
        
        # Generate S3 key
        key = to_s3_key(timestamp, satellite, product_type=product_type, band=band)
        
        # Verify basic structure
        assert key.startswith(f"ABI-L1b-{product_type}/2023/166/12/")
        
        # Verify satellite code
        if satellite == SatellitePattern.GOES_16:
            assert "G16" in key
        else:
            assert "G18" in key
        
        # Verify band formatting
        assert f"C{band:02d}_" in key
        
        # Verify scan mode
        assert "M6" in key
        
        # Verify timestamp structure
        assert "s2023166" in key  # Year and DOY
        assert key.endswith(".nc")

    @pytest.mark.parametrize("timestamp_category", [
        "standard_times",
        "edge_case_times", 
        "various_doy",
        "minute_boundary_cases",
    ])
    def test_timestamp_handling_scenarios(self, timestamp_test_cases, timestamp_category):
        """Test timestamp handling in S3 key generation."""
        timestamps = timestamp_test_cases[timestamp_category]
        
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 13
        
        for timestamp in timestamps:
            key = to_s3_key(timestamp, satellite, product_type=product_type, band=band)
            
            # Verify DOY calculation
            expected_doy = date_utils.date_to_doy(timestamp.date())
            assert f"/{expected_doy:03d}/" in key
            assert f"s{timestamp.year}{expected_doy:03d}" in key
            
            # Verify hour formatting
            assert f"/{timestamp.hour:02d}/" in key

    def test_nearest_minute_selection_comprehensive(self):
        """Test nearest minute selection for different product types."""
        test_cases = [
            # RadF cases (10-minute intervals: 0, 10, 20, 30, 40, 50)
            {"product": "RadF", "input_minute": 32, "expected_minute": 30},
            {"product": "RadF", "input_minute": 7, "expected_minute": 10},
            {"product": "RadF", "input_minute": 55, "expected_minute": 50},
            {"product": "RadF", "input_minute": 0, "expected_minute": 0},
            
            # RadC cases (5-minute intervals: 1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56)
            {"product": "RadC", "input_minute": 32, "expected_minute": 31},
            {"product": "RadC", "input_minute": 14, "expected_minute": 11},
            {"product": "RadC", "input_minute": 58, "expected_minute": 56},
            {"product": "RadC", "input_minute": 1, "expected_minute": 1},
            
            # RadM cases (every minute: 0-59)
            {"product": "RadM", "input_minute": 32, "expected_minute": 32},
            {"product": "RadM", "input_minute": 14, "expected_minute": 14},
            {"product": "RadM", "input_minute": 59, "expected_minute": 59},
        ]
        
        for case in test_cases:
            timestamp = datetime(2023, 6, 15, 12, case["input_minute"], 0)
            key = to_s3_key(timestamp, SatellitePattern.GOES_16, 
                           product_type=case["product"], band=13)
            
            # Extract minute from key
            pattern = rf"s20231661{12:02d}(\d{{2}})"
            match = re.search(pattern, key)
            assert match, f"Could not find minute pattern in key: {key}"
            
            actual_minute = int(match.group(1))
            assert actual_minute == case["expected_minute"], \
                f"For {case['product']} minute {case['input_minute']}, expected {case['expected_minute']}, got {actual_minute}"

    @pytest.mark.parametrize("band_category", [
        "visible_bands",
        "near_ir_bands", 
        "infrared_bands",
        "popular_bands",
    ])
    def test_band_filtering_comprehensive(self, real_file_examples, band_test_cases, band_category):
        """Test band filtering with various band categories."""
        bands = band_test_cases[band_category]
        
        # Create test keys with all bands
        all_keys = []
        for product_examples in real_file_examples.values():
            all_keys.extend(product_examples)
        
        for band in bands:
            # Filter for this specific band
            filtered_keys = filter_s3_keys_by_band(all_keys, band)
            
            # Verify all returned keys contain the correct band
            for key in filtered_keys:
                assert f"C{band:02d}_" in key, f"Key {key} should contain band {band:02d}"
            
            # Verify we get reasonable results (some bands are in the examples)
            if band in [1, 2, 7, 13, 14]:  # Bands present in examples
                assert len(filtered_keys) > 0, f"Should find some keys for band {band}"

    @pytest.mark.parametrize("file_category", ["radf_examples", "radc_examples", "radm_examples"])
    def test_real_file_pattern_validation(self, real_file_examples, file_category):
        """Test validation of real file patterns from S3."""
        examples = real_file_examples[file_category]
        
        for filename in examples:
            # Verify basic structure
            assert filename.startswith("OR_ABI-L1b-")
            assert filename.endswith(".nc")
            assert "M6C" in filename  # Scan mode and channel
            assert "_G1" in filename  # Satellite code
            assert "_s202" in filename  # Start time
            assert "_e202" in filename  # End time  
            assert "_c202" in filename  # Creation time
            
            # Extract and verify components
            parts = filename.split('_')
            assert len(parts) >= 6, f"Filename should have at least 6 parts: {filename}"
            
            # Verify product type
            product_part = parts[1]  # ABI-L1b-{product}-M6C{band}
            assert product_part.startswith("ABI-L1b-")
            
            # Verify satellite code
            satellite_part = parts[2]
            assert satellite_part in ["G16", "G18"], f"Invalid satellite code: {satellite_part}"

    @pytest.mark.parametrize("exact_match", [True, False])
    def test_wildcard_pattern_handling(self, exact_match):
        """Test wildcard pattern handling in S3 keys."""
        timestamp = datetime(2023, 6, 15, 12, 30, 0)
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 13
        
        key = to_s3_key(timestamp, satellite, product_type=product_type, 
                       band=band, exact_match=exact_match)
        
        if exact_match:
            # Should not contain wildcards
            assert "*" not in key
            # Should have specific timestamp components
            assert "s2023166" in key
        else:
            # Should contain wildcards
            assert "*" in key
            # May have wildcards in timestamp areas

    def test_doy_calculation_edge_cases(self):
        """Test day-of-year calculation for edge cases."""
        edge_cases = [
            # Regular year cases
            (datetime(2023, 1, 1), 1),       # First day
            (datetime(2023, 12, 31), 365),   # Last day of regular year
            
            # Leap year cases
            (datetime(2024, 1, 1), 1),       # First day of leap year
            (datetime(2024, 2, 29), 60),     # Leap day
            (datetime(2024, 3, 1), 61),      # Day after leap day
            (datetime(2024, 12, 31), 366),   # Last day of leap year
            
            # Common dates
            (datetime(2024, 4, 1), 92),      # April 1 in leap year
            (datetime(2023, 4, 1), 91),      # April 1 in regular year
            (datetime(2024, 11, 1), 306),    # November 1 in leap year
        ]
        
        for timestamp, expected_doy in edge_cases:
            key = to_s3_key(timestamp, SatellitePattern.GOES_16, 
                           product_type="RadC", band=13)
            
            # Verify DOY in path structure
            assert f"/{expected_doy:03d}/" in key
            
            # Verify DOY in timestamp
            assert f"s{timestamp.year}{expected_doy:03d}" in key

    def test_cross_product_comprehensive_validation(self):
        """Test comprehensive cross-product validation of all parameters."""
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
        products = ["RadF", "RadC", "RadM1", "RadM2"]
        bands = [1, 7, 13, 16]
        timestamps = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2024, 2, 29, 18, 45, 0),  # Leap day evening
        ]
        
        valid_combinations = 0
        
        for satellite in satellites:
            for product in products:
                for band in bands:
                    for timestamp in timestamps:
                        try:
                            key = to_s3_key(timestamp, satellite, 
                                          product_type=product, band=band)
                            
                            # Verify key is well-formed
                            assert key.startswith("ABI-L1b-")
                            assert key.endswith(".nc")
                            assert f"C{band:02d}_" in key
                            
                            # Verify satellite code
                            if satellite == SatellitePattern.GOES_16:
                                assert "G16" in key
                            else:
                                assert "G18" in key
                            
                            # Verify product type
                            assert product in key
                            
                            valid_combinations += 1
                            
                        except Exception as e:
                            pytest.fail(f"Failed for {satellite.name}, {product}, band {band}, {timestamp}: {e}")
        
        # Should have generated keys for all combinations
        expected_combinations = len(satellites) * len(products) * len(bands) * len(timestamps)
        assert valid_combinations == expected_combinations

    def test_pattern_consistency_across_time_ranges(self):
        """Test pattern consistency across different time ranges."""
        base_time = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 13
        
        # Generate keys for a 24-hour period
        time_keys = []
        for hour in range(24):
            timestamp = base_time.replace(hour=hour)
            key = to_s3_key(timestamp, satellite, product_type=product_type, band=band)
            time_keys.append((timestamp, key))
        
        # Verify consistent structure across all hours
        for timestamp, key in time_keys:
            # Should have consistent prefix
            assert key.startswith("ABI-L1b-RadC/2023/166/")
            
            # Should have hour-specific path
            assert f"/{timestamp.hour:02d}/" in key
            
            # Should have consistent filename structure
            filename = key.split('/')[-1]
            assert filename.startswith("OR_ABI-L1b-RadC-M6C13_G16_s")
            assert filename.endswith(".nc")

    def test_band_filtering_with_mixed_products(self):
        """Test band filtering with mixed product types."""
        # Create keys with same band across different products
        mixed_keys = [
            "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s20231661200000_e20231661209214_c20231661209291.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661206190_e20231661208562_c20231661209032.nc",
            "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
            "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C07_G16_s20231661200000_e20231661209214_c20231661209291.nc",
            "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C07_G16_s20231661206190_e20231661208562_c20231661209032.nc",
        ]
        
        # Filter for band 13
        band13_keys = filter_s3_keys_by_band(mixed_keys, 13)
        assert len(band13_keys) == 3  # RadF, RadC, RadM1 with band 13
        
        for key in band13_keys:
            assert "C13_" in key
            assert "C07_" not in key
        
        # Filter for band 7
        band7_keys = filter_s3_keys_by_band(mixed_keys, 7)
        assert len(band7_keys) == 2  # RadF, RadC with band 7
        
        for key in band7_keys:
            assert "C07_" in key
            assert "C13_" not in key

    def test_performance_bulk_key_generation(self):
        """Test performance of bulk S3 key generation."""
        import time
        
        # Generate many keys to test performance
        start_time = time.time()
        
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
        products = ["RadF", "RadC", "RadM1"]
        bands = [1, 7, 13]
        
        generated_keys = []
        for i in range(50):  # Reduced for CI performance
            timestamp = datetime(2023, 6, 15, 12, 0, 0) + timedelta(hours=i)
            for satellite in satellites:
                for product in products:
                    for band in bands:
                        key = to_s3_key(timestamp, satellite, product_type=product, band=band)
                        generated_keys.append(key)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should generate keys quickly
        assert duration < 2.0, f"Key generation too slow: {duration:.3f}s for {len(generated_keys)} keys"
        
        # Verify all keys are valid
        assert len(generated_keys) == 50 * 2 * 3 * 3  # 900 keys
        for key in generated_keys[:10]:  # Spot check
            assert key.startswith("ABI-L1b-")
            assert key.endswith(".nc")

    def test_memory_efficiency_pattern_operations(self):
        """Test memory efficiency during pattern operations."""
        import sys
        
        initial_refs = sys.getrefcount(str)
        
        # Perform many pattern operations
        for i in range(1000):
            timestamp = datetime(2023, 6, 15, 12, 0, 0) + timedelta(minutes=i)
            satellite = SatellitePattern.GOES_16 if i % 2 == 0 else SatellitePattern.GOES_18
            product = ["RadF", "RadC", "RadM1"][i % 3]
            band = [1, 7, 13][i % 3]
            
            # Generate key
            key = to_s3_key(timestamp, satellite, product_type=product, band=band)
            
            # Filter operation
            filtered = filter_s3_keys_by_band([key], band)
            assert len(filtered) == 1
            
            # Check memory periodically
            if i % 100 == 0:
                current_refs = sys.getrefcount(str)
                assert abs(current_refs - initial_refs) <= 20, f"Memory leak at iteration {i}"
        
        final_refs = sys.getrefcount(str)
        assert abs(final_refs - initial_refs) <= 50, f"Memory leak detected: {initial_refs} -> {final_refs}"

    def test_edge_case_filename_parsing(self):
        """Test edge case filename parsing scenarios."""
        edge_case_filenames = [
            # Very long timestamps
            "OR_ABI-L1b-RadF-M6C13_G16_s20231661200000_e20231661209999_c20231661999999.nc",
            
            # Different scan modes (though M6 is standard)
            "OR_ABI-L1b-RadC-M3C13_G18_s20231661206190_e20231661208562_c20231661209032.nc",
            
            # All 16 bands
            "OR_ABI-L1b-RadF-M6C16_G16_s20231661200000_e20231661209214_c20231661209291.nc",
            
            # Mesoscale variations
            "OR_ABI-L1b-RadM2-M6C01_G18_s20231661200245_e20231661200302_c20231661200344.nc",
        ]
        
        for filename in edge_case_filenames:
            # Extract band from filename
            match = re.search(r'C(\d{2})_', filename)
            if match:
                band = int(match.group(1))
                
                # Test filtering works
                filtered = filter_s3_keys_by_band([filename], band)
                assert len(filtered) == 1
                assert filtered[0] == filename
            else:
                pytest.fail(f"Could not extract band from filename: {filename}")

    def test_realistic_s3_key_structure_validation(self):
        """Test that generated keys match realistic S3 bucket structure."""
        timestamp = datetime(2023, 6, 15, 12, 30, 0)
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 13
        
        key = to_s3_key(timestamp, satellite, product_type=product_type, band=band)
        
        # Should match NOAA's actual S3 structure
        # Format: ABI-L1b-{product}/{year}/{doy}/{hour}/{filename}
        parts = key.split('/')
        
        assert len(parts) == 5
        assert parts[0] == "ABI-L1b-RadC"
        assert parts[1] == "2023"
        assert parts[2] == "166"  # DOY for June 15
        assert parts[3] == "12"   # Hour
        
        filename = parts[4]
        assert filename.startswith("OR_ABI-L1b-RadC-M6C13_G16_s")
        assert "_e2023166" in filename  # End time
        assert "_c2023166" in filename  # Creation time
        assert filename.endswith(".nc")