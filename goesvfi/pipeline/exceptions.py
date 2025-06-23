"""Custom exceptions for pipeline processing.

This module defines specific exception types for different error scenarios
in the video processing pipeline.
"""


class PipelineError(Exception):
    """Base exception for all pipeline-related errors."""


class ProcessingError(PipelineError):
    """Raised when there's an error during video/image processing."""


class FFmpegError(ProcessingError):
    """Raised when FFmpeg operations fail."""

    def __init__(self, message: str, command: str = "", stderr: str = "") -> None:
        """Initialize FFmpeg error with additional context.

        Args:
            message: Error message
            command: FFmpeg command that failed
            stderr: FFmpeg stderr output
        """
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class RIFEError(ProcessingError):
    """Raised when RIFE interpolation fails."""


class SanchezError(ProcessingError):
    """Raised when Sanchez processing fails."""


class InputError(PipelineError):
    """Raised when input validation fails."""


class OutputError(PipelineError):
    """Raised when output operations fail."""


class ResourceError(PipelineError):
    """Raised when system resources are insufficient."""

    def __init__(self, message: str, resource_type: str = "") -> None:
        """Initialize resource error with type information.

        Args:
            message: Error message
            resource_type: Type of resource (memory, disk, etc.)
        """
        super().__init__(message)
        self.resource_type = resource_type


class ConfigurationError(PipelineError):
    """Raised when configuration is invalid or missing."""
