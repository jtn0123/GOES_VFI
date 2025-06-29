"""
Optimized unit tests for S3 key patterns using real GOES data patterns.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for test dates and pattern configurations
- Enhanced test managers for comprehensive pattern validation
- Batch testing of multiple bands, products, and satellites
- Improved real pattern validation with test data sets
"""

from datetime import datetime
import re
from typing import Any

import pytest

from goesvfi.integrity_check.time_index import (
    RADC_MINUTES,
    RADF_MINUTES,
    RADM_MINUTES,
    SatellitePattern,
    filter_s3_keys_by_band,
    to_s3_key,
)


class TestRealS3PatternsOptimizedV2:
    """Optimized tests for S3 key patterns using real GOES data samples."""

    @pytest.fixture(scope="class")
    def s3_pattern_test_components(self):
        """Create shared components for S3 pattern testing."""

        # Enhanced S3 Pattern Test Manager
        class S3PatternTestManager:
            """Manage S3 pattern testing scenarios."""

            def __init__(self) -> None:
                # Define test configurations
                self.test_configs = {
                    "test_dates": [
                        datetime(2023, 6, 15, 12, 30, 0),
                        datetime(2024, 4, 1, 10, 15, 0),  # Day 092
                        datetime(2024, 2, 29, 12, 0, 0),  # Leap year day 060
                        datetime(2024, 11, 1, 12, 0, 0),  # Day 306
                    ],
                    "satellites": [SatellitePattern.GOES_16, SatellitePattern.GOES_18],
                    "product_types": ["RadF", "RadC", "RadM"],
                    "bands": [1, 2, 7, 9, 13, 16],
                    "minute_schedules": {"RadF": RADF_MINUTES, "RadC": RADC_MINUTES, "RadM": RADM_MINUTES},
                }

                # Real S3 key examples
                self.real_s3_examples = [
                    # RadF examples
                    "OR_ABI-L1b-RadF-M6C13_G16_s20230661200000_e20230661209214_c20230661209291.nc",
                    "OR_ABI-L1b-RadF-M6C13_G18_s20240920100012_e20240920109307_c20240920109383.nc",
                    "OR_ABI-L1b-RadF-M6C01_G16_s20231661000000_e20231661009214_c20231661009291.nc",
                    # RadC examples
                    "OR_ABI-L1b-RadC-M6C13_G16_s20231661206190_e20231661208562_c20231661209032.nc",
                    "OR_ABI-L1b-RadC-M6C13_G18_s20240920101189_e20240920103562_c20240920104022.nc",
                    "OR_ABI-L1b-RadC-M6C02_G16_s20231661211190_e20231661213562_c20231661214024.nc",
                    # RadM examples
                    "OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
                    "OR_ABI-L1b-RadM1-M6C13_G18_s20240920100245_e20240920100302_c20240920100347.nc",
                    "OR_ABI-L1b-RadM2-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
                ]

                # Real key patterns from logs
                self.log_key_examples = [
                    "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20231661211190_e20231661213562_c20231661214024.nc",
                    "ABI-L1b-RadF/2024/092/10/OR_ABI-L1b-RadF-M6C01_G18_s20240921000012_e20240921009307_c20240921009377.nc",
                    "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G16_s20231661200245_e20231661200302_c20231661200344.nc",
                ]

                # Define test scenarios
                self.test_scenarios = {
                    "minute_schedules": self._test_minute_schedules,
                    "s3_key_formats": self._test_s3_key_formats,
                    "band_handling": self._test_band_handling,
                    "wildcard_patterns": self._test_wildcard_patterns,
                    "band_filtering": self._test_band_filtering,
                    "doy_handling": self._test_doy_handling,
                    "minute_selection": self._test_minute_selection,
                    "real_patterns": self._test_real_patterns,
                    "comprehensive_validation": self._test_comprehensive_validation,
                }

            def extract_minute_from_key(self, key: str) -> int:
                """Extract minute from S3 key pattern."""
                # Pattern to match the minute in timestamps like s20231661211
                pattern = re.compile(r"s\d{7}\d{2}(\d{2})")
                match = pattern.search(key)
                if match:
                    return int(match.group(1))
                return -1

            def validate_key_structure(
                self, key: str, product_type: str, satellite: SatellitePattern, band: int, timestamp: datetime
            ) -> dict[str, bool]:
                """Validate S3 key structure components."""
                year = timestamp.year
                doy = timestamp.timetuple().tm_yday
                hour = timestamp.hour

                sat_code = "G16" if satellite == SatellitePattern.GOES_16 else "G18"

                validation = {
                    "has_product_type": f"ABI-L1b-{product_type}" in key,
                    "has_year": str(year) in key,
                    "has_doy": f"{doy:03d}" in key,
                    "has_hour": f"{hour:02d}" in key,
                    "has_band": f"C{band:02d}" in key,
                    "has_satellite": sat_code in key,
                    "has_mode": "M6" in key,  # Mode 6 is standard
                }

                validation["all_valid"] = all(validation.values())
                return validation

            def _test_minute_schedules(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test minute schedule patterns."""
                results = {}

                if scenario_name == "schedule_validation":
                    # Validate each product's minute schedule
                    schedule_results = {}

                    # RadF schedule
                    radf_valid = RADF_MINUTES == [0, 10, 20, 30, 40, 50] and all(
                        RADF_MINUTES[i + 1] - RADF_MINUTES[i] == 10 for i in range(len(RADF_MINUTES) - 1)
                    )
                    schedule_results["RadF"] = {"minutes": RADF_MINUTES, "interval": 10, "valid": radf_valid}

                    # RadC schedule
                    radc_valid = RADC_MINUTES == [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56] and all(
                        RADC_MINUTES[i + 1] - RADC_MINUTES[i] == 5 for i in range(len(RADC_MINUTES) - 1)
                    )
                    schedule_results["RadC"] = {"minutes": RADC_MINUTES, "interval": 5, "valid": radc_valid}

                    # RadM schedule
                    radm_valid = list(range(60)) == RADM_MINUTES and len(RADM_MINUTES) == 60
                    schedule_results["RadM"] = {
                        "minutes": RADM_MINUTES[:10],  # Show first 10 for brevity
                        "total_count": len(RADM_MINUTES),
                        "valid": radm_valid,
                    }

                    results["schedules"] = schedule_results
                    results["all_valid"] = all(s["valid"] for s in schedule_results.values())

                    # All schedules should be valid
                    assert results["all_valid"]

                return {"scenario": scenario_name, "results": results}

            def _test_s3_key_formats(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test S3 key format generation."""
                results = {}

                if scenario_name == "basic_formats":
                    # Test basic key formats for each product type
                    format_results = []

                    for product_type in self.test_configs["product_types"]:
                        for satellite in self.test_configs["satellites"]:
                            # Use appropriate minute for product type
                            if product_type == "RadF":
                                test_ts = datetime(2023, 6, 15, 12, 0, 0)  # 00 minute
                            elif product_type == "RadC":
                                test_ts = datetime(2023, 6, 15, 12, 11, 0)  # 11 minute
                            else:  # RadM
                                test_ts = datetime(2023, 6, 15, 12, 32, 0)  # Any minute

                            key = to_s3_key(test_ts, satellite, product_type=product_type, band=13)

                            validation = self.validate_key_structure(key, product_type, satellite, 13, test_ts)

                            format_results.append({
                                "product_type": product_type,
                                "satellite": satellite.name,
                                "key": key,
                                "validation": validation,
                            })

                    results["formats"] = format_results
                    results["all_valid"] = all(f["validation"]["all_valid"] for f in format_results)

                    # All formats should be valid
                    assert results["all_valid"]

                elif scenario_name == "timestamp_precision":
                    # Test timestamp handling with exact product minutes
                    precision_results = []

                    test_cases = [
                        ("RadF", datetime(2023, 6, 15, 12, 0, 0), "00"),
                        ("RadC", datetime(2023, 6, 15, 12, 14, 0), "11"),  # Nearest is 11
                        ("RadM", datetime(2023, 6, 15, 12, 32, 0), "32"),  # Exact
                    ]

                    for product_type, test_ts, expected_minute in test_cases:
                        key = to_s3_key(test_ts, SatellitePattern.GOES_16, product_type=product_type, band=13)

                        minute_extracted = self.extract_minute_from_key(key)

                        precision_results.append({
                            "product_type": product_type,
                            "input_minute": test_ts.minute,
                            "expected_minute": expected_minute,
                            "actual_minute": f"{minute_extracted:02d}",
                            "correct": f"{minute_extracted:02d}" == expected_minute,
                        })

                    results["precision_tests"] = precision_results
                    results["all_correct"] = all(p["correct"] for p in precision_results)

                    assert results["all_correct"]

                return {"scenario": scenario_name, "results": results}

            def _test_band_handling(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test band handling in S3 keys."""
                results = {}

                if scenario_name == "multiple_bands":
                    # Test key generation for multiple bands
                    band_results = []

                    test_ts = datetime(2023, 6, 15, 12, 30, 0)

                    for band in self.test_configs["bands"]:
                        key = to_s3_key(test_ts, SatellitePattern.GOES_18, product_type="RadC", band=band)

                        band_results.append({
                            "band": band,
                            "band_string": f"C{band:02d}",
                            "in_key": f"M6C{band:02d}_G18_s" in key,
                            "key_segment": key[key.find("M6C") : key.find("_G18") + 4],
                        })

                        # Verify band formatting
                        assert f"M6C{band:02d}_G18_s" in key

                    results["band_tests"] = band_results
                    results["all_bands_present"] = all(b["in_key"] for b in band_results)

                    assert results["all_bands_present"]

                return {"scenario": scenario_name, "results": results}

            def _test_wildcard_patterns(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test wildcard pattern handling."""
                results = {}

                if scenario_name == "wildcard_generation":
                    # Test wildcard vs exact match patterns
                    test_ts = datetime(2023, 6, 15, 12, 30, 0)

                    wildcard_results = []
                    for exact_match in [True, False]:
                        key = to_s3_key(
                            test_ts, SatellitePattern.GOES_16, product_type="RadC", band=13, exact_match=exact_match
                        )

                        wildcard_results.append({"exact_match": exact_match, "has_wildcards": "*" in key, "key": key})

                    # Verify wildcard behavior
                    assert wildcard_results[0]["exact_match"]
                    assert not wildcard_results[0]["has_wildcards"]
                    assert not wildcard_results[1]["exact_match"]
                    assert wildcard_results[1]["has_wildcards"]

                    results["wildcard_tests"] = wildcard_results
                    results["behavior_correct"] = True

                return {"scenario": scenario_name, "results": results}

            def _test_band_filtering(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test S3 key filtering by band."""
                results = {}

                if scenario_name == "filter_operations":
                    # Test filtering with various key sets
                    test_keys = [
                        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s2023166121100_e2023166121159_c20231661212.nc",
                        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C01_G16_s2023166121100_e2023166121159_c20231661212.nc",
                        "ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C02_G16_s2023166121100_e2023166121159_c20231661212.nc",
                        "ABI-L1b-RadF/2023/166/12/OR_ABI-L1b-RadF-M6C13_G16_s2023166120000_e2023166120590_c20231661206.nc",
                        "ABI-L1b-RadM1/2023/166/12/OR_ABI-L1b-RadM1-M6C13_G16_s2023166120000_e2023166120059_c20231661201.nc",
                    ]

                    filter_results = []
                    for band in [1, 2, 13]:
                        filtered = filter_s3_keys_by_band(test_keys, band)

                        filter_results.append({
                            "band": band,
                            "count": len(filtered),
                            "keys": filtered,
                            "all_match": all(f"C{band:02d}_" in key for key in filtered),
                        })

                    # Verify filter counts
                    assert filter_results[0]["count"] == 1  # Band 1
                    assert filter_results[1]["count"] == 1  # Band 2
                    assert filter_results[2]["count"] == 3  # Band 13

                    results["filter_tests"] = filter_results
                    results["all_filters_correct"] = all(f["all_match"] for f in filter_results)

                elif scenario_name == "real_key_filtering":
                    # Test with real S3 examples
                    filter_results = []

                    for band in [1, 13]:
                        filtered = filter_s3_keys_by_band(self.real_s3_examples, band)

                        filter_results.append({
                            "band": band,
                            "count": len(filtered),
                            "all_correct_band": all(f"C{band:02d}_" in key for key in filtered),
                        })

                    results["real_filter_tests"] = filter_results
                    results["all_correct"] = all(f["all_correct_band"] for f in filter_results)

                    assert results["all_correct"]

                return {"scenario": scenario_name, "results": results}

            def _test_doy_handling(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test day of year handling in keys."""
                results = {}

                if scenario_name == "doy_formatting":
                    # Test various dates for correct DOY formatting
                    doy_results = []

                    test_cases = [
                        (datetime(2024, 4, 1, 12, 0, 0), 92),  # April 1
                        (datetime(2024, 11, 1, 12, 0, 0), 306),  # Nov 1 (leap year)
                        (datetime(2024, 2, 29, 12, 0, 0), 60),  # Leap day
                        (datetime(2023, 1, 1, 0, 0, 0), 1),  # New Year
                        (datetime(2023, 12, 31, 23, 59, 0), 365),  # Last day
                    ]

                    for test_date, expected_doy in test_cases:
                        key = to_s3_key(test_date, SatellitePattern.GOES_18, product_type="RadC", band=13)

                        doy_results.append({
                            "date": test_date.strftime("%Y-%m-%d"),
                            "expected_doy": expected_doy,
                            "doy_in_path": f"/{expected_doy:03d}/" in key,
                            "doy_in_timestamp": f"s{test_date.year}{expected_doy:03d}" in key,
                            "key_segment": key[key.find(f"/{test_date.year}/") : key.find(f"/{test_date.hour:02d}/")],
                        })

                        # Verify DOY formatting
                        assert f"/{expected_doy:03d}/" in key
                        assert f"s{test_date.year}{expected_doy:03d}" in key

                    results["doy_tests"] = doy_results
                    results["all_correct"] = all(d["doy_in_path"] and d["doy_in_timestamp"] for d in doy_results)

                    assert results["all_correct"]

                return {"scenario": scenario_name, "results": results}

            def _test_minute_selection(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test nearest valid minute selection."""
                results = {}

                if scenario_name == "nearest_minute_logic":
                    # Test minute selection for various timestamps
                    minute_results = []

                    test_cases = [
                        # (product, input_minute, expected_minute)
                        ("RadF", 32, 30),  # RadF: 32 -> 30
                        ("RadC", 32, 31),  # RadC: 32 -> 31
                        ("RadM", 32, 32),  # RadM: 32 -> 32 (exact)
                        ("RadF", 5, 0),  # RadF: 5 -> 0
                        ("RadC", 5, 1),  # RadC: 5 -> 1
                        ("RadF", 55, 50),  # RadF: 55 -> 50
                        ("RadC", 55, 51),  # RadC: 55 -> 51
                    ]

                    for product_type, input_minute, expected_minute in test_cases:
                        test_ts = datetime(2023, 6, 15, 12, input_minute, 0)
                        key = to_s3_key(test_ts, SatellitePattern.GOES_18, product_type=product_type, band=13)

                        actual_minute = self.extract_minute_from_key(key)

                        minute_results.append({
                            "product_type": product_type,
                            "input_minute": input_minute,
                            "expected_minute": expected_minute,
                            "actual_minute": actual_minute,
                            "correct": actual_minute == expected_minute,
                        })

                    results["minute_tests"] = minute_results
                    results["all_correct"] = all(m["correct"] for m in minute_results)

                    assert results["all_correct"]

                return {"scenario": scenario_name, "results": results}

            def _test_real_patterns(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test with real S3 patterns."""
                results = {}

                if scenario_name == "real_examples":
                    # Test band filtering on real examples
                    real_results = []

                    # Test each unique band in real examples
                    bands_in_examples = set()
                    for key in self.real_s3_examples:
                        match = re.search(r"C(\d{2})_", key)
                        if match:
                            bands_in_examples.add(int(match.group(1)))

                    for band in sorted(bands_in_examples):
                        filtered = filter_s3_keys_by_band(self.real_s3_examples, band)
                        expected_count = sum(1 for k in self.real_s3_examples if f"C{band:02d}_" in k)

                        real_results.append({
                            "band": band,
                            "filtered_count": len(filtered),
                            "expected_count": expected_count,
                            "match": len(filtered) == expected_count,
                        })

                    results["real_pattern_tests"] = real_results
                    results["all_match"] = all(r["match"] for r in real_results)

                    assert results["all_match"]

                elif scenario_name == "log_examples":
                    # Test with examples from logs
                    log_results = []

                    # Filter by different bands
                    for band in [1, 13]:
                        filtered = filter_s3_keys_by_band(self.log_key_examples, band)

                        log_results.append({
                            "band": band,
                            "count": len(filtered),
                            "keys": [k.split("/")[-1] for k in filtered],  # Just filename
                        })

                    # Verify expected counts
                    assert log_results[0]["count"] == 1  # Band 1
                    assert log_results[1]["count"] == 2  # Band 13

                    results["log_filter_tests"] = log_results

                return {"scenario": scenario_name, "results": results}

            def _test_comprehensive_validation(self, scenario_name: str, **kwargs) -> dict[str, Any]:
                """Test comprehensive pattern validation."""
                results = {}

                if scenario_name == "full_validation":
                    # Comprehensive test across multiple dimensions
                    validation_count = 0
                    total_tests = 0

                    # Sample across products, satellites, and bands
                    for product_type in self.test_configs["product_types"]:
                        for satellite in self.test_configs["satellites"]:
                            for band in [1, 13]:  # Sample bands
                                test_ts = self.test_configs["test_dates"][0]

                                # Adjust minute for product type
                                if product_type == "RadF":
                                    test_ts = test_ts.replace(minute=30)
                                elif product_type == "RadC":
                                    test_ts = test_ts.replace(minute=31)
                                else:
                                    test_ts = test_ts.replace(minute=32)

                                key = to_s3_key(test_ts, satellite, product_type=product_type, band=band)

                                validation = self.validate_key_structure(key, product_type, satellite, band, test_ts)

                                total_tests += 1
                                if validation["all_valid"]:
                                    validation_count += 1

                    results["total_tests"] = total_tests
                    results["passed_tests"] = validation_count
                    results["success_rate"] = validation_count / total_tests

                    assert validation_count == total_tests

                return {"scenario": scenario_name, "results": results}

        return {"manager": S3PatternTestManager()}

    def test_minute_schedule_scenarios(self, s3_pattern_test_components) -> None:
        """Test minute schedule patterns."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_minute_schedules("schedule_validation")
        assert result["scenario"] == "schedule_validation"
        assert result["results"]["all_valid"] is True

        # Verify specific schedules
        schedules = result["results"]["schedules"]
        assert schedules["RadF"]["interval"] == 10
        assert schedules["RadC"]["interval"] == 5
        assert schedules["RadM"]["total_count"] == 60

    def test_s3_key_format_scenarios(self, s3_pattern_test_components) -> None:
        """Test S3 key format generation."""
        manager = s3_pattern_test_components["manager"]

        format_scenarios = ["basic_formats", "timestamp_precision"]

        for scenario in format_scenarios:
            result = manager._test_s3_key_formats(scenario)
            assert result["scenario"] == scenario

            if scenario == "basic_formats":
                assert result["results"]["all_valid"] is True
            elif scenario == "timestamp_precision":
                assert result["results"]["all_correct"] is True

    def test_band_handling_scenarios(self, s3_pattern_test_components) -> None:
        """Test band handling in S3 keys."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_band_handling("multiple_bands")
        assert result["scenario"] == "multiple_bands"
        assert result["results"]["all_bands_present"] is True
        assert len(result["results"]["band_tests"]) == 6

    def test_wildcard_pattern_scenarios(self, s3_pattern_test_components) -> None:
        """Test wildcard pattern handling."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_wildcard_patterns("wildcard_generation")
        assert result["scenario"] == "wildcard_generation"
        assert result["results"]["behavior_correct"] is True

    def test_band_filtering_scenarios(self, s3_pattern_test_components) -> None:
        """Test S3 key filtering by band."""
        manager = s3_pattern_test_components["manager"]

        filtering_scenarios = ["filter_operations", "real_key_filtering"]

        for scenario in filtering_scenarios:
            result = manager._test_band_filtering(scenario)
            assert result["scenario"] == scenario

            if scenario == "filter_operations":
                assert result["results"]["all_filters_correct"] is True
            elif scenario == "real_key_filtering":
                assert result["results"]["all_correct"] is True

    def test_doy_handling_scenarios(self, s3_pattern_test_components) -> None:
        """Test day of year handling."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_doy_handling("doy_formatting")
        assert result["scenario"] == "doy_formatting"
        assert result["results"]["all_correct"] is True
        assert len(result["results"]["doy_tests"]) == 5

    def test_minute_selection_scenarios(self, s3_pattern_test_components) -> None:
        """Test nearest valid minute selection."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_minute_selection("nearest_minute_logic")
        assert result["scenario"] == "nearest_minute_logic"
        assert result["results"]["all_correct"] is True

    def test_real_pattern_scenarios(self, s3_pattern_test_components) -> None:
        """Test with real S3 patterns."""
        manager = s3_pattern_test_components["manager"]

        real_scenarios = ["real_examples", "log_examples"]

        for scenario in real_scenarios:
            result = manager._test_real_patterns(scenario)
            assert result["scenario"] == scenario

            if scenario == "real_examples":
                assert result["results"]["all_match"] is True

    def test_comprehensive_validation_scenarios(self, s3_pattern_test_components) -> None:
        """Test comprehensive pattern validation."""
        manager = s3_pattern_test_components["manager"]

        result = manager._test_comprehensive_validation("full_validation")
        assert result["scenario"] == "full_validation"
        assert result["results"]["success_rate"] == 1.0

    @pytest.mark.parametrize(
        "product_type,expected_interval",
        [
            ("RadF", 10),
            ("RadC", 5),
            ("RadM", 1),  # Every minute
        ],
    )
    def test_product_minute_intervals(self, s3_pattern_test_components, product_type, expected_interval) -> None:
        """Test that each product type has correct minute intervals."""
        manager = s3_pattern_test_components["manager"]

        schedule = manager.test_configs["minute_schedules"][product_type]

        if product_type == "RadM":
            # RadM has every minute, so interval is 1
            assert len(schedule) == 60
        else:
            # Check intervals between consecutive minutes
            intervals = [schedule[i + 1] - schedule[i] for i in range(len(schedule) - 1)]
            assert all(interval == expected_interval for interval in intervals)

    def test_real_s3_patterns_comprehensive_validation(self, s3_pattern_test_components) -> None:
        """Test comprehensive S3 pattern validation."""
        manager = s3_pattern_test_components["manager"]

        # Test minute schedules
        result = manager._test_minute_schedules("schedule_validation")
        assert all(s["valid"] for s in result["results"]["schedules"].values())

        # Test key formats
        result = manager._test_s3_key_formats("basic_formats")
        assert len(result["results"]["formats"]) == 6  # 3 products × 2 satellites

        # Test band filtering
        result = manager._test_band_filtering("filter_operations")
        filter_tests = result["results"]["filter_tests"]
        assert filter_tests[0]["count"] == 1  # Band 1
        assert filter_tests[2]["count"] == 3  # Band 13

        # Test DOY handling
        result = manager._test_doy_handling("doy_formatting")
        doy_tests = result["results"]["doy_tests"]
        assert doy_tests[2]["expected_doy"] == 60  # Leap day

    def test_s3_patterns_integration_validation(self, s3_pattern_test_components) -> None:
        """Test S3 patterns integration scenarios."""
        manager = s3_pattern_test_components["manager"]

        # Create complex test scenario
        test_timestamp = datetime(2024, 2, 29, 12, 33, 45)  # Leap year, odd minute

        # Test each product type's minute selection
        for product_type in ["RadF", "RadC", "RadM"]:
            key = to_s3_key(test_timestamp, SatellitePattern.GOES_18, product_type=product_type, band=13)

            minute = manager.extract_minute_from_key(key)

            if product_type == "RadF":
                assert minute == 30  # Nearest RadF minute
            elif product_type == "RadC":
                assert minute == 31  # Nearest RadC minute
            elif product_type == "RadM":
                assert minute == 33  # Exact minute

            # Verify DOY for leap year
            assert "/060/" in key  # Feb 29 is day 60 in leap year
