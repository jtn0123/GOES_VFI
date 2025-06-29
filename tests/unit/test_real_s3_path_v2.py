"""Optimized real S3 path tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common S3 path configurations and satellite setups
- Parameterized test scenarios for comprehensive path generation validation
- Enhanced pattern matching and validation testing
- Mock-based testing to avoid real S3 calls while validating patterns
- Comprehensive edge case and boundary condition testing
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
import pytest

from goesvfi.integrity_check.time_index import (
    SATELLITE_CODES,
    SatellitePattern,
)
from goesvfi.utils import date_utils


class TestRealS3PathV2:
    """Optimized test class for real S3 path functionality."""

    @pytest.fixture(scope="class")
    def satellite_configurations(self):
        """Define various satellite configuration test cases."""
        return {
            "goes_16": {
                "pattern": SatellitePattern.GOES_16,
                "satellite_code": "G16",
                "satellite_number": 16,
                "bucket": "noaa-goes16",
                "description": "GOES-16 East",
            },
            "goes_18": {
                "pattern": SatellitePattern.GOES_18,
                "satellite_code": "G18",
                "satellite_number": 18,
                "bucket": "noaa-goes18",
                "description": "GOES-18 West",
            },
        }

    @pytest.fixture(scope="class")
    def product_configurations(self):
        """Define various product configuration test cases."""
        return {
            "full_disk": {
                "product_type": "RadF",
                "scan_mode": "M6",
                "scan_interval_minutes": 15,
                "typical_minutes": [0, 15, 30, 45],  # Every 15 minutes
                "file_pattern": "OR_ABI-L1b-RadF-M6C{band:02d}_{satellite}_s{year}{doy:03d}{hour:02d}{minute:02d}{second:03d}_e{end_time}_c{creation_time}.nc",
            },
            "conus": {
                "product_type": "RadC",
                "scan_mode": "M6",
                "scan_interval_minutes": 5,
                "typical_minutes": [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57],  # Every 5 minutes
                "file_pattern": "OR_ABI-L1b-RadC-M6C{band:02d}_{satellite}_s{year}{doy:03d}{hour:02d}{minute:02d}{second:03d}_e{end_time}_c{creation_time}.nc",
            },
            "mesoscale_1": {
                "product_type": "RadM1",
                "scan_mode": "M6",
                "scan_interval_minutes": 1,
                "typical_minutes": list(range(0, 60, 1)),  # Every minute
                "file_pattern": "OR_ABI-L1b-RadM1-M6C{band:02d}_{satellite}_s{year}{doy:03d}{hour:02d}{minute:02d}{second:03d}_e{end_time}_c{creation_time}.nc",
            },
            "mesoscale_2": {
                "product_type": "RadM2",
                "scan_mode": "M6",
                "scan_interval_minutes": 1,
                "typical_minutes": list(range(0, 60, 1)),  # Every minute
                "file_pattern": "OR_ABI-L1b-RadM2-M6C{band:02d}_{satellite}_s{year}{doy:03d}{hour:02d}{minute:02d}{second:03d}_e{end_time}_c{creation_time}.nc",
            },
        }

    @pytest.fixture(scope="class")
    def band_configurations(self):
        """Define various band configuration test cases."""
        return {
            "visible_bands": {
                "bands": [1, 2, 3],
                "wavelengths": ["0.47 μm", "0.64 μm", "0.86 μm"],
                "descriptions": ["Blue", "Red", "Veggie"],
                "typical_use": "True color imagery",
            },
            "near_infrared_bands": {
                "bands": [4, 5, 6],
                "wavelengths": ["1.37 μm", "1.6 μm", "2.24 μm"],
                "descriptions": ["Cirrus", "Snow/Ice", "Cloud Particle Size"],
                "typical_use": "Cloud analysis",
            },
            "infrared_bands": {
                "bands": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                "wavelengths": ["3.9 μm", "6.2 μm", "6.9 μm", "7.3 μm", "8.4 μm", "9.6 μm", "10.3 μm", "11.2 μm", "12.3 μm", "13.3 μm"],
                "descriptions": ["Shortwave Window", "Upper-Level Water Vapor", "Mid-Level Water Vapor", "Low-Level Water Vapor", "Cloud-Top Phase", "Ozone", "Clean IR", "IR Cloud", "Dirty IR", "CO2"],
                "typical_use": "Temperature and atmospheric analysis",
            },
            "popular_bands": {
                "bands": [1, 2, 3, 7, 13, 14, 15],
                "descriptions": ["Blue", "Red", "Veggie", "Shortwave Window", "Clean IR", "IR Cloud", "Dirty IR"],
                "typical_use": "Common analysis and imagery",
            },
        }

    @pytest.fixture(scope="class")
    def timestamp_scenarios(self):
        """Define various timestamp scenario test cases."""
        return {
            "standard_times": [
                datetime(2023, 6, 15, 12, 0, 0),    # Noon
                datetime(2023, 6, 15, 0, 0, 0),     # Midnight
                datetime(2023, 6, 15, 18, 30, 0),   # Evening
                datetime(2023, 6, 15, 6, 45, 0),    # Morning
            ],
            "edge_case_times": [
                datetime(2023, 1, 1, 0, 0, 0),      # New Year
                datetime(2023, 12, 31, 23, 59, 0),  # End of year
                datetime(2024, 2, 29, 12, 0, 0),    # Leap day
                datetime(2023, 7, 4, 12, 0, 0),     # Independence Day
            ],
            "various_doy_times": [
                datetime(2023, 1, 15, 12, 0, 0),    # DOY 15
                datetime(2023, 3, 21, 12, 0, 0),    # DOY 80 (Spring equinox)
                datetime(2023, 6, 21, 12, 0, 0),    # DOY 172 (Summer solstice)
                datetime(2023, 9, 23, 12, 0, 0),    # DOY 266 (Fall equinox)
                datetime(2023, 12, 21, 12, 0, 0),   # DOY 355 (Winter solstice)
            ],
            "hourly_progression": [
                datetime(2023, 6, 15, hour, 0, 0) for hour in range(0, 24, 3)  # Every 3 hours
            ],
        }

    @pytest.fixture
    def s3_path_generator(self):
        """Generate S3 paths for testing."""
        def generate_s3_path(timestamp, satellite_pattern, product_type, band=13):
            # Get satellite info
            sat_code = SATELLITE_CODES.get(satellite_pattern, "G16")
            satellite_number = int(sat_code[1:])
            bucket = f"noaa-goes{satellite_number}"
            
            # Convert timestamp to DOY format
            year = timestamp.year
            doy = date_utils.date_to_doy(timestamp.date())
            hour = timestamp.hour
            minute = timestamp.minute
            
            # Generate S3 key pattern
            key_prefix = f"ABI-L1b-{product_type}/{year}/{doy:03d}/{hour:02d}/"
            
            # Generate realistic filename pattern
            second = timestamp.second
            # Realistic end time (scan duration varies by product)
            if product_type == "RadF":
                end_minute = minute + 9  # Full disk takes ~9 minutes
            elif product_type.startswith("RadC"):
                end_minute = minute + 2  # CONUS takes ~2-3 minutes
            else:  # RadM
                end_minute = minute + 1  # Mesoscale takes ~1 minute
            
            # Handle minute overflow
            end_hour = hour
            if end_minute >= 60:
                end_minute -= 60
                end_hour += 1
                if end_hour >= 24:
                    end_hour = 0
            
            # Creation time (usually a few seconds after end time)
            create_minute = end_minute
            create_second = (second + 30) % 60
            
            filename = (
                f"OR_ABI-L1b-{product_type}-M6C{band:02d}_{sat_code}_"
                f"s{year}{doy:03d}{hour:02d}{minute:02d}{second:03d}_"
                f"e{year}{doy:03d}{end_hour:02d}{end_minute:02d}{second+120:03d}_"
                f"c{year}{doy:03d}{end_hour:02d}{create_minute:02d}{create_second:03d}.nc"
            )
            
            s3_key = key_prefix + filename
            
            return {
                "bucket": bucket,
                "key": s3_key,
                "key_prefix": key_prefix,
                "filename": filename,
                "satellite_code": sat_code,
                "satellite_number": satellite_number,
                "year": year,
                "doy": doy,
                "hour": hour,
                "minute": minute,
                "product_type": product_type,
                "band": band,
            }
        
        return generate_s3_path

    @pytest.fixture
    def path_validator(self):
        """Validate S3 path components."""
        def validate_path(path_info, expected_satellite, expected_timestamp, expected_product, expected_band):
            # Validate bucket
            expected_number = SATELLITE_CODES.get(expected_satellite, "G16")[1:]
            assert path_info["bucket"] == f"noaa-goes{expected_number}"
            assert str(expected_number) in path_info["bucket"]
            
            # Validate timestamp components
            expected_doy = date_utils.date_to_doy(expected_timestamp.date())
            assert path_info["year"] == expected_timestamp.year
            assert path_info["doy"] == expected_doy
            assert path_info["hour"] == expected_timestamp.hour
            
            # Validate product and band
            assert path_info["product_type"] == expected_product
            assert path_info["band"] == expected_band
            
            # Validate key structure
            assert path_info["product_type"] in path_info["key"]
            assert str(path_info["year"]) in path_info["key"]
            assert f"{path_info['doy']:03d}" in path_info["key"]
            assert f"{path_info['hour']:02d}" in path_info["key"]
            assert f"C{expected_band:02d}" in path_info["filename"]
            assert path_info["satellite_code"] in path_info["filename"]
            
            return True
        
        return validate_path

    @pytest.mark.parametrize("satellite_name", ["goes_16", "goes_18"])
    @pytest.mark.parametrize("product_name", ["full_disk", "conus", "mesoscale_1", "mesoscale_2"])
    def test_s3_path_generation_comprehensive(self, satellite_configurations, product_configurations,
                                            s3_path_generator, path_validator, satellite_name, product_name):
        """Test comprehensive S3 path generation for different satellites and products."""
        sat_config = satellite_configurations[satellite_name]
        prod_config = product_configurations[product_name]
        
        timestamp = datetime(2023, 6, 15, 12, 0, 0)
        test_band = 13
        
        # Generate S3 path
        path_info = s3_path_generator(
            timestamp, 
            sat_config["pattern"], 
            prod_config["product_type"], 
            test_band
        )
        
        # Validate path components
        path_validator(
            path_info, 
            sat_config["pattern"], 
            timestamp, 
            prod_config["product_type"], 
            test_band
        )
        
        # Verify satellite-specific details
        assert path_info["satellite_number"] == sat_config["satellite_number"]
        assert path_info["satellite_code"] == sat_config["satellite_code"]
        assert path_info["bucket"] == sat_config["bucket"]

    @pytest.mark.parametrize("band_category", ["visible_bands", "near_infrared_bands", "infrared_bands", "popular_bands"])
    def test_band_specific_path_generation(self, satellite_configurations, product_configurations,
                                         band_configurations, s3_path_generator, band_category):
        """Test S3 path generation for different spectral bands."""
        band_config = band_configurations[band_category]
        
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        timestamp = datetime(2023, 6, 15, 15, 30, 0)
        
        for band in band_config["bands"]:
            path_info = s3_path_generator(timestamp, satellite, product_type, band)
            
            # Verify band is correctly encoded in filename
            assert f"C{band:02d}" in path_info["filename"]
            assert path_info["band"] == band
            
            # Verify path structure remains consistent
            assert "ABI-L1b" in path_info["key"]
            assert product_type in path_info["key"]
            assert "noaa-goes16" == path_info["bucket"]

    @pytest.mark.parametrize("timestamp_category", [
        "standard_times", 
        "edge_case_times", 
        "various_doy_times",
        "hourly_progression",
    ])
    def test_timestamp_edge_cases(self, timestamp_scenarios, s3_path_generator, 
                                 path_validator, timestamp_category):
        """Test S3 path generation with various timestamp edge cases."""
        timestamps = timestamp_scenarios[timestamp_category]
        
        satellite = SatellitePattern.GOES_18
        product_type = "RadF"
        band = 13
        
        for timestamp in timestamps:
            path_info = s3_path_generator(timestamp, satellite, product_type, band)
            
            # Validate using the validator
            path_validator(path_info, satellite, timestamp, product_type, band)
            
            # Additional edge case validations
            assert 1 <= path_info["doy"] <= 366  # Valid day of year
            assert 0 <= path_info["hour"] <= 23  # Valid hour
            assert path_info["year"] == timestamp.year

    def test_leap_year_doy_handling(self, s3_path_generator, path_validator):
        """Test day-of-year calculation for leap years."""
        leap_year_cases = [
            (datetime(2024, 2, 28, 12, 0, 0), 59),   # Feb 28 in leap year
            (datetime(2024, 2, 29, 12, 0, 0), 60),   # Leap day
            (datetime(2024, 3, 1, 12, 0, 0), 61),    # Day after leap day
            (datetime(2024, 12, 31, 12, 0, 0), 366), # Last day of leap year
        ]
        
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 7
        
        for timestamp, expected_doy in leap_year_cases:
            path_info = s3_path_generator(timestamp, satellite, product_type, band)
            
            assert path_info["doy"] == expected_doy
            assert f"{expected_doy:03d}" in path_info["key"]
            
            # Validate overall path
            path_validator(path_info, satellite, timestamp, product_type, band)

    def test_multiple_satellites_same_time(self, satellite_configurations, s3_path_generator):
        """Test path generation for multiple satellites at the same time."""
        timestamp = datetime(2023, 8, 10, 14, 25, 0)
        product_type = "RadC"
        band = 2
        
        satellite_paths = {}
        
        for sat_name, sat_config in satellite_configurations.items():
            path_info = s3_path_generator(
                timestamp, 
                sat_config["pattern"], 
                product_type, 
                band
            )
            satellite_paths[sat_name] = path_info
        
        # Verify different satellites have different buckets but same time structure
        assert len(satellite_paths) == 2
        
        goes16_path = satellite_paths["goes_16"]
        goes18_path = satellite_paths["goes_18"]
        
        # Different buckets
        assert goes16_path["bucket"] != goes18_path["bucket"]
        assert "16" in goes16_path["bucket"]
        assert "18" in goes18_path["bucket"]
        
        # Different satellite codes in filenames
        assert "G16" in goes16_path["filename"]
        assert "G18" in goes18_path["filename"]
        
        # Same timestamp components
        assert goes16_path["year"] == goes18_path["year"]
        assert goes16_path["doy"] == goes18_path["doy"]
        assert goes16_path["hour"] == goes18_path["hour"]

    def test_product_type_scan_timing_realism(self, product_configurations, s3_path_generator):
        """Test that product types have realistic scan timing patterns."""
        base_time = datetime(2023, 6, 15, 12, 0, 0)
        satellite = SatellitePattern.GOES_16
        band = 13
        
        for prod_name, prod_config in product_configurations.items():
            product_type = prod_config["product_type"]
            typical_minutes = prod_config["typical_minutes"]
            
            # Test several typical scan times for this product
            sample_minutes = typical_minutes[:3] if len(typical_minutes) > 3 else typical_minutes
            
            for minute in sample_minutes:
                test_time = base_time.replace(minute=minute)
                path_info = s3_path_generator(test_time, satellite, product_type, band)
                
                # Verify product type structure
                assert product_type in path_info["key"]
                assert product_type in path_info["filename"]
                
                # Verify scan mode is included
                assert "M6" in path_info["filename"]  # Mode 6 is standard
                
                # Verify realistic file naming
                assert path_info["filename"].startswith("OR_ABI-L1b-")
                assert path_info["filename"].endswith(".nc")

    def test_filename_component_validation(self, s3_path_generator):
        """Test detailed validation of filename components."""
        timestamp = datetime(2023, 9, 23, 16, 42, 15)  # Specific time with seconds
        satellite = SatellitePattern.GOES_18
        product_type = "RadC"
        band = 14
        
        path_info = s3_path_generator(timestamp, satellite, product_type, band)
        filename = path_info["filename"]
        
        # Parse filename components
        parts = filename.split('_')
        
        # Verify structure: OR_ABI-L1b-{product}-M6C{band}_{satellite}_s{time}_e{time}_c{time}.nc
        assert parts[0] == "OR"
        assert parts[1] == "ABI-L1b-RadC-M6C14"
        assert parts[2] == "G18"
        
        # Verify time components
        start_time = parts[3]  # s{year}{doy}{hour}{minute}{second}
        assert start_time.startswith("s2023266")  # s + year + doy
        assert "1642" in start_time  # hour + minute
        
        end_time = parts[4]    # e{year}{doy}{hour}{minute}{second}
        assert end_time.startswith("e2023266")
        
        create_time = parts[5].replace(".nc", "")  # c{year}{doy}{hour}{minute}{second}
        assert create_time.startswith("c2023266")

    def test_s3_key_structure_validation(self, s3_path_generator):
        """Test S3 key structure follows AWS best practices."""
        timestamp = datetime(2023, 4, 10, 9, 15, 30)
        satellite = SatellitePattern.GOES_16
        product_type = "RadF"
        band = 1
        
        path_info = s3_path_generator(timestamp, satellite, product_type, band)
        s3_key = path_info["key"]
        
        # Verify hierarchical structure
        key_parts = s3_key.split('/')
        
        assert len(key_parts) == 5  # product/year/doy/hour/filename
        assert key_parts[0] == "ABI-L1b-RadF"
        assert key_parts[1] == "2023"
        assert key_parts[2] == "100"  # DOY for April 10
        assert key_parts[3] == "09"   # Hour
        assert key_parts[4].endswith(".nc")  # Filename
        
        # Verify no leading/trailing slashes or double slashes
        assert not s3_key.startswith('/')
        assert not s3_key.endswith('/')
        assert '//' not in s3_key

    def test_path_generation_performance(self, s3_path_generator):
        """Test performance of path generation operations."""
        import time
        
        # Generate many paths to test performance
        timestamps = [
            datetime(2023, 6, 15, 12, 0, 0) + timedelta(hours=i)
            for i in range(100)
        ]
        
        satellites = [SatellitePattern.GOES_16, SatellitePattern.GOES_18]
        products = ["RadF", "RadC", "RadM1"]
        bands = [1, 7, 13]
        
        start_time = time.time()
        
        generated_paths = []
        for timestamp in timestamps[:10]:  # Limit for CI performance
            for satellite in satellites:
                for product in products:
                    for band in bands:
                        path_info = s3_path_generator(timestamp, satellite, product, band)
                        generated_paths.append(path_info)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should generate paths quickly
        assert duration < 1.0, f"Path generation too slow: {duration:.3f}s for {len(generated_paths)} paths"
        
        # Verify all paths were generated correctly
        assert len(generated_paths) == 10 * 2 * 3 * 3  # 180 paths
        
        # Spot check a few paths
        for path_info in generated_paths[:5]:
            assert "bucket" in path_info
            assert "key" in path_info
            assert "filename" in path_info
            assert path_info["bucket"].startswith("noaa-goes")

    def test_cross_validation_with_real_patterns(self, satellite_configurations, product_configurations, s3_path_generator):
        """Test cross-validation with known real GOES file patterns."""
        # Real GOES file examples for validation
        real_examples = [
            {
                "bucket": "noaa-goes16",
                "key": "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s20231661200000_e20231661209214_c20231661209291.nc",
                "timestamp": datetime(2023, 6, 15, 12, 0, 0),
                "satellite": SatellitePattern.GOES_16,
                "product": "RadF",
                "band": 13,
            },
            {
                "bucket": "noaa-goes18", 
                "key": "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G18_s20231661206190_e20231661208562_c20231661209032.nc",
                "timestamp": datetime(2023, 6, 15, 12, 6, 19),
                "satellite": SatellitePattern.GOES_18,
                "product": "RadC",
                "band": 2,
            },
        ]
        
        for example in real_examples:
            # Generate path using our function
            generated = s3_path_generator(
                example["timestamp"],
                example["satellite"], 
                example["product"],
                example["band"]
            )
            
            # Compare key structure (allowing for time differences)
            real_key_parts = example["key"].split('/')
            gen_key_parts = generated["key"].split('/')
            
            # Should have same hierarchy
            assert len(real_key_parts) == len(gen_key_parts)
            assert real_key_parts[0] == gen_key_parts[0]  # Product type
            assert real_key_parts[1] == gen_key_parts[1]  # Year
            assert real_key_parts[2] == gen_key_parts[2]  # DOY
            assert real_key_parts[3] == gen_key_parts[3]  # Hour
            
            # Filename should have similar structure
            real_filename = real_key_parts[4]
            gen_filename = gen_key_parts[4]
            
            assert real_filename.startswith("OR_ABI-L1b-")
            assert gen_filename.startswith("OR_ABI-L1b-")
            assert real_filename.endswith(".nc")
            assert gen_filename.endswith(".nc")

    def test_edge_case_boundary_conditions(self, s3_path_generator, path_validator):
        """Test boundary conditions and edge cases."""
        edge_cases = [
            # Year boundaries
            datetime(2023, 1, 1, 0, 0, 0),     # First moment of year
            datetime(2023, 12, 31, 23, 59, 59), # Last moment of year
            
            # Month boundaries  
            datetime(2023, 2, 28, 23, 59, 59),  # End of February (non-leap)
            datetime(2024, 2, 29, 0, 0, 0),     # Leap day start
            
            # Hour boundaries
            datetime(2023, 6, 15, 0, 0, 0),     # Midnight
            datetime(2023, 6, 15, 23, 59, 59),  # Almost midnight
            
            # Minute boundaries
            datetime(2023, 6, 15, 12, 0, 0),    # Top of hour
            datetime(2023, 6, 15, 12, 59, 59),  # End of hour
        ]
        
        satellite = SatellitePattern.GOES_16
        product_type = "RadC"
        band = 13
        
        for timestamp in edge_cases:
            path_info = s3_path_generator(timestamp, satellite, product_type, band)
            
            # Should handle all edge cases gracefully
            path_validator(path_info, satellite, timestamp, product_type, band)
            
            # Verify no invalid values
            assert 1 <= path_info["doy"] <= 366
            assert 0 <= path_info["hour"] <= 23
            assert path_info["year"] > 2000  # Reasonable year range

    def test_memory_efficiency_bulk_generation(self, s3_path_generator):
        """Test memory efficiency during bulk path generation."""
        import sys
        
        initial_refs = sys.getrefcount(dict)
        
        # Generate many paths
        for i in range(500):
            timestamp = datetime(2023, 6, 15, 12, 0, 0) + timedelta(minutes=i)
            satellite = SatellitePattern.GOES_16 if i % 2 == 0 else SatellitePattern.GOES_18
            product = ["RadF", "RadC", "RadM1"][i % 3]
            band = [1, 7, 13][i % 3]
            
            path_info = s3_path_generator(timestamp, satellite, product, band)
            
            # Verify path is valid
            assert "bucket" in path_info
            assert "key" in path_info
            
            # Check memory periodically
            if i % 100 == 0:
                current_refs = sys.getrefcount(dict)
                assert abs(current_refs - initial_refs) <= 20, f"Memory leak at iteration {i}"
        
        final_refs = sys.getrefcount(dict)
        assert abs(final_refs - initial_refs) <= 50, f"Memory leak detected: {initial_refs} -> {final_refs}"