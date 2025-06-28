"""S3 error conversion utilities.

This module provides utilities to convert S3/boto3 errors into
appropriate RemoteStoreError subclasses with user-friendly messages.
"""

import asyncio
from datetime import datetime
from typing import Any, Union

import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError as RemoteConnectionError,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

# Type alias for error types
RemoteErrorType = Union[
    AuthenticationError,
    ResourceNotFoundError,
    RemoteConnectionError,
    RemoteStoreError,
]


class S3ErrorConverter:
    """Converts S3/boto3 errors to appropriate RemoteStoreError subclasses."""

    @staticmethod
    def from_client_error(
        error: botocore.exceptions.ClientError,
        operation: str,
        satellite: SatellitePattern,
        timestamp: datetime,
        additional_context: dict[str, Any] | None = None,
    ) -> RemoteErrorType:
        """Convert a botocore ClientError to appropriate RemoteStoreError.

        Args:
            error: The botocore ClientError
            operation: Description of the operation (e.g., "download", "check existence")
            satellite: Satellite pattern being accessed
            timestamp: Timestamp being accessed
            additional_context: Optional additional context (bucket, key, etc.)

        Returns:
            Appropriate RemoteStoreError subclass
        """
        error_code = error.response.get("Error", {}).get("Code")
        error_message = error.response.get("Error", {}).get("Message", "Unknown error")

        # Build technical details
        context = additional_context or {}
        technical_details = S3ErrorConverter._build_technical_details(
            error_code, error_message, operation, satellite, timestamp, context
        )

        # Map error codes to appropriate error types
        if error_code in {"AccessDenied", "403", "InvalidAccessKeyId"}:
            return AuthenticationError(
                message=f"Access denied to {satellite.name} data",
                technical_details=technical_details + "\nNote: NOAA buckets should be publicly accessible.",
                original_exception=error,
            )
        if error_code in {"NoSuchBucket", "NoSuchKey", "404"}:
            return ResourceNotFoundError(
                message=f"Resource not found for {satellite.name} at {timestamp.isoformat()}",
                technical_details=technical_details + "\nThis data may not be available in the AWS S3 bucket.",
                original_exception=error,
            )
        # Check for timeout/connection issues in error message
        if "timeout" in str(error).lower() or "connection" in str(error).lower():
            return RemoteConnectionError(
                message=f"Connection error accessing {satellite.name} data",
                technical_details=technical_details + "\nThis suggests network connectivity issues.",
                original_exception=error,
            )
        return RemoteStoreError(
            message=f"Error {operation} for {satellite.name} data",
            technical_details=technical_details,
            original_exception=error,
        )

    @staticmethod
    def from_generic_error(
        error: Exception,
        operation: str,
        satellite: SatellitePattern,
        timestamp: datetime,
        additional_context: dict[str, Any] | None = None,
    ) -> RemoteErrorType:
        """Convert a generic exception to appropriate RemoteStoreError.

        Args:
            error: The exception that occurred
            operation: Description of the operation
            satellite: Satellite pattern being accessed
            timestamp: Timestamp being accessed
            additional_context: Optional additional context

        Returns:
            Appropriate RemoteStoreError subclass
        """
        error_str = str(error).lower()
        context = additional_context or {}

        # Build technical details
        technical_details = S3ErrorConverter._build_technical_details(
            None, str(error), operation, satellite, timestamp, context
        )

        # Determine error type based on error message
        if isinstance(error, PermissionError) or "permission" in error_str or "access" in error_str:
            return AuthenticationError(
                message=f"Permission error {operation} {satellite.name} data",
                technical_details=technical_details + "\nCheck file system permissions.",
                original_exception=error,
            )
        if isinstance(error, asyncio.TimeoutError | TimeoutError) or "timeout" in error_str:
            return RemoteConnectionError(
                message=f"Timeout {operation} {satellite.name} data",
                technical_details=technical_details + "\nCheck your internet connection speed.",
                original_exception=error,
            )
        if "not found" in error_str or "404" in error_str or "no such" in error_str:
            return ResourceNotFoundError(
                message=f"Resource not found for {satellite.name}",
                technical_details=technical_details,
                original_exception=error,
            )
        if "connection" in error_str or "network" in error_str:
            return RemoteConnectionError(
                message=f"Network error {operation} {satellite.name} data",
                technical_details=technical_details + "\nCheck your internet connection.",
                original_exception=error,
            )
        return RemoteStoreError(
            message=f"Error {operation} {satellite.name} data",
            technical_details=technical_details,
            original_exception=error,
        )

    @staticmethod
    def _build_technical_details(
        error_code: str | None,
        error_message: str,
        operation: str,
        satellite: SatellitePattern,
        timestamp: datetime,
        context: dict[str, Any],
    ) -> str:
        """Build technical details string for error.

        Args:
            error_code: S3 error code (if available)
            error_message: Error message
            operation: Operation being performed
            satellite: Satellite pattern
            timestamp: Timestamp
            context: Additional context (bucket, key, path, etc.)

        Returns:
            Formatted technical details string
        """
        details = [f"Operation: {operation}"]

        if error_code:
            details.append(f"S3 Error Code: {error_code}")

        details.extend((
            f"Error Message: {error_message}",
            f"Satellite: {satellite.name}",
            f"Timestamp: {timestamp.isoformat()} "
            f"(Year={timestamp.year}, DOY={timestamp.strftime('%j')}, "
            f"Hour={timestamp.strftime('%H')}, Minute={timestamp.strftime('%M')})",
        ))

        # Add context information
        if "bucket" in context:
            details.append(f"S3 Bucket: {context['bucket']}")
        if "key" in context:
            details.append(f"S3 Key: {context['key']}")
        if "path" in context:
            details.append(f"Local Path: {context['path']}")
        if "download_time" in context:
            details.append(f"Download Time: {context['download_time']:.2f}s")

        return "\n".join(details)

    @staticmethod
    def get_error_type(error: Exception) -> str:
        """Determine error type for statistics tracking.

        Args:
            error: The exception

        Returns:
            Error type string: "not_found", "auth", "timeout", "network", or "unknown"
        """
        if isinstance(error, ResourceNotFoundError):
            return "not_found"
        if isinstance(error, AuthenticationError):
            return "auth"
        if isinstance(error, RemoteConnectionError):
            # Further classify connection errors
            if "timeout" in str(error).lower():
                return "timeout"
            return "network"
        if isinstance(error, botocore.exceptions.ClientError):
            error_code = error.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                return "not_found"
            if error_code in {"AccessDenied", "403"}:
                return "auth"
            return "network"
        if isinstance(error, asyncio.TimeoutError | TimeoutError) or "timeout" in str(error).lower():
            return "timeout"
        if "connection" in str(error).lower() or "network" in str(error).lower():
            return "network"
        return "unknown"
