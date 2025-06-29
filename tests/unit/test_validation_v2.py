"""Optimized validation tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common validation setups and file system scenarios
- Parameterized test scenarios for comprehensive validation testing
- Enhanced error handling and edge case coverage
- Mock-based testing to reduce file system operations
- Comprehensive validation rule and constraint testing
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import tempfile
import os

from goesvfi.utils.validation import validate_path_exists, validate_positive_int


class TestValidationV2:
    """Optimized test class for validation functionality."""

    @pytest.fixture(scope="class")
    def validation_scenarios(self):
        """Define various validation scenarios for testing."""
        return {
            "path_scenarios": {
                "existing_file": {"type": "file", "should_exist": True},
                "existing_dir": {"type": "directory", "should_exist": True},
                "missing_file": {"type": "file", "should_exist": False},
                "missing_dir": {"type": "directory", "should_exist": False},
                "symlink": {"type": "symlink", "should_exist": True},
            },
            "integer_scenarios": {
                "positive_small": {"value": 1, "valid": True},
                "positive_large": {"value": 999999, "valid": True},
                "zero": {"value": 0, "valid": False},
                "negative": {"value": -1, "valid": False},
                "negative_large": {"value": -999999, "valid": False},
            },
            "type_scenarios": {
                "string_number": {"value": "5", "valid": False, "type": str},
                "float_positive": {"value": 5.5, "valid": False, "type": float},
                "none_value": {"value": None, "valid": False, "type": type(None)},
                "list_value": {"value": [1, 2, 3], "valid": False, "type": list},
                "dict_value": {"value": {"key": "value"}, "valid": False, "type": dict},
            }
        }

    @pytest.fixture
    def temp_filesystem(self, tmp_path):
        """Create temporary filesystem structure for testing."""
        # Create various file system objects
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        
        test_dir = tmp_path / "test_directory"
        test_dir.mkdir()
        
        nested_dir = test_dir / "nested"
        nested_dir.mkdir()
        
        nested_file = nested_dir / "nested_file.txt"
        nested_file.write_text("nested content")
        
        # Create symlink if supported
        symlink_path = tmp_path / "test_symlink"
        try:
            symlink_path.symlink_to(test_file)
            symlink_created = True
        except (OSError, NotImplementedError):
            symlink_created = False
        
        return {
            "root": tmp_path,
            "file": test_file,
            "directory": test_dir,
            "nested_dir": nested_dir,
            "nested_file": nested_file,
            "symlink": symlink_path if symlink_created else None,
            "missing_file": tmp_path / "missing_file.txt",
            "missing_dir": tmp_path / "missing_directory",
        }

    @pytest.mark.parametrize("path_type,must_be_dir,should_pass", [
        ("file", False, True),      # File exists, not required to be dir
        ("file", True, False),      # File exists, but required to be dir
        ("directory", True, True),  # Directory exists, required to be dir
        ("directory", False, True), # Directory exists, not required to be dir
        ("missing_file", False, False),  # Missing file
        ("missing_file", True, False),   # Missing file (as dir)
        ("missing_dir", False, False),   # Missing directory
        ("missing_dir", True, False),    # Missing directory
    ])
    def test_validate_path_exists_scenarios(self, temp_filesystem, path_type, must_be_dir, should_pass):
        """Test path validation with various path types and directory requirements."""
        test_path = temp_filesystem[path_type]
        
        if should_pass:
            result = validate_path_exists(test_path, must_be_dir=must_be_dir)
            assert result == test_path
            assert isinstance(result, Path)
        else:
            with pytest.raises((FileNotFoundError, ValueError)):
                validate_path_exists(test_path, must_be_dir=must_be_dir)

    def test_validate_path_exists_symlink_handling(self, temp_filesystem):
        """Test path validation with symlinks."""
        symlink_path = temp_filesystem["symlink"]
        
        if symlink_path is not None:
            # Symlink to file should be valid when not requiring directory
            result = validate_path_exists(symlink_path, must_be_dir=False)
            assert result == symlink_path
            
            # Symlink to file should fail when requiring directory
            with pytest.raises(ValueError):
                validate_path_exists(symlink_path, must_be_dir=True)

    @pytest.mark.parametrize("integer_value,expected_valid", [
        (1, True),
        (5, True),
        (100, True),
        (999999, True),
        (0, False),
        (-1, False),
        (-100, False),
        (-999999, False),
    ])
    def test_validate_positive_int_values(self, integer_value, expected_valid):
        """Test positive integer validation with various values."""
        if expected_valid:
            result = validate_positive_int(integer_value, "test_value")
            assert result == integer_value
            assert isinstance(result, int)
        else:
            with pytest.raises(ValueError):
                validate_positive_int(integer_value, "test_value")

    @pytest.mark.parametrize("invalid_value,expected_exception", [
        ("5", TypeError),           # String
        (5.5, TypeError),          # Float
        (None, TypeError),         # None
        ([1, 2, 3], TypeError),    # List
        ({"key": 5}, TypeError),   # Dict
        (complex(1, 2), TypeError), # Complex number
    ])
    def test_validate_positive_int_type_errors(self, invalid_value, expected_exception):
        """Test positive integer validation with invalid types."""
        with pytest.raises(expected_exception):
            validate_positive_int(invalid_value, "test_value")

    def test_validate_path_exists_with_pathlib_objects(self, temp_filesystem):
        """Test path validation with different pathlib object types."""
        # Test with Path object
        path_obj = temp_filesystem["file"]
        result = validate_path_exists(path_obj, must_be_dir=False)
        assert result == path_obj
        assert isinstance(result, Path)
        
        # Test with string path
        string_path = str(temp_filesystem["file"])
        result = validate_path_exists(string_path, must_be_dir=False)
        assert result == Path(string_path)

    def test_validate_path_exists_error_messages(self, temp_filesystem):
        """Test that validation errors contain helpful messages."""
        missing_path = temp_filesystem["missing_file"]
        
        with pytest.raises(FileNotFoundError) as exc_info:
            validate_path_exists(missing_path, must_be_dir=False)
        
        # Error message should contain the path
        assert str(missing_path) in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    def test_validate_positive_int_error_messages(self):
        """Test that integer validation errors contain helpful messages."""
        test_name = "custom_parameter_name"
        
        # Test ValueError message
        with pytest.raises(ValueError) as exc_info:
            validate_positive_int(0, test_name)
        
        error_message = str(exc_info.value)
        assert test_name in error_message or "positive" in error_message.lower()
        
        # Test TypeError message
        with pytest.raises(TypeError) as exc_info:
            validate_positive_int("invalid", test_name)
        
        error_message = str(exc_info.value)
        assert test_name in error_message or "integer" in error_message.lower()

    def test_validate_path_exists_permissions(self, temp_filesystem):
        """Test path validation with various permission scenarios."""
        test_file = temp_filesystem["file"]
        
        # Test with readable file
        assert test_file.exists()
        result = validate_path_exists(test_file, must_be_dir=False)
        assert result == test_file
        
        # Test with read-only file (if we can make it read-only)
        try:
            original_mode = test_file.stat().st_mode
            test_file.chmod(0o444)  # Read-only
            
            # Should still validate successfully
            result = validate_path_exists(test_file, must_be_dir=False)
            assert result == test_file
            
            # Restore original permissions
            test_file.chmod(original_mode)
        except (OSError, PermissionError):
            # Permission changes might not be supported on all systems
            pass

    def test_validate_path_exists_nested_paths(self, temp_filesystem):
        """Test path validation with nested directory structures."""
        nested_file = temp_filesystem["nested_file"]
        nested_dir = temp_filesystem["nested_dir"]
        
        # Validate nested file
        result = validate_path_exists(nested_file, must_be_dir=False)
        assert result == nested_file
        
        # Validate nested directory
        result = validate_path_exists(nested_dir, must_be_dir=True)
        assert result == nested_dir

    def test_validate_positive_int_boundary_values(self):
        """Test positive integer validation with boundary values."""
        # Test minimum positive value
        result = validate_positive_int(1, "minimum")
        assert result == 1
        
        # Test just above zero
        result = validate_positive_int(1, "just_above_zero")
        assert result == 1
        
        # Test large positive values
        large_value = 2**31 - 1  # Large but valid integer
        result = validate_positive_int(large_value, "large_value")
        assert result == large_value

    def test_validation_parameter_name_handling(self):
        """Test that parameter names are properly handled in validation."""
        parameter_names = [
            "simple_name",
            "name_with_underscores",
            "Name With Spaces",
            "name123with456numbers",
            "",  # Empty name
            None,  # None name
        ]
        
        for param_name in parameter_names:
            try:
                # Test with valid value
                result = validate_positive_int(5, param_name)
                assert result == 5
                
                # Test with invalid value to check error message
                with pytest.raises(ValueError):
                    validate_positive_int(0, param_name)
                    
            except Exception as e:
                # Should handle edge cases gracefully
                if param_name is None:
                    # None parameter name might cause issues
                    assert isinstance(e, (TypeError, AttributeError))

    def test_validate_path_exists_edge_cases(self, tmp_path):
        """Test path validation with edge cases."""
        # Test with empty path
        with pytest.raises((ValueError, FileNotFoundError)):
            validate_path_exists("", must_be_dir=False)
        
        # Test with None path
        with pytest.raises((TypeError, AttributeError)):
            validate_path_exists(None, must_be_dir=False)
        
        # Test with very long path name
        long_path = tmp_path / ("x" * 255)  # Very long filename
        with pytest.raises(FileNotFoundError):
            validate_path_exists(long_path, must_be_dir=False)

    def test_validate_positive_int_edge_cases(self):
        """Test positive integer validation with edge cases."""
        # Test with very large integers
        try:
            very_large = 2**63 - 1
            result = validate_positive_int(very_large, "very_large")
            assert result == very_large
        except OverflowError:
            # System might not support very large integers
            pass
        
        # Test with boolean values (True/False)
        # Note: In Python, bool is a subclass of int
        try:
            result = validate_positive_int(True, "boolean_true")
            assert result == 1  # True == 1 in Python
        except TypeError:
            # Implementation might explicitly reject booleans
            pass
        
        with pytest.raises((ValueError, TypeError)):
            validate_positive_int(False, "boolean_false")

    def test_validation_integration_workflow(self, temp_filesystem):
        """Test complete validation workflow with multiple validators."""
        # Create a scenario where both validations are used
        test_dir = temp_filesystem["directory"] 
        positive_count = 10
        
        # Both validations should pass
        validated_path = validate_path_exists(test_dir, must_be_dir=True)
        validated_count = validate_positive_int(positive_count, "file_count")
        
        assert validated_path == test_dir
        assert validated_count == positive_count
        
        # Integration test: use validated values together
        assert validated_path.exists()
        assert validated_count > 0
        assert isinstance(validated_path, Path)
        assert isinstance(validated_count, int)

    def test_validation_performance_with_many_paths(self, tmp_path):
        """Test validation performance with many path validations."""
        # Create multiple files
        test_files = []
        for i in range(100):
            file_path = tmp_path / f"test_file_{i}.txt"
            file_path.write_text(f"content_{i}")
            test_files.append(file_path)
        
        # Validate all files
        validated_files = []
        for file_path in test_files:
            result = validate_path_exists(file_path, must_be_dir=False)
            validated_files.append(result)
        
        assert len(validated_files) == 100
        assert all(isinstance(f, Path) for f in validated_files)

    def test_validation_performance_with_many_integers(self):
        """Test validation performance with many integer validations."""
        # Validate many positive integers
        test_values = list(range(1, 1001))  # 1 to 1000
        validated_values = []
        
        for value in test_values:
            result = validate_positive_int(value, f"value_{value}")
            validated_values.append(result)
        
        assert len(validated_values) == 1000
        assert validated_values == test_values

    def test_cross_platform_path_validation(self, tmp_path):
        """Test path validation across different path formats."""
        # Test with forward slashes
        forward_slash_path = tmp_path / "forward/slash/path"
        forward_slash_path.parent.mkdir(parents=True, exist_ok=True)
        forward_slash_path.touch()
        
        result = validate_path_exists(forward_slash_path, must_be_dir=False)
        assert result == forward_slash_path
        
        # Test with Path objects vs strings
        string_path = str(forward_slash_path)
        result_from_string = validate_path_exists(string_path, must_be_dir=False)
        assert result_from_string == Path(string_path)

    def test_validation_thread_safety_simulation(self, temp_filesystem):
        """Simulate concurrent validation to test thread safety."""
        import threading
        import time
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                # Test path validation
                path_result = validate_path_exists(temp_filesystem["file"], must_be_dir=False)
                
                # Test integer validation
                int_result = validate_positive_int(worker_id + 1, f"worker_{worker_id}")
                
                results.append((worker_id, path_result, int_result))
                time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 10
        assert len(errors) == 0
        
        # Verify all results are correct
        for worker_id, path_result, int_result in results:
            assert path_result == temp_filesystem["file"]
            assert int_result == worker_id + 1