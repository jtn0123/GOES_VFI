"""
Optimized tests for validation utilities with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for common test data
- Parameterized tests for similar validation scenarios
- Combined validation scenarios
- Enhanced edge case testing for better coverage
"""

import math
from pathlib import Path

import pytest

from goesvfi.utils.validation import validate_path_exists, validate_positive_int


class TestValidationOptimizedV2:
    """Optimized validation tests with full coverage."""

    @pytest.fixture(scope="class")
    def test_directory_structure(self, tmp_path_factory):
        """Create a shared test directory structure."""
        base_dir = tmp_path_factory.mktemp("validation_test")

        # Create test directories
        test_dirs = {
            "existing_dir": base_dir / "existing_directory",
            "nested_dir": base_dir / "parent" / "nested_directory",
            "empty_dir": base_dir / "empty_directory",
        }

        for dir_path in test_dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        # Create test files
        test_files = {
            "existing_file": base_dir / "test_file.txt",
            "nested_file": test_dirs["nested_dir"] / "nested_file.txt",
            "large_file": base_dir / "large_file.dat",
        }

        for file_path in test_files.values():
            file_path.touch()

        # Make large file actually large for testing
        test_files["large_file"].write_bytes(b"x" * 1024)  # 1KB file

        return {
            "base_dir": base_dir,
            "dirs": test_dirs,
            "files": test_files,
            "nonexistent_dir": base_dir / "nonexistent_directory",
            "nonexistent_file": base_dir / "nonexistent_file.txt",
        }

    @pytest.mark.parametrize(
        "path_type,must_be_dir,should_succeed",
        [
            ("existing_dir", True, True),  # Directory exists, expecting directory
            ("existing_file", False, True),  # File exists, not expecting directory
            ("nested_dir", True, True),  # Nested directory exists
            ("nested_file", False, True),  # Nested file exists
            ("existing_file", True, False),  # File exists but expecting directory
            ("existing_dir", False, True),  # Directory exists, not specifically expecting directory
        ],
    )
    def test_validate_path_exists_valid_scenarios(
        self, test_directory_structure, path_type, must_be_dir, should_succeed
    ) -> None:
        """Test path validation with valid existing paths."""
        if path_type in test_directory_structure["dirs"]:
            test_path = test_directory_structure["dirs"][path_type]
        else:
            test_path = test_directory_structure["files"][path_type]

        if should_succeed:
            result = validate_path_exists(test_path, must_be_dir=must_be_dir)
            assert result == test_path
            assert result.exists()
        else:
            with pytest.raises(ValueError, match="not a directory"):
                validate_path_exists(test_path, must_be_dir=must_be_dir)

    def test_validate_path_exists_missing_paths(self, test_directory_structure) -> None:
        """Test path validation with missing paths."""
        # Test missing directory
        with pytest.raises(FileNotFoundError):
            validate_path_exists(test_directory_structure["nonexistent_dir"], must_be_dir=True)

        # Test missing file
        with pytest.raises(FileNotFoundError):
            validate_path_exists(test_directory_structure["nonexistent_file"], must_be_dir=False)

        # Test missing path with default must_be_dir
        with pytest.raises(FileNotFoundError):
            validate_path_exists(test_directory_structure["nonexistent_dir"])

    def test_validate_path_exists_edge_cases(self, test_directory_structure) -> None:
        """Test path validation edge cases and error conditions."""
        base_dir = test_directory_structure["base_dir"]

        # Test with Path object
        path_obj = Path(test_directory_structure["dirs"]["existing_dir"])
        result = validate_path_exists(path_obj, must_be_dir=True)
        assert result == path_obj
        assert isinstance(result, Path)

        # Test with string path
        str_path = str(test_directory_structure["dirs"]["existing_dir"])
        result = validate_path_exists(str_path, must_be_dir=True)
        assert str(result) == str_path
        assert isinstance(result, Path)

        # Test with relative path
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            relative_path = "existing_directory"
            result = validate_path_exists(relative_path, must_be_dir=True)
            assert result.name == "existing_directory"
        finally:
            os.chdir(original_cwd)

        # Test with empty path
        with pytest.raises(FileNotFoundError):
            validate_path_exists("", must_be_dir=False)

    @pytest.mark.parametrize(
        "value,expected_result",
        [
            (1, 1),
            (5, 5),
            (100, 100),
            (999999, 999999),
            (42, 42),
        ],
    )
    def test_validate_positive_int_valid_values(self, value, expected_result) -> None:
        """Test positive integer validation with valid values."""
        result = validate_positive_int(value, "test_value")
        assert result == expected_result
        assert isinstance(result, int)

    @pytest.mark.parametrize(
        "invalid_value,expected_exception,error_pattern",
        [
            (0, ValueError, r"must be positive"),
            (-1, ValueError, r"must be positive"),
            (-100, ValueError, r"must be positive"),
            ("1", TypeError, r"must be an integer"),
            ("not_a_number", TypeError, r"must be an integer"),
            (1.5, TypeError, r"must be an integer"),
            (None, TypeError, r"must be an integer"),
            ([], TypeError, r"must be an integer"),
            ({}, TypeError, r"must be an integer"),
            (True, TypeError, r"must be an integer"),  # bool is subclass of int in Python
        ],
    )
    def test_validate_positive_int_invalid_values(self, invalid_value, expected_exception, error_pattern) -> None:
        """Test positive integer validation with invalid values."""
        with pytest.raises(expected_exception, match=error_pattern):
            validate_positive_int(invalid_value, "test_value")

    def test_validate_positive_int_custom_field_names(self) -> None:
        """Test positive integer validation with custom field names in error messages."""
        test_cases = [
            ("frame_count", 0),
            ("iteration_limit", -5),
            ("buffer_size", "not_a_number"),
            ("timeout_seconds", math.pi),
        ]

        for field_name, invalid_value in test_cases:
            with pytest.raises((ValueError, TypeError)) as exc_info:
                validate_positive_int(invalid_value, field_name)

            # Verify field name appears in error message
            assert field_name in str(exc_info.value)

    def test_validation_comprehensive_workflow(self, test_directory_structure) -> None:
        """Test comprehensive validation workflow with multiple validations."""
        test_directory_structure["base_dir"]

        # Validate multiple paths in sequence
        paths_to_validate = [
            (test_directory_structure["dirs"]["existing_dir"], True),
            (test_directory_structure["files"]["existing_file"], False),
            (test_directory_structure["dirs"]["nested_dir"], True),
            (test_directory_structure["files"]["nested_file"], False),
        ]

        validated_paths = []
        for path, must_be_dir in paths_to_validate:
            result = validate_path_exists(path, must_be_dir=must_be_dir)
            validated_paths.append(result)
            assert result.exists()

        # Validate multiple positive integers
        values_to_validate = [1, 10, 100, 1000, 42]
        validated_values = []
        for value in values_to_validate:
            result = validate_positive_int(value, f"value_{value}")
            validated_values.append(result)
            assert result > 0
            assert isinstance(result, int)

        # Verify all validations succeeded
        assert len(validated_paths) == len(paths_to_validate)
        assert len(validated_values) == len(values_to_validate)

    def test_validation_error_message_quality(self, test_directory_structure) -> None:
        """Test that validation error messages are informative."""
        # Test path validation error messages
        nonexistent_path = test_directory_structure["nonexistent_dir"]

        with pytest.raises(FileNotFoundError) as exc_info:
            validate_path_exists(nonexistent_path, must_be_dir=True)

        error_msg = str(exc_info.value)
        assert str(nonexistent_path) in error_msg or "not found" in error_msg.lower()

        # Test directory type mismatch error
        existing_file = test_directory_structure["files"]["existing_file"]

        with pytest.raises(ValueError) as exc_info:
            validate_path_exists(existing_file, must_be_dir=True)

        error_msg = str(exc_info.value)
        assert "not a directory" in error_msg.lower()

        # Test positive integer error messages
        with pytest.raises(ValueError) as exc_info:
            validate_positive_int(-5, "negative_value")

        error_msg = str(exc_info.value)
        assert "negative_value" in error_msg
        assert "positive" in error_msg.lower()

        with pytest.raises(TypeError) as exc_info:
            validate_positive_int("string", "string_value")

        error_msg = str(exc_info.value)
        assert "string_value" in error_msg
        assert "integer" in error_msg.lower()

    def test_validation_boundary_conditions(self, test_directory_structure) -> None:
        """Test validation with boundary conditions and edge cases."""
        # Test positive integer boundary (1 is the smallest positive integer)
        assert validate_positive_int(1, "minimum_positive") == 1

        # Test very large positive integer
        large_int = 2**31 - 1  # Max 32-bit signed integer
        assert validate_positive_int(large_int, "large_value") == large_int

        # Test very small negative integer
        with pytest.raises(ValueError):
            validate_positive_int(-(2**31), "very_negative")

        # Test path validation with various path types
        test_directory_structure["base_dir"]

        # Test with pathlib.Path object
        path_obj = Path(test_directory_structure["dirs"]["existing_dir"])
        result = validate_path_exists(path_obj, must_be_dir=True)
        assert isinstance(result, Path)

        # Test with absolute string path
        abs_str_path = str(test_directory_structure["dirs"]["existing_dir"].absolute())
        result = validate_path_exists(abs_str_path, must_be_dir=True)
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_validation_type_consistency(self, test_directory_structure) -> None:
        """Test that validation functions return consistent types."""
        # Path validation should always return Path objects
        test_path = test_directory_structure["dirs"]["existing_dir"]

        # Input as string
        result_from_str = validate_path_exists(str(test_path), must_be_dir=True)
        assert isinstance(result_from_str, Path)

        # Input as Path object
        result_from_path = validate_path_exists(test_path, must_be_dir=True)
        assert isinstance(result_from_path, Path)

        # Both should be equivalent
        assert result_from_str == result_from_path

        # Integer validation should always return int
        test_values = [1, 5, 100]
        for value in test_values:
            result = validate_positive_int(value, "test")
            assert isinstance(result, int)
            assert result == value

    def test_validation_concurrent_usage_simulation(self, test_directory_structure) -> None:
        """Test validation functions under simulated concurrent usage."""
        # Simulate multiple "threads" validating different resources
        validation_scenarios = [
            ("scenario_1", test_directory_structure["dirs"]["existing_dir"], True, 10),
            ("scenario_2", test_directory_structure["files"]["existing_file"], False, 25),
            ("scenario_3", test_directory_structure["dirs"]["nested_dir"], True, 50),
            ("scenario_4", test_directory_structure["files"]["nested_file"], False, 100),
        ]

        results = []
        for scenario_name, path, must_be_dir, int_value in validation_scenarios:
            # Validate path
            path_result = validate_path_exists(path, must_be_dir=must_be_dir)

            # Validate integer
            int_result = validate_positive_int(int_value, f"{scenario_name}_value")

            results.append((scenario_name, path_result, int_result))

        # Verify all validations succeeded and are consistent
        assert len(results) == len(validation_scenarios)
        for scenario_name, path_result, int_result in results:
            assert path_result.exists()
            assert int_result > 0
            assert isinstance(path_result, Path)
            assert isinstance(int_result, int)
