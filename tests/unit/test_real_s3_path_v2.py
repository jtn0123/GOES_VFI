"""
Optimized tests for validating GOES file pattern matching with real S3 data.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for timestamp and satellite configurations
- Enhanced test managers for comprehensive S3 path validation
- Batch testing of multiple product types and satellites
- Improved pattern generation with validation helpers
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SATELLITE_CODES,
    SatellitePattern,
)
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class TestRealS3PathOptimizedV2:
    """Optimized tests for S3 path pattern generation with full coverage."""

    @pytest.fixture(scope="class")
    def s3_path_test_components(self) -> dict[str, Any]:  # noqa: PLR6301, C901
        """Create shared components for S3 path testing.

        Returns:
            dict[str, Any]: Dictionary containing S3 path testing components.
        """

        # Enhanced S3 Path Test Manager
        class S3PathTestManager:
            """Manage S3 path testing scenarios."""

            def __init__(self) -> None:
                # Define test configurations
                self.test_configs = {
                    "timestamps": [
                        datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC),
                        datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC),
                        datetime(2023, 12, 31, 23, 59, 0, tzinfo=UTC),
                        datetime(2024, 2, 29, 6, 30, 0, tzinfo=UTC),  # Leap year
                    ],
                    "satellites": [SatellitePattern.GOES_16, SatellitePattern.GOES_18],
                    "product_types": ["RadF", "RadC", "RadM"],
                    "bands": [1, 7, 13, 16],  # Various bands for testing
                    "file_patterns": {
                        "RadF": "OR_ABI-L1b-RadF-M6C{band}_{sat}_s{start}_e{end}_c{created}.nc",
                        "RadC": "OR_ABI-L1b-RadC-M6C{band}_{sat}_s{start}_e{end}_c{created}.nc",
                        "RadM": "OR_ABI-L1b-RadM{sector}-M6C{band}_{sat}_s{start}_e{end}_c{created}.nc",
                    },
                }

                # Product schedule mappings
                self.product_schedules = {"RadF": RADF_MINUTES, "RadC": RADC_MINUTES, "RadM": RADM_MINUTES}

                # Define test scenarios
                self.test_scenarios = {
                    "basic_patterns": self._test_basic_patterns,
                    "all_product_types": self._test_all_product_types,
                    "multiple_satellites": self._test_multiple_satellites,
                    "timestamp_variations": self._test_timestamp_variations,
                    "band_variations": self._test_band_variations,
                    "key_pattern_validation": self._test_key_pattern_validation,
                    "edge_cases": self._test_edge_cases,
                    "comprehensive_validation": self._test_comprehensive_validation,
                }

            def generate_s3_bucket(self, satellite: SatellitePattern) -> str:  # noqa: PLR6301
                """Generate S3 bucket name for a satellite.

                Returns:
                    str: The S3 bucket name for the satellite.
                """
                sat_code = SATELLITE_CODES.get(satellite, "G16")
                satellite_number = int(sat_code[1:])
                return f"noaa-goes{satellite_number}"

            def generate_s3_key_prefix(self, timestamp: datetime, product_type: str) -> str:  # noqa: PLR6301
                """Generate S3 key prefix for a timestamp and product type.

                Returns:
                    str: The S3 key prefix for the timestamp and product type.
                """
                year = timestamp.year
                day_of_year = timestamp.timetuple().tm_yday
                hour = timestamp.hour

                return f"ABI-L1b-{product_type}/{year}/{day_of_year:03d}/{hour:02d}/"

            @staticmethod
            def generate_filename(
                timestamp: datetime, satellite: SatellitePattern, product_type: str, band: int
            ) -> str:
                """Generate expected filename pattern.

                Returns:
                    str: The expected filename pattern.
                """
                sat_code = SATELLITE_CODES.get(satellite, "G16")

                # Create timestamp strings
                start_str = timestamp.strftime("%Y%j%H%M%S0")  # Year, DOY, HHMMSS0
                end_str = (timestamp + timedelta(minutes=10)).strftime("%Y%j%H%M%S0")
                created_str = (timestamp + timedelta(minutes=11)).strftime("%Y%j%H%M%S0")

                if product_type == "RadM":
                    # RadM includes sector number
                    return f"OR_ABI-L1b-RadM1-M6C{band:02d}_{sat_code}_s{start_str}_e{end_str}_c{created_str}.nc"
                return f"OR_ABI-L1b-{product_type}-M6C{band:02d}_{sat_code}_s{start_str}_e{end_str}_c{created_str}.nc"

            @staticmethod
            def validate_s3_pattern(
                bucket: str, key: str, satellite: SatellitePattern, product_type: str, timestamp: datetime
            ) -> dict[str, Any]:
                """Validate S3 pattern components.

                Returns:
                    dict[str, Any]: Validation results for S3 pattern components.
                """
                validation = {
                    "bucket_valid": bucket.startswith("noaa-goes"),
                    "satellite_match": str(SATELLITE_CODES.get(satellite, "G16")[1:]) in bucket,
                    "product_type_in_key": product_type in key,
                    "year_in_key": str(timestamp.year) in key,
                    "day_of_year_in_key": f"{timestamp.timetuple().tm_yday:03d}" in key,
                    "hour_in_key": f"{timestamp.hour:02d}" in key,
                }

                validation["all_valid"] = all(validation.values())
                return validation

            def _test_basic_patterns(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:
                """Test basic S3 pattern generation.

                Returns:
                    dict[str, Any]: Test results for basic pattern generation.
                """
                results = {}

                if scenario_name == "single_pattern":
                    # Test single pattern generation
                    timestamp = self.test_configs["timestamps"][0]
                    satellite = self.test_configs["satellites"][0]
                    product_type = self.test_configs["product_types"][0]
                    band = self.test_configs["bands"][2]  # Band 13

                    bucket = self.generate_s3_bucket(satellite)
                    key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                    filename = self.generate_filename(timestamp, satellite, product_type, band)

                    full_key = key_prefix + filename
                    dest_path = dest_dir / filename

                    validation = self.validate_s3_pattern(bucket, full_key, satellite, product_type, timestamp)

                    results["bucket"] = bucket
                    results["key"] = full_key
                    results["dest_path"] = str(dest_path)
                    results["validation"] = validation

                    # All validations should pass
                    assert validation["all_valid"]
                    assert bucket == "noaa-goes16"
                    assert product_type in full_key
                    assert f"C{band:02d}" in filename

                return {"scenario": scenario_name, "results": results}

            def _test_all_product_types(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
                """Test all product types.

                Returns:
                    dict[str, Any]: Test results for all product types.
                """
                results = {}

                if scenario_name == "product_type_patterns":
                    # Test pattern generation for all product types
                    timestamp = self.test_configs["timestamps"][0]
                    satellite = self.test_configs["satellites"][0]
                    band = 13

                    product_results = {}
                    for product_type in self.test_configs["product_types"]:
                        bucket = self.generate_s3_bucket(satellite)
                        key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                        filename = self.generate_filename(timestamp, satellite, product_type, band)

                        validation = self.validate_s3_pattern(
                            bucket, key_prefix + filename, satellite, product_type, timestamp
                        )

                        product_results[product_type] = {
                            "bucket": bucket,
                            "key_prefix": key_prefix,
                            "filename": filename,
                            "validation": validation,
                            "schedule": self.product_schedules[product_type],
                        }

                        # Verify product-specific patterns
                        assert validation["all_valid"]
                        assert f"ABI-L1b-{product_type}" in key_prefix
                        if product_type == "RadM":
                            assert "RadM1" in filename  # Sector included

                    results["product_patterns"] = product_results
                    results["all_valid"] = all(pr["validation"]["all_valid"] for pr in product_results.values())

                return {"scenario": scenario_name, "results": results}

            def _test_multiple_satellites(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
                """Test multiple satellite patterns.

                Returns:
                    dict[str, Any]: Test results for multiple satellite patterns.
                """
                results = {}

                if scenario_name == "satellite_variations":
                    # Test both GOES-16 and GOES-18
                    timestamp = self.test_configs["timestamps"][0]
                    product_type = "RadC"
                    band = 13

                    satellite_results = {}
                    for satellite in self.test_configs["satellites"]:
                        bucket = self.generate_s3_bucket(satellite)
                        key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                        filename = self.generate_filename(timestamp, satellite, product_type, band)

                        sat_code = SATELLITE_CODES.get(satellite, "G16")

                        satellite_results[satellite.name] = {
                            "bucket": bucket,
                            "key": key_prefix + filename,
                            "satellite_code": sat_code,
                            "satellite_number": int(sat_code[1:]),
                        }

                        # Verify satellite-specific patterns
                        assert f"goes{sat_code[1:]}" in bucket
                        assert sat_code in filename

                    # Verify different satellites have different buckets
                    buckets = [sr["bucket"] for sr in satellite_results.values()]
                    assert len(set(buckets)) == len(buckets), "Each satellite should have unique bucket"

                    results["satellite_patterns"] = satellite_results
                    results["unique_buckets"] = len(set(buckets))

                return {"scenario": scenario_name, "results": results}

            def _test_timestamp_variations(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
                """Test timestamp variation handling.

                Returns:
                    dict[str, Any]: Test results for timestamp variations.
                """
                results = {}

                if scenario_name == "various_timestamps":
                    # Test various timestamps including edge cases
                    satellite = self.test_configs["satellites"][0]
                    product_type = "RadF"

                    timestamp_results = []
                    for timestamp in self.test_configs["timestamps"]:
                        self.generate_s3_bucket(satellite)
                        key_prefix = self.generate_s3_key_prefix(timestamp, product_type)

                        # Extract date components
                        year = timestamp.year
                        day_of_year = timestamp.timetuple().tm_yday
                        hour = timestamp.hour

                        timestamp_results.append({
                            "timestamp": timestamp.isoformat(),
                            "year": year,
                            "day_of_year": day_of_year,
                            "hour": hour,
                            "key_prefix": key_prefix,
                            "key_contains_date": (
                                str(year) in key_prefix
                                and f"{day_of_year:03d}" in key_prefix
                                and f"{hour:02d}" in key_prefix
                            ),
                        })

                        # Verify date components in key
                        assert f"{year}/{day_of_year:03d}/{hour:02d}/" in key_prefix

                    results["timestamp_patterns"] = timestamp_results
                    results["all_valid"] = all(tr["key_contains_date"] for tr in timestamp_results)

                return {"scenario": scenario_name, "results": results}

            def _test_band_variations(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:
                """Test band variation handling.

                Returns:
                    dict[str, Any]: Test results for band variations.
                """
                results = {}

                if scenario_name == "multiple_bands":
                    # Test pattern generation for multiple bands
                    timestamp = self.test_configs["timestamps"][0]
                    satellite = self.test_configs["satellites"][0]
                    product_type = "RadC"

                    band_results = []
                    for band in self.test_configs["bands"]:
                        filename = self.generate_filename(timestamp, satellite, product_type, band)

                        band_results.append({
                            "band": band,
                            "filename": filename,
                            "band_in_filename": f"C{band:02d}" in filename,
                            "dest_path": str(dest_dir / filename),
                        })

                        # Verify band formatting
                        assert f"M6C{band:02d}" in filename

                    results["band_patterns"] = band_results
                    results["all_bands_valid"] = all(br["band_in_filename"] for br in band_results)

                return {"scenario": scenario_name, "results": results}

            def _test_key_pattern_validation(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
                """Test S3 key pattern validation.

                Returns:
                    dict[str, Any]: Test results for key pattern validation.
                """
                results = {}

                if scenario_name == "comprehensive_validation":
                    # Test comprehensive validation of patterns
                    validation_results = []

                    for satellite in self.test_configs["satellites"]:
                        for product_type in self.test_configs["product_types"]:
                            timestamp = self.test_configs["timestamps"][0]
                            band = 13

                            bucket = self.generate_s3_bucket(satellite)
                            key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                            filename = self.generate_filename(timestamp, satellite, product_type, band)
                            full_key = key_prefix + filename

                            validation = self.validate_s3_pattern(bucket, full_key, satellite, product_type, timestamp)

                            validation_results.append({
                                "satellite": satellite.name,
                                "product_type": product_type,
                                "bucket": bucket,
                                "key": full_key,
                                "validation": validation,
                            })

                    # All patterns should be valid
                    assert all(vr["validation"]["all_valid"] for vr in validation_results)

                    results["validations"] = validation_results
                    results["total_validated"] = len(validation_results)
                    results["all_valid"] = all(vr["validation"]["all_valid"] for vr in validation_results)

                return {"scenario": scenario_name, "results": results}

            def _test_edge_cases(self, scenario_name: str, dest_dir: Path, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
                """Test edge cases in pattern generation.

                Returns:
                    dict[str, Any]: Test results for edge cases.
                """
                results = {}

                if scenario_name == "boundary_conditions":
                    # Test edge cases
                    edge_cases = [
                        # New Year's Eve to New Year
                        (datetime(2023, 12, 31, 23, 59, 0, tzinfo=UTC), "year_boundary"),
                        # Start of year
                        (datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC), "year_start"),
                        # Leap year
                        (datetime(2024, 2, 29, 12, 0, 0, tzinfo=UTC), "leap_year"),
                        # Last hour of day
                        (datetime(2023, 6, 15, 23, 45, 0, tzinfo=UTC), "day_end"),
                    ]

                    satellite = self.test_configs["satellites"][0]
                    product_type = "RadF"
                    band = 13

                    edge_results = []
                    for timestamp, case_name in edge_cases:
                        key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                        filename = self.generate_filename(timestamp, satellite, product_type, band)

                        edge_results.append({
                            "case": case_name,
                            "timestamp": timestamp.isoformat(),
                            "day_of_year": timestamp.timetuple().tm_yday,
                            "key_prefix": key_prefix,
                            "filename": filename,
                            "valid": self.validate_s3_pattern(
                                self.generate_s3_bucket(satellite),
                                key_prefix + filename,
                                satellite,
                                product_type,
                                timestamp,
                            )["all_valid"],
                        })

                    # All edge cases should be valid
                    assert all(er["valid"] for er in edge_results)

                    results["edge_cases"] = edge_results
                    results["all_valid"] = all(er["valid"] for er in edge_results)

                return {"scenario": scenario_name, "results": results}

            def _test_comprehensive_validation(
                self,
                scenario_name: str,
                dest_dir: Path,
                **kwargs: Any,  # noqa: ARG002
            ) -> dict[str, Any]:
                """Test comprehensive validation across all dimensions.

                Returns:
                    dict[str, Any]: Test results for comprehensive validation.
                """
                results = {}

                if scenario_name == "full_matrix":
                    # Test a sample across all dimensions
                    test_count = 0
                    validation_count = 0

                    # Sample timestamps, satellites, products, and bands
                    for i, timestamp in enumerate(self.test_configs["timestamps"][:2]):
                        for _j, satellite in enumerate(self.test_configs["satellites"]):
                            for _k, product_type in enumerate(self.test_configs["product_types"][:2]):
                                band = self.test_configs["bands"][i % len(self.test_configs["bands"])]

                                bucket = self.generate_s3_bucket(satellite)
                                key_prefix = self.generate_s3_key_prefix(timestamp, product_type)
                                filename = self.generate_filename(timestamp, satellite, product_type, band)

                                validation = self.validate_s3_pattern(
                                    bucket, key_prefix + filename, satellite, product_type, timestamp
                                )

                                test_count += 1
                                if validation["all_valid"]:
                                    validation_count += 1

                    results["tests_run"] = test_count
                    results["validations_passed"] = validation_count
                    results["success_rate"] = validation_count / test_count if test_count > 0 else 0

                    # All should pass
                    assert validation_count == test_count

                return {"scenario": scenario_name, "results": results}

        return {"manager": S3PathTestManager()}

    @pytest.fixture()
    def temp_directory(self, tmp_path: Any) -> Any:  # noqa: PLR6301
        """Create temporary directory for each test.

        Returns:
            Any: Temporary directory path.
        """
        return tmp_path

    def test_basic_pattern_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test basic S3 pattern generation scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_basic_patterns("single_pattern", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "single_pattern"
        assert result["results"]["validation"]["all_valid"] is True
        assert result["results"]["bucket"] == "noaa-goes16"

    def test_all_product_type_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test all product type scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_all_product_types("product_type_patterns", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "product_type_patterns"
        assert len(result["results"]["product_patterns"]) == 3
        assert result["results"]["all_valid"] is True

    def test_multiple_satellite_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test multiple satellite scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_multiple_satellites("satellite_variations", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "satellite_variations"
        assert result["results"]["unique_buckets"] == 2
        assert "GOES_16" in result["results"]["satellite_patterns"]
        assert "GOES_18" in result["results"]["satellite_patterns"]

    def test_timestamp_variation_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test timestamp variation scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_timestamp_variations("various_timestamps", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "various_timestamps"
        assert len(result["results"]["timestamp_patterns"]) == 4
        assert result["results"]["all_valid"] is True

    def test_band_variation_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test band variation scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_band_variations("multiple_bands", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "multiple_bands"
        assert len(result["results"]["band_patterns"]) == 4
        assert result["results"]["all_bands_valid"] is True

    @staticmethod
    def test_key_pattern_validation_scenarios(s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:
        """Test S3 key pattern validation scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_key_pattern_validation("comprehensive_validation", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "comprehensive_validation"
        assert result["results"]["total_validated"] == 6  # 2 satellites x 3 product types
        assert result["results"]["all_valid"] is True

    def test_edge_case_scenarios(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301
        """Test edge case scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_edge_cases("boundary_conditions", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "boundary_conditions"
        assert len(result["results"]["edge_cases"]) == 4
        assert result["results"]["all_valid"] is True

    @staticmethod
    def test_comprehensive_validation_scenarios(s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:
        """Test comprehensive validation scenarios."""
        manager = s3_path_test_components["manager"]

        result = manager._test_comprehensive_validation("full_matrix", temp_directory)  # noqa: SLF001
        assert result["scenario"] == "full_matrix"
        assert result["results"]["success_rate"] == 1.0
        assert result["results"]["tests_run"] == result["results"]["validations_passed"]

    @pytest.mark.parametrize(
        "product_type,schedule", [("RadF", RADF_MINUTES), ("RadC", RADC_MINUTES), ("RadM", RADM_MINUTES)]
    )
    @staticmethod
    def test_product_schedule_alignment(
        s3_path_test_components: dict[str, Any], product_type: str, schedule: list[int]
    ) -> None:
        """Test that product types align with their schedules."""
        manager = s3_path_test_components["manager"]

        # Verify schedule mapping
        assert manager.product_schedules[product_type] == schedule

        # Test pattern generation for scheduled minutes
        timestamp = datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC)

        # Adjust timestamp to match schedule
        if schedule:
            minute = schedule[0] if schedule else 0
            timestamp = timestamp.replace(minute=minute)

        key_prefix = manager.generate_s3_key_prefix(timestamp, product_type)
        assert product_type in key_prefix

    @staticmethod
    def test_real_s3_path_comprehensive_validation(
        s3_path_test_components: dict[str, Any], temp_directory: Any
    ) -> None:
        """Test comprehensive S3 path validation."""
        manager = s3_path_test_components["manager"]

        # Test basic pattern
        result = manager._test_basic_patterns("single_pattern", temp_directory)  # noqa: SLF001
        assert "noaa-goes16" in result["results"]["bucket"]

        # Test all products
        result = manager._test_all_product_types("product_type_patterns", temp_directory)  # noqa: SLF001
        for product_type in ["RadF", "RadC", "RadM"]:
            assert product_type in result["results"]["product_patterns"]

        # Test satellites
        result = manager._test_multiple_satellites("satellite_variations", temp_directory)  # noqa: SLF001
        assert result["results"]["satellite_patterns"]["GOES_16"]["bucket"] == "noaa-goes16"
        assert result["results"]["satellite_patterns"]["GOES_18"]["bucket"] == "noaa-goes18"

        # Test edge cases
        result = manager._test_edge_cases("boundary_conditions", temp_directory)  # noqa: SLF001
        assert all(ec["valid"] for ec in result["results"]["edge_cases"])

    def test_s3_path_integration_validation(self, s3_path_test_components: dict[str, Any], temp_directory: Any) -> None:  # noqa: PLR6301, ARG002
        """Test S3 path integration scenarios."""
        manager = s3_path_test_components["manager"]

        # Create a complex scenario
        timestamp = datetime(2023, 12, 31, 23, 45, 0, tzinfo=UTC)  # Near year boundary

        for satellite in [SatellitePattern.GOES_16, SatellitePattern.GOES_18]:
            for product_type in ["RadF", "RadC", "RadM"]:
                bucket = manager.generate_s3_bucket(satellite)
                key_prefix = manager.generate_s3_key_prefix(timestamp, product_type)

                # Verify bucket format
                assert bucket.startswith("noaa-goes")

                # Verify key components
                assert str(timestamp.year) in key_prefix
                assert f"{timestamp.timetuple().tm_yday:03d}" in key_prefix
                assert f"{timestamp.hour:02d}" in key_prefix
                assert product_type in key_prefix

                # Verify full validation
                filename = manager.generate_filename(timestamp, satellite, product_type, 13)
                validation = manager.validate_s3_pattern(
                    bucket, key_prefix + filename, satellite, product_type, timestamp
                )
                assert validation["all_valid"]
