"""S3 Store implementation for accessing GOES imagery via AWS S3 buckets.

This module provides a RemoteStore implementation that fetches GOES Band 13
NetCDF data from AWS S3 buckets using asynchronous boto3 operations.

Note: This implementation uses unsigned S3 access for public NOAA GOES buckets.
No AWS credentials are required as these buckets are publicly accessible.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from pathlib import Path
import random
import socket
import sys
import time
import traceback
from typing import Any, TypeVar, Union

import aioboto3  # type: ignore
from botocore import UNSIGNED
from botocore.config import Config
import botocore.exceptions

from goesvfi.integrity_check.remote.base import (
    AuthenticationError,
    ConnectionError as RemoteConnectionError,
    RemoteStore,
    RemoteStoreError,
    ResourceNotFoundError,
)
from goesvfi.integrity_check.time_index import (
    SATELLITE_CODES,
    SatellitePattern,
    TimeIndex,
)
from goesvfi.utils.log import get_logger

# Define a type variable for exceptions
ExcType = TypeVar("ExcType", bound=BaseException)

# Define a type variable for the union of all error types
RemoteErrorType = Union[AuthenticationError, ResourceNotFoundError, RemoteConnectionError, RemoteStoreError]

# Define a type for the S3 client
S3ClientType = Any  # aioboto3 doesn't expose concrete types

LOGGER = get_logger(__name__)

# Enable debug logging for boto3/botocore to help diagnose issues
if logging.getLogger().level <= logging.DEBUG:
    # Set up detailed logging for boto3/botocore only when app is in debug mode
    boto_logger = logging.getLogger("boto3")
    boto_logger.setLevel(logging.DEBUG)
    boto_http_logger = logging.getLogger("botocore.hooks")
    boto_http_logger.setLevel(logging.DEBUG)
    # Log HTTP requests and responses
    boto_http_logger = logging.getLogger("botocore.endpoint")
    boto_http_logger.setLevel(logging.DEBUG)
    # Log auth and credentials
    boto_auth_logger = logging.getLogger("botocore.auth")
    boto_auth_logger.setLevel(logging.DEBUG)
    # Log retries and errors
    boto_retry_logger = logging.getLogger("botocore.retryhandler")
    boto_retry_logger.setLevel(logging.DEBUG)

# Define type for download statistics dictionary
DownloadStatsDict = dict[str, int | float | list[float] | list[dict[str, Any]] | list[str] | str]

# Dictionary to track download statistics
DOWNLOAD_STATS: DownloadStatsDict = {
    # Basic counters
    "total_attempts": 0,
    "successful": 0,
    "failed": 0,
    "retry_count": 0,
    # Error type counters
    "not_found": 0,
    "auth_errors": 0,
    "timeouts": 0,
    "network_errors": 0,
    # Performance metrics
    "download_times": [],  # List of download times in seconds
    "download_rates": [],  # List of download rates in bytes per second
    "start_time": time.time(),
    "last_success_time": 0,
    "largest_file_size": 0,
    "smallest_file_size": float("inf"),
    "total_bytes": 0,
    # Recent history
    "errors": [],  # Track the last 20 errors
    "recent_attempts": [],  # Track the last 50 attempts with timestamps
    # Session information
    "session_id": f"{int(time.time())}-{random.randint(1000, 9999)}",
    "hostname": socket.gethostname(),
    "start_timestamp": datetime.now().isoformat(),
}


def _get_safe_int_stat(key: str, default: int = 0) -> int:
    """Safely extract integer stat value."""
    value = DOWNLOAD_STATS.get(key, default)
    return int(value) if isinstance(value, int | float) else default


def _get_safe_float_stat(key: str, default: float = 0.0) -> float:
    """Safely extract float stat value."""
    value = DOWNLOAD_STATS.get(key, default)
    return float(value) if isinstance(value, int | float) else default


def _get_safe_list_stat(key: str) -> list[Any]:
    """Safely extract list stat value."""
    value = DOWNLOAD_STATS.get(key, [])
    return value if isinstance(value, list) else []


def _format_bytes_per_second(speed_bps: float) -> str:
    """Format bytes per second to human readable string."""
    if speed_bps > 1024 * 1024:
        return f"{speed_bps / 1024 / 1024:.2f} MB/s"
    return f"{speed_bps / 1024:.2f} KB/s"


def _calculate_network_speed(download_times_float: list[float], total_bytes: int) -> str:
    """Calculate network speed from download times and bytes."""
    if total_bytes > 0 and download_times_float:
        total_time = sum(download_times_float)
        if total_time > 0:
            speed_bps = total_bytes / total_time
            return _format_bytes_per_second(speed_bps)
    return "N/A"


def _get_download_metrics() -> dict[str, Any]:
    """Extract and calculate download metrics."""
    total_attempts = _get_safe_int_stat("total_attempts")
    successful = _get_safe_int_stat("successful")

    download_times = _get_safe_list_stat("download_times")
    download_times_float = [t for t in download_times if isinstance(t, int | float)]

    avg_time = sum(download_times_float) / len(download_times_float) if download_times_float else 0

    total_bytes = _get_safe_int_stat("total_bytes")
    network_speed = _calculate_network_speed(download_times_float, total_bytes)

    # Calculate average download rate
    avg_download_rate = "N/A"
    download_rates = _get_safe_list_stat("download_rates")
    download_rates_float = [r for r in download_rates if isinstance(r, int | float)]

    if download_rates_float:
        rate_bps = sum(download_rates_float) / len(download_rates_float)
        avg_download_rate = _format_bytes_per_second(rate_bps)

    return {
        "total_attempts": total_attempts,
        "successful": successful,
        "success_rate": ((successful / total_attempts * 100) if total_attempts > 0 else 0),
        "avg_time": avg_time,
        "total_bytes": total_bytes,
        "network_speed": network_speed,
        "avg_download_rate": avg_download_rate,
    }


def _get_error_metrics() -> dict[str, int]:
    """Extract error metrics."""
    return {
        "failed": _get_safe_int_stat("failed"),
        "retry_count": _get_safe_int_stat("retry_count"),
        "not_found": _get_safe_int_stat("not_found"),
        "auth_errors": _get_safe_int_stat("auth_errors"),
        "timeouts": _get_safe_int_stat("timeouts"),
        "network_errors": _get_safe_int_stat("network_errors"),
    }


def _format_recent_errors(errors: list[Any], max_errors: int = 5) -> str:
    """Format recent errors for logging."""
    if not errors:
        return ""

    msg = "\nRecent errors:\n"
    errors_to_show = errors[-max_errors:]
    for i, error in enumerate(errors_to_show):
        if isinstance(error, str):
            msg += f"{i + 1}. {error}\n"
    return msg


def _format_recent_attempts(attempts: list[Any], max_attempts: int = 3) -> str:
    """Format recent download attempts for logging."""
    if not attempts:
        return ""

    msg = "\nRecent download attempts:\n"
    attempts_to_show = attempts[-max_attempts:]

    for i, attempt in enumerate(attempts_to_show):
        if not isinstance(attempt, dict):
            continue

        success_val = attempt.get("success", False)
        status = "✓ Success" if success_val else "✗ Failed"

        file_size_val = attempt.get("file_size", 0)
        if not isinstance(file_size_val, int | float):
            file_size_val = 0
        size = f"{file_size_val / 1024:.1f} KB" if file_size_val > 0 else "N/A"

        download_time_val = attempt.get("download_time", 0)
        if not isinstance(download_time_val, int | float):
            download_time_val = 0
        time_taken = f"{download_time_val:.2f}s" if download_time_val > 0 else "N/A"
        # Format the key for display
        key_val = attempt.get("key", "N/A")
        if key_val != "N/A" and key_val is not None and isinstance(key_val, str) and len(key_val) > 40:
            key_parts = key_val.split("/")
            key_val = f".../{key_parts[-1]}" if key_parts else key_val

        timestamp_val = attempt.get("timestamp", "N/A")
        msg += f"{i + 1}. [{timestamp_val}] {status} - Size: {size}, Time: {time_taken}, Key: {key_val}\n"

    return msg


def log_download_statistics() -> None:
    """Log detailed statistics about S3 downloads."""
    metrics = _get_download_metrics()

    if metrics["total_attempts"] == 0:
        LOGGER.info("No S3 download attempts recorded yet")
        return

    # Get error metrics
    error_metrics = _get_error_metrics()

    # Get runtime info
    start_time = _get_safe_float_stat("start_time", time.time())
    total_time = time.time() - start_time

    # Get file size stats
    largest_file_size = _get_safe_int_stat("largest_file_size")
    smallest_file_size = _get_safe_float_stat("smallest_file_size", float("inf"))

    # Format statistics message
    stats_msg = (
        f"\nS3 Download Statistics:\n"
        f"---------------------\n"
        f"Session ID: {DOWNLOAD_STATS.get('session_id', 'N/A')}\n"
        f"Hostname: {DOWNLOAD_STATS.get('hostname', 'N/A')}\n"
        f"Start time: {DOWNLOAD_STATS.get('start_timestamp', 'N/A')}\n"
        f"\nPerformance Summary:\n"
        f"Total attempts: {metrics['total_attempts']}\n"
        f"Successful: {metrics['successful']} ({metrics['success_rate']:.1f}%)\n"
        f"Failed: {error_metrics['failed']}\n"
        f"Retries: {error_metrics['retry_count']}\n"
        f"Not found errors: {error_metrics['not_found']}\n"
        f"Auth errors: {error_metrics['auth_errors']}\n"
        f"Timeouts: {error_metrics['timeouts']}\n"
        f"Network errors: {error_metrics['network_errors']}\n"
        f"\nDownload Metrics:\n"
        f"Average download time: {metrics['avg_time']:.2f} seconds\n"
        f"Total bytes: {metrics['total_bytes']} bytes\n"
        f"Average network speed: {metrics['network_speed']}\n"
        f"Average download rate: {metrics['avg_download_rate']}\n"
        f"Largest file: {largest_file_size} bytes\n"
        f"Smallest file: {smallest_file_size if smallest_file_size != float('inf') else 'N/A'} bytes\n"
        f"Total runtime: {total_time:.1f} seconds\n"
    )

    # Add recent errors if any
    errors = _get_safe_list_stat("errors")
    stats_msg += _format_recent_errors(errors)

    # Add recent attempts if any
    attempts = _get_safe_list_stat("recent_attempts")
    stats_msg += _format_recent_attempts(attempts)

    # Add time since last successful download
    last_success_time = _get_safe_float_stat("last_success_time")
    if last_success_time > 0:
        time_since_last = time.time() - last_success_time
        stats_msg += f"\nTime since last successful download: {time_since_last:.1f} seconds\n"

    LOGGER.info(stats_msg)


def get_system_network_info() -> dict[str, Any]:
    """Collect system and network information for debugging."""
    from datetime import datetime
    import os
    import platform
    import socket

    info: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "python_version": sys.version,
        "hostname": socket.gethostname(),
    }

    # Try to get network info - this may not work on all platforms
    try:
        # Try to get DNS server info on Unix systems
        dns_servers: list[str] = []
        if os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) > 1:
                            dns_servers.append(parts[1])
        info["dns_servers"] = dns_servers
    except Exception as e:
        info["dns_error"] = str(e)

    # Try a basic network check - can we resolve AWS S3 hostnames?
    try:
        s3_host = "noaa-goes16.s3.amazonaws.com"
        ip_addr = socket.gethostbyname(s3_host)
        resolution_info: dict[str, Any] = {
            "host": s3_host,
            "ip": ip_addr,
            "success": True,
        }
        info["s3_host_resolution"] = resolution_info
    except Exception as e:
        error_info: dict[str, Any] = {
            "host": "s3_host",
            "error": str(e),
            "success": False,
        }
        info["s3_host_resolution"] = error_info

    log_lines = [
        "System and Network Information:",
        f"  Timestamp: {info.get('timestamp', 'N/A')}",
        f"  Platform: {info.get('platform', 'N/A')}",
        f"  Python: {info.get('python_version', 'N/A')}",
        f"  Hostname: {info.get('hostname', 'N/A')}",
    ]

    # Add DNS information
    dns_servers = info.get("dns_servers", [])
    if isinstance(dns_servers, list) and dns_servers:
        log_lines.append(f"  DNS Servers: {', '.join(dns_servers)}")

    # Add S3 host resolution info
    s3_host_resolution = info.get("s3_host_resolution")
    if s3_host_resolution is not None and isinstance(s3_host_resolution, dict):
        if s3_host_resolution.get("success", False):
            host = s3_host_resolution.get("host", "N/A")
            ip = s3_host_resolution.get("ip", "N/A")
            log_lines.append(f"  S3 Host Resolution: {host} -> {ip}")
        else:
            error = s3_host_resolution.get("error", "Unknown error")
            log_lines.append(f"  S3 Host Resolution Failed: {error}")

    # Log full network diagnostics
    LOGGER.info("\n".join(log_lines))

    return info


def create_error_from_code(
    error_code: str | None,
    error_message: str,
    technical_details: str,
    satellite_name: str,
    exception: Exception,
    error_msg: str | None = None,
) -> RemoteErrorType:
    """Create appropriate error object based on error code.

    Args:
        error_code: AWS S3 error code
        error_message: Error message from AWS
        technical_details: Technical details for the error
        satellite_name: Name of satellite being accessed
        exception: Original exception that was caught
        error_msg: Optional custom error message (defaults to generated message)

    Returns:
        Appropriate error type based on the error code
    """
    # Handle case where error_code is None
    if error_code is None:
        # If no error code available, check exception message for clues
        err_str = str(exception).lower()
        if "access denied" in err_str or "403" in err_str:
            return AuthenticationError(
                message=f"Access denied to {satellite_name} data",
                technical_details=technical_details + "Note: NOAA buckets should be publicly accessible.",
                original_exception=exception,
            )
        if "not found" in err_str or "404" in err_str or "no such" in err_str:
            return ResourceNotFoundError(
                message=f"Resource not found for {satellite_name}",
                technical_details=technical_details + "This could mean the bucket or file does not exist.",
                original_exception=exception,
            )
        # Fall through to later checks if no match
    elif error_code in {"AccessDenied", "403", "InvalidAccessKeyId"}:
        return AuthenticationError(
            message=f"Access denied to {satellite_name} data",
            technical_details=technical_details + "Note: NOAA buckets should be publicly accessible.",
            original_exception=exception,
        )
    elif error_code in {"NoSuchBucket", "NoSuchKey", "404"}:
        return ResourceNotFoundError(
            message=f"Resource not found for {satellite_name}",
            technical_details=technical_details + "This could mean the bucket or file does not exist.",
            original_exception=exception,
        )
    elif "timeout" in str(exception).lower() or "connection" in str(exception).lower():
        return RemoteConnectionError(
            message=f"Connection error accessing {satellite_name} data",
            technical_details=technical_details + "This suggests network connectivity issues.",
            original_exception=exception,
        )
    return RemoteStoreError(
        message=error_msg or f"Error accessing {satellite_name} data",
        technical_details=technical_details,
        original_exception=exception,
    )


def format_error_message(error_type: str, error_message: str) -> str:
    """Format error message with a consistent structure.

    Args:
        error_type: The type of error (e.g., 'timeout', 'network')
        error_message: The error message

    Returns:
        A formatted error message with timestamp and type prefix
    """
    timestamp = datetime.now().isoformat()

    # Ensure error_type is not duplicated
    if error_message.startswith(f"{error_type}:"):
        return f"[{timestamp}] {error_message}"
    return f"[{timestamp}] {error_type}: {error_message}"


def update_download_stats(
    success: bool,
    download_time: float = 0,
    file_size: int = 0,
    error_type: str | None = None,
    error_message: str | None = None,
    satellite: str | None = None,
    bucket: str | None = None,
    key: str | None = None,
) -> None:
    """Update download statistics.

    Args:
        success: Whether the download was successful
        download_time: Time taken for the download in seconds
        file_size: Size of the downloaded file in bytes
        error_type: Type of error if download failed
        error_message: Error message if download failed
        satellite: Satellite name for additional tracking
        bucket: S3 bucket name for additional tracking
        key: S3 key for additional tracking
    """
    # Create attempt record with timestamp
    timestamp = datetime.now().isoformat()
    attempt_record: dict[str, Any] = {
        "timestamp": timestamp,
        "success": success,
        "download_time": download_time,
        "file_size": file_size,
        "error_type": error_type,
        "satellite": satellite,
        "bucket": bucket,
        "key": key,
    }

    # Safely get and update recent attempts (limited to 50)
    recent_attempts_value = DOWNLOAD_STATS.get("recent_attempts", [])
    if not isinstance(recent_attempts_value, list):
        recent_attempts_list: list[dict[str, Any]] = []
    else:
        # Make sure we have the right type - list of dicts
        recent_attempts_list = []
        for item in recent_attempts_value:
            if isinstance(item, dict):
                recent_attempts_list.append(item)

    if len(recent_attempts_list) >= 50:
        recent_attempts_list.pop(0)  # Remove oldest
    recent_attempts_list.append(attempt_record)
    DOWNLOAD_STATS["recent_attempts"] = recent_attempts_list

    # Safely update total attempts counter
    total_attempts = (
        int(DOWNLOAD_STATS["total_attempts"]) if isinstance(DOWNLOAD_STATS["total_attempts"], int | float) else 0
    )
    DOWNLOAD_STATS["total_attempts"] = total_attempts + 1

    if success:
        # Safely update successful counter
        successful = int(DOWNLOAD_STATS["successful"]) if isinstance(DOWNLOAD_STATS["successful"], int | float) else 0
        DOWNLOAD_STATS["successful"] = successful + 1

        # Safely update download times list
        download_times_value = DOWNLOAD_STATS.get("download_times", [])
        if not isinstance(download_times_value, list):
            download_times_list: list[float] = []
        else:
            # Make sure we have the right type - list of floats
            download_times_list = []
            for item in download_times_value:
                if isinstance(item, int | float):
                    download_times_list.append(float(item))

        download_times_list.append(download_time)
        DOWNLOAD_STATS["download_times"] = download_times_list

        # Set last success time
        DOWNLOAD_STATS["last_success_time"] = time.time()

        # Safely update total bytes counter
        total_bytes = (
            int(DOWNLOAD_STATS["total_bytes"]) if isinstance(DOWNLOAD_STATS["total_bytes"], int | float) else 0
        )
        DOWNLOAD_STATS["total_bytes"] = total_bytes + file_size

        # Calculate and store download rate if time is non-zero
        if download_time > 0 and file_size > 0:
            download_rate = file_size / download_time  # bytes per second

            # Safely get and update download rates list
            download_rates_value = DOWNLOAD_STATS.get("download_rates", [])
            if not isinstance(download_rates_value, list):
                download_rates_list: list[float] = []
            else:
                # Make sure we have the right type - list of floats
                download_rates_list = []
                for item in download_rates_value:
                    if isinstance(item, int | float):
                        download_rates_list.append(float(item))

            download_rates_list.append(download_rate)

            # Limit history to prevent memory growth
            if len(download_rates_list) > 100:
                download_rates_list = download_rates_list[-100:]
            DOWNLOAD_STATS["download_rates"] = download_rates_list

        # Track file size statistics
        largest_file_size = (
            int(DOWNLOAD_STATS["largest_file_size"])
            if isinstance(DOWNLOAD_STATS["largest_file_size"], int | float)
            else 0
        )
        if file_size > largest_file_size:
            DOWNLOAD_STATS["largest_file_size"] = file_size

        smallest_file_size = (
            float(DOWNLOAD_STATS["smallest_file_size"])
            if isinstance(DOWNLOAD_STATS["smallest_file_size"], int | float)
            else float("inf")
        )
        if file_size < smallest_file_size:
            DOWNLOAD_STATS["smallest_file_size"] = file_size
    else:
        # Safely update failed counter
        failed = int(DOWNLOAD_STATS["failed"]) if isinstance(DOWNLOAD_STATS["failed"], int | float) else 0
        DOWNLOAD_STATS["failed"] = failed + 1

        if error_type:
            if error_type == "not_found":
                not_found = (
                    int(DOWNLOAD_STATS["not_found"]) if isinstance(DOWNLOAD_STATS["not_found"], int | float) else 0
                )
                DOWNLOAD_STATS["not_found"] = not_found + 1
            elif error_type == "auth":
                auth_errors = (
                    int(DOWNLOAD_STATS["auth_errors"]) if isinstance(DOWNLOAD_STATS["auth_errors"], int | float) else 0
                )
                DOWNLOAD_STATS["auth_errors"] = auth_errors + 1
            elif error_type == "timeout":
                timeouts = int(DOWNLOAD_STATS["timeouts"]) if isinstance(DOWNLOAD_STATS["timeouts"], int | float) else 0
                DOWNLOAD_STATS["timeouts"] = timeouts + 1
            elif error_type == "network":
                network_errors = (
                    int(DOWNLOAD_STATS["network_errors"])
                    if isinstance(DOWNLOAD_STATS["network_errors"], int | float)
                    else 0
                )
                DOWNLOAD_STATS["network_errors"] = network_errors + 1

        if error_message:
            # Format error message consistently
            formatted_error = format_error_message(error_type or "unknown", error_message)

            # Safely get and update errors list
            errors_value = DOWNLOAD_STATS.get("errors", [])
            if not isinstance(errors_value, list):
                errors_list: list[str] = []
            else:
                # Make sure we have the right type - list of strings
                errors_list = []
                for item in errors_value:
                    if isinstance(item, str):
                        errors_list.append(item)

            if len(errors_list) >= 20:
                errors_list.pop(0)  # Remove oldest error
            errors_list.append(formatted_error)
            DOWNLOAD_STATS["errors"] = errors_list

        # On failures, periodically collect network diagnostics
        # Every 5 failures, get network info to help diagnose issues
        if failed % 5 == 0:
            get_system_network_info()

    # Log statistics every 10 downloads
    if total_attempts % 10 == 0:
        log_download_statistics()


class S3Store(RemoteStore):
    """Store implementation for AWS S3 buckets containing GOES data.

    This implementation is specifically designed for accessing public NOAA GOES
    satellite data stored in AWS S3 buckets. It uses unsigned S3 access, so
    no AWS credentials are required.
    """

    def __init__(
        self,
        aws_profile: str | None = None,
        aws_region: str = "us-east-1",
        timeout: int = 60,
    ) -> None:
        """Initialize with optional AWS profile and timeout parameters.

        Note: AWS credentials are NOT required as this implementation uses
        unsigned S3 access for public NOAA GOES buckets.

        Args:
            aws_profile: AWS profile name to use (optional, not required for NOAA buckets)
            aws_region: AWS region name (defaults to us-east-1 where NOAA buckets are located)
            timeout: Operation timeout in seconds
        """
        self.aws_profile: str | None = aws_profile
        self.aws_region: str = aws_region
        self.timeout: int = timeout
        self._session: Any | None = None
        self._s3_client: S3ClientType | None = None

        # Log diagnostic information at startup
        LOGGER.info("Initializing S3Store: region=%s, timeout=%ss", aws_region, timeout)

        # Reset download statistics - useful if multiple S3Store instances are created
        global DOWNLOAD_STATS
        DOWNLOAD_STATS = {
            # Basic counters
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "retry_count": 0,
            # Error type counters
            "not_found": 0,
            "auth_errors": 0,
            "timeouts": 0,
            "network_errors": 0,
            # Performance metrics
            "download_times": [],
            "download_rates": [],  # Bytes per second
            "start_time": time.time(),
            "last_success_time": 0,
            "largest_file_size": 0,
            "smallest_file_size": float("inf"),
            "total_bytes": 0,
            # Recent history
            "errors": [],  # Track the last 20 errors
            "recent_attempts": [],  # Track the last 50 attempts with timestamps
            # Session information
            "session_id": f"{int(time.time())}-{random.randint(1000, 9999)}",
            "hostname": socket.gethostname(),
            "start_timestamp": datetime.now().isoformat(),
        }

        # Get and log system/network info at startup
        try:
            LOGGER.info("Collecting system and network diagnostics during S3Store initialization")
            get_system_network_info()
        except Exception:
            LOGGER.exception("Error collecting system diagnostics")

        # Check connectivity to AWS S3 NOAA buckets
        LOGGER.info("Testing connectivity to AWS S3 NOAA buckets...")
        try:
            hosts_to_check = [
                "noaa-goes16.s3.amazonaws.com",
                "noaa-goes18.s3.amazonaws.com",
                "s3.amazonaws.com",
            ]

            for host in hosts_to_check:
                try:
                    ip_addr = socket.gethostbyname(host)
                    LOGGER.info("✓ Successfully resolved %s to %s", host, ip_addr)
                except Exception:
                    LOGGER.exception("✗ Failed to resolve %s", host)
        except Exception:
            LOGGER.exception("Error testing connectivity")

    @property
    def session_kwargs(self) -> dict[str, Any]:
        """Get boto3 session keyword arguments."""
        kwargs = {"region_name": self.aws_region}
        if self.aws_profile:
            kwargs["profile_name"] = self.aws_profile
        return kwargs

    async def _get_s3_client(self) -> S3ClientType:
        """Get or create an S3 client with improved timeout handling and exponential backoff.

        Uses unsigned S3 access for public NOAA GOES buckets.
        No AWS credentials are required as these buckets allow public access.

        Returns:
            An S3 client instance with unsigned access configuration

        Raises:
            RemoteStoreError: If the client creation fails
            ConnectionError: If connection timeouts occur
            AuthenticationError: If authentication issues occur (unlikely with unsigned access)
        """
        retry_count = 0
        max_retries = 3

        # Safely set retry count for reporting
        retry_count_value = (
            int(DOWNLOAD_STATS["retry_count"]) if isinstance(DOWNLOAD_STATS["retry_count"], int | float) else 0
        )
        DOWNLOAD_STATS["retry_count"] = 0

        while retry_count < max_retries:
            try:
                # Calculate exponential backoff delay (except on first attempt)
                delay = 0
                if retry_count > 0:
                    # Exponential backoff with jitter: 2^retry_count * (0.75 to 1.25)
                    # First retry: ~2s delay, second retry: ~4s delay
                    jitter = 0.75 + (0.5 * random.random())  # Random value between 0.75 and 1.25
                    delay = (2**retry_count) * jitter

                if self._s3_client is None:
                    LOGGER.debug(
                        "Creating new S3 client with unsigned access (attempt %s/%s, region: %s, delay: %.2fs)",
                        retry_count + 1,
                        max_retries,
                        self.aws_region,
                        delay,
                    )

                    # Apply delay for retries using exponential backoff
                    if delay > 0:
                        LOGGER.info(
                            "Applying exponential backoff delay of %.2fs before retry %s", delay, retry_count + 1
                        )
                        await asyncio.sleep(delay)

                    # Create config with UNSIGNED signature and explicit timeouts
                    s3_config = Config(
                        signature_version=UNSIGNED,
                        connect_timeout=10,  # 10 seconds for connection
                        read_timeout=self.timeout,
                        retries={"max_attempts": 2},
                    )
                    LOGGER.debug(
                        "Created config with UNSIGNED signature version and timeouts (connect: 10s, read: %ss)",
                        self.timeout,
                    )

                    # First, create the Session
                    session = aioboto3.Session(**self.session_kwargs)
                    LOGGER.debug("Created aioboto3 Session with kwargs: %s", self.session_kwargs)

                    # Create client with the session and config, with overall timeout
                    try:
                        client_context = session.client("s3", config=s3_config)
                        LOGGER.debug("Got client context from session.client()")

                        # Use asyncio.wait_for to add an overall timeout
                        try:
                            # Increase timeout for retries to reduce false negatives
                            client_timeout = 15 * (1 + retry_count * 0.5)  # 15s, 22.5s, 30s

                            LOGGER.debug(
                                "Attempting to create S3 client with timeout %.1fs",
                                client_timeout,
                            )
                            self._s3_client = await asyncio.wait_for(
                                client_context.__aenter__(), timeout=client_timeout
                            )
                            LOGGER.debug(
                                "Entered client context, got S3 client: %s",
                                self._s3_client,
                            )
                        except TimeoutError:
                            retry_count += 1
                            # Safely update retry counter
                            retry_count_value = (
                                int(DOWNLOAD_STATS["retry_count"])
                                if isinstance(DOWNLOAD_STATS["retry_count"], int | float)
                                else 0
                            )
                            DOWNLOAD_STATS["retry_count"] = retry_count_value + 1

                            LOGGER.warning(
                                "Timeout creating S3 client, attempt %s/%s",
                                retry_count,
                                max_retries,
                            )
                            if retry_count >= max_retries:
                                error_msg = (
                                    "Connection to AWS S3 timed out. "
                                    "Please check your internet connection and try again."
                                )
                                technical_details = (
                                    f"Client creation timed out after {retry_count} attempts with "
                                    f"increasing timeouts (15s, 22.5s, 30s)."
                                )

                                # Add network diagnostics to help troubleshoot
                                get_system_network_info()

                                raise RemoteConnectionError(
                                    message=error_msg,
                                    technical_details=technical_details,
                                    error_code="CONN-TIMEOUT",
                                )
                            continue

                        if self._s3_client is None:
                            raise RemoteStoreError(
                                message="Failed to create S3 client - received None",
                                technical_details="The S3 client creation succeeded but returned None",
                                error_code="CLIENT-NONE",
                            )

                        LOGGER.debug("Successfully created S3 client with unsigned access configuration")
                    except TimeoutError:
                        # This is handled above
                        continue
                    except Exception as e:
                        LOGGER.exception("Error creating S3 client")
                        if "NoCredentialsError" in str(e) or "AccessDenied" in str(e):
                            # This shouldn't happen with UNSIGNED access
                            raise AuthenticationError(
                                message="Could not access S3 with unsigned access configuration",
                                technical_details=f"Error creating S3 client despite using unsigned access: {e}",
                                original_exception=e,
                                error_code="AUTH-001",
                            )
                        if "endpoint" in str(e).lower() or "connect" in str(e).lower() or "timeout" in str(e).lower():
                            retry_count += 1
                            # Safely update retry counter
                            retry_count_value = (
                                int(DOWNLOAD_STATS["retry_count"])
                                if isinstance(DOWNLOAD_STATS["retry_count"], int | float)
                                else 0
                            )
                            DOWNLOAD_STATS["retry_count"] = retry_count_value + 1

                            LOGGER.warning(
                                "Connection error creating S3 client, attempt %s/%s",
                                retry_count,
                                max_retries,
                            )
                            if retry_count >= max_retries:
                                # Add network diagnostics to help troubleshoot
                                get_system_network_info()

                                raise RemoteConnectionError(
                                    message="Could not connect to AWS S3 service - check your internet connection",
                                    technical_details=(
                                        f"Connection error after {retry_count} attempts with exponential backoff: {e}"
                                    ),
                                    original_exception=e,
                                    error_code="CONN-FAILED",
                                )
                            continue
                        raise RemoteStoreError(
                            message=f"Failed to create S3 client: {e}",
                            technical_details=f"Unexpected error creating S3 client: {e}",
                            original_exception=e,
                            error_code="CLIENT-ERROR",
                        )

                return self._s3_client
            except (RemoteStoreError, AuthenticationError, RemoteConnectionError):
                # Re-raise our custom exceptions without wrapping
                raise
            except TimeoutError:
                # This is handled in the retry loop
                continue
            except Exception as e:
                LOGGER.exception("Unexpected error in _get_s3_client")
                import traceback

                LOGGER.exception(traceback.format_exc())

                # Add network diagnostics to help troubleshoot
                get_system_network_info()

                # Wrap in RemoteStoreError
                raise RemoteStoreError(
                    message="Unexpected error setting up S3 access",
                    technical_details=f"Unexpected error in _get_s3_client: {e}",
                    original_exception=e,
                    error_code="INIT-ERROR",
                )
        return None

    async def close(self) -> None:
        """Close the S3 client."""
        if self._s3_client is not None:
            await self._s3_client.__aexit__(None, None, None)
            self._s3_client = None

    async def __aenter__(self) -> "S3Store":
        """Context manager entry."""
        await self._get_s3_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[ExcType] | None,
        exc_val: ExcType | None,
        exc_tb: Any | None,
    ) -> None:
        """Context manager exit."""
        await self.close()

    def _get_bucket_and_key(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
        exact_match: bool = False,
    ) -> tuple[str, str]:
        """Get the S3 bucket and key for the given timestamp and satellite.

        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
            band: Band number (1-16, default 13 for Clean IR)
            exact_match: If True, return a concrete filename without wildcards

        Returns:
            Tuple of (bucket_name, object_key)
        """
        bucket = TimeIndex.S3_BUCKETS[satellite]
        key = TimeIndex.to_s3_key(ts, satellite, product_type=product_type, band=band, exact_match=exact_match)
        return bucket, key

    async def exists(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        product_type: str = "RadC",
        band: int = 13,
    ) -> bool:
        """Check if a file exists in S3 for the timestamp and satellite.

        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
            band: Band number (1-16, default 13 for Clean IR)

        Returns:
            True if the file exists, False otherwise

        Raises:
            RemoteStoreError: If an error occurs during the check (except for 404 Not Found)
        """
        # Use exact_match=True for head_object operations
        bucket, key = self._get_bucket_and_key(ts, satellite, product_type=product_type, band=band, exact_match=True)
        s3 = await self._get_s3_client()

        try:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                LOGGER.debug("S3 object not found: s3://%s/%s", bucket, key)
                return False

            # Handle other errors with user-friendly messages
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", "Unknown error")

            # Create enhanced error with detailed context
            error_msg = f"Error checking if file exists for {satellite.name} at {ts.isoformat()}"
            technical_details = f"S3 {error_code}: {error_message}\nPath: s3://{bucket}/{key}"

            # Create error object using helper function
            error = create_error_from_code(
                error_code=error_code if error_code is not None else "UnknownError",
                error_message=error_message,
                technical_details=technical_details,
                satellite_name=satellite.name,
                exception=e,
                error_msg=error_msg,
            )

            # Log the error details
            LOGGER.exception("S3 error: %s", error.get_user_message())
            if hasattr(error, "technical_details") and error.technical_details:
                LOGGER.exception("S3 technical details: %s", error.technical_details)

            # For credential or connection errors, we should raise to notify the user
            if isinstance(error, AuthenticationError | ConnectionError):
                raise error

            # For other errors, log and return False
            LOGGER.debug("S3 check failed for s3://%s/%s: %s", bucket, key, e)
            return False

    async def _check_exact_file_exists(
        self,
        s3: S3ClientType,
        bucket: str,
        key: str,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> bool:
        """Check if an exact file exists in S3.

        Args:
            s3: S3 client
            bucket: S3 bucket name
            key: S3 object key
            ts: Timestamp for logging
            satellite: Satellite pattern for logging

        Returns:
            True if file exists, False otherwise

        Raises:
            Various S3 errors converted to appropriate RemoteStoreError subclasses
        """
        try:
            LOGGER.debug("Checking if exact file exists: s3://%s/%s", bucket, key)
            await s3.head_object(Bucket=bucket, Key=key)
            LOGGER.info("Found exact match for file: s3://%s/%s", bucket, key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                LOGGER.info("Exact file not found (404), will try wildcard pattern")
                error_message = e.response.get("Error", {}).get("Message", "Unknown error")
                LOGGER.debug("S3 404 details: %s", error_message)
                return False
            # Handle other errors
            LOGGER.exception("S3 error during head_object check: %s", error_code)
            error_message = e.response.get("Error", {}).get("Message", "Unknown error")
            LOGGER.exception("S3 error message: %s", error_message)

            # Create enhanced error with detailed context
            error_msg = f"Error checking if file exists for {satellite.name} at {ts.isoformat()}"
            technical_details = (
                f"S3 {error_code}: {error_message}\n"
                f"Path: s3://{bucket}/{key}\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
            )

            error = create_error_from_code(
                error_code=error_code if error_code is not None else "UnknownError",
                error_message=error_message,
                technical_details=technical_details,
                satellite_name=satellite.name,
                exception=e,
                error_msg=error_msg,
            )

            LOGGER.exception("S3 error: %s", error.get_user_message())
            LOGGER.exception("S3 technical details: %s", error.technical_details)
            raise error

    async def _download_exact_file(
        self,
        s3: S3ClientType,
        bucket: str,
        key: str,
        dest_path: Path,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> Path:
        """Download an exact file from S3.

        Args:
            s3: S3 client
            bucket: S3 bucket name
            key: S3 object key
            dest_path: Destination path
            ts: Timestamp for logging
            satellite: Satellite pattern for logging

        Returns:
            Path to downloaded file

        Raises:
            Various S3 errors converted to appropriate RemoteStoreError subclasses
        """
        # Create parent directory if it doesn't exist
        LOGGER.debug("Creating parent directory: %s", dest_path.parent)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the file with timing
        LOGGER.info("Downloading s3://%s/%s to %s", bucket, key, dest_path)
        download_start = time.time()
        download_success = False
        file_size = 0

        try:
            # Log system info and network state at download time
            LOGGER.debug("System info: Python %s, Platform: %s", sys.version, sys.platform)
            LOGGER.debug("Download starting at %s", datetime.now().isoformat())

            # Start download with timing
            await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))
            download_time = time.time() - download_start

            LOGGER.info("Download complete: %s in %.2f seconds", dest_path, download_time)

            # Verify the downloaded file and capture size
            if dest_path.exists():
                file_size = dest_path.stat().st_size
                download_speed = file_size / download_time if download_time > 0 else 0

                # Format download speed in appropriate units
                speed_str = ""
                if download_speed > 1024 * 1024:
                    speed_str = f"{download_speed / 1024 / 1024:.2f} MB/s"
                else:
                    speed_str = f"{download_speed / 1024:.2f} KB/s"

                LOGGER.info("Verified downloaded file: %s", dest_path)
                LOGGER.info(
                    "File details: Size: %s bytes, Download time: %.2fs, Speed: %s", file_size, download_time, speed_str
                )
                download_success = True
            else:
                LOGGER.error("File download completed but file doesn't exist at %s", dest_path)

            # Update download statistics
            update_download_stats(
                success=download_success,
                download_time=download_time,
                file_size=file_size,
            )

            # If this is a significant milestone (every 50 successful downloads), log full stats
            successful_count = (
                int(DOWNLOAD_STATS["successful"]) if isinstance(DOWNLOAD_STATS["successful"], int | float) else 0
            )
            if download_success and successful_count % 50 == 0:
                log_download_statistics()

            return dest_path

        except Exception as download_error:
            # Calculate download time even for failures
            download_time = time.time() - download_start

            # Enhanced error logging for download failures
            LOGGER.exception("Failed to download file after %.2fs", download_time)
            LOGGER.exception("Download exception type: %s", type(download_error).__name__)
            LOGGER.exception("Download path: s3://%s/%s", bucket, key)
            LOGGER.exception("Destination: %s", dest_path)

            # Log the traceback for more detailed debugging
            LOGGER.exception("Traceback: %s", traceback.format_exc())

            # Convert to appropriate error type and raise
            error = self._convert_download_error(download_error, bucket, key, dest_path, ts, satellite, download_time)
            raise error

    def _convert_download_error(
        self,
        download_error: Exception,
        bucket: str,
        key: str,
        dest_path: Path,
        ts: datetime,
        satellite: SatellitePattern,
        download_time: float,
    ) -> RemoteStoreError:
        """Convert a download exception to appropriate RemoteStoreError subclass.

        Args:
            download_error: The original exception
            bucket: S3 bucket name
            key: S3 object key
            dest_path: Destination path
            ts: Timestamp
            satellite: Satellite pattern
            download_time: Time taken for download attempt

        Returns:
            Appropriate RemoteStoreError subclass
        """
        error_type = None
        error_message = str(download_error)

        if isinstance(download_error, botocore.exceptions.ClientError):
            error_code = download_error.response.get("Error", {}).get("Code")
            error_message = download_error.response.get("Error", {}).get("Message", "Unknown error")
            LOGGER.error("S3 error code: %s, message: %s", error_code, error_message)

            # Create detailed error object to be returned to user
            technical_details = (
                f"S3 {error_code}: {error_message}\n"
                f"Path: s3://{bucket}/{key}\n"
                f"Destination: {dest_path}\n"
                f"Download time: {download_time:.2f}s\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
            )

            # Determine error type for statistics tracking
            if error_code in {"AccessDenied", "403"}:
                error_type = "auth"
            elif error_code in {"NoSuchKey", "404"}:
                error_type = "not_found"
            else:
                error_type = "network"

            # Create error object using helper function
            custom_msg = (
                f"File for {satellite.name} at {ts.isoformat()} disappeared during download"
                if error_code in {"NoSuchKey", "404"}
                else None
            )
            error = create_error_from_code(
                error_code=error_code,
                error_message=error_message,
                technical_details=technical_details,
                satellite_name=satellite.name,
                exception=download_error,
                error_msg=custom_msg,
            )
        elif isinstance(download_error, PermissionError):
            error_type = "auth"
            technical_details = (
                f"Permission denied while downloading: s3://{bucket}/{key}\n"
                f"Destination: {dest_path}\n"
                f"Download time: {download_time:.2f}s\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
                f"Check file system permissions at the destination.\n"
            )
            error = AuthenticationError(
                message=f"Permission error downloading {satellite.name} data",
                technical_details=technical_details,
                original_exception=download_error,
            )
        elif (
            isinstance(download_error, asyncio.TimeoutError | TimeoutError) or "timeout" in str(download_error).lower()
        ):
            error_type = "timeout"
            technical_details = (
                f"Timeout while downloading: s3://{bucket}/{key}\n"
                f"Destination: {dest_path}\n"
                f"Download time: {download_time:.2f}s\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
                f"Check your internet connection speed and stability.\n"
            )
            error = RemoteConnectionError(
                message=f"Timeout downloading {satellite.name} data",
                technical_details=technical_details,
                original_exception=download_error,
            )
        else:
            # Generic error for unexpected exceptions
            error_type = "network"
            technical_details = (
                f"Error: {download_error!s}\n"
                f"Path: s3://{bucket}/{key}\n"
                f"Destination: {dest_path}\n"
                f"Download time: {download_time:.2f}s\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
                f"Check your internet connection and try again.\n"
            )
            error = RemoteStoreError(
                message=f"Failed to download {satellite.name} data",
                technical_details=technical_details,
                original_exception=download_error,
            )

        # Update error statistics
        update_download_stats(success=False, error_type=error_type)

        # Log user-friendly message
        LOGGER.error("Download error: %s", error.get_user_message())
        LOGGER.error("Technical details: %s", error.technical_details)

        return error

    async def _find_best_match_with_wildcard(
        self,
        s3: S3ClientType,
        bucket: str,
        wildcard_key: str,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> str:
        """Find the best matching object using wildcard search.

        Args:
            s3: S3 client
            bucket: S3 bucket name
            wildcard_key: S3 key pattern with wildcards
            ts: Timestamp for matching
            satellite: Satellite pattern for matching

        Returns:
            Best matching S3 key

        Raises:
            ResourceNotFoundError: If no matching files found
        """
        LOGGER.info("Trying wildcard match: s3://%s/%s", bucket, wildcard_key)

        # Extract the prefix from the wildcard key
        prefix = wildcard_key.split("*")[0] if "*" in wildcard_key else wildcard_key

        LOGGER.info("Searching with prefix s3://%s/%s", bucket, prefix)

        # List objects with the prefix
        paginator = s3.get_paginator("list_objects_v2")
        matching_objects = []

        # Get the base path from the wildcard key
        base_path = "/".join(wildcard_key.split("/")[:-1]) + "/"

        # Extract exact components from the wildcard pattern
        sat_code = f"_{SATELLITE_CODES.get(satellite)}_"
        year = ts.year
        doy = ts.strftime("%j")
        hour = ts.strftime("%H")
        minute = ts.strftime("%M")
        timestamp_part = f"s{year}{doy}{hour}{minute}"

        # Log search parameters for debugging
        LOGGER.info(
            "Search parameters: base_path=%s, sat_code=%s, timestamp_part=%s", base_path, sat_code, timestamp_part
        )

        # Generate regex pattern to match the wildcard key
        import re

        filename_pattern = wildcard_key.split("/")[-1]
        regex_pattern = filename_pattern.replace("*", ".*")
        compiled_pattern = re.compile(regex_pattern)

        LOGGER.debug("Using regex pattern: %s", regex_pattern)

        # Track how many pages we've examined
        page_count = 0
        total_objects = 0

        async for page in paginator.paginate(Bucket=bucket, Prefix=base_path):
            page_count += 1

            if "Contents" not in page:
                LOGGER.info("Page %s: No Contents found", page_count)
                continue

            objects_in_page = len(page["Contents"])
            total_objects += objects_in_page
            LOGGER.info("Page %s: Found %s objects", page_count, objects_in_page)

            # Log a sample of keys for debugging
            if objects_in_page > 0 and page_count == 1:
                sample_keys = [obj["Key"] for obj in page["Contents"][:5]]
                LOGGER.debug("Sample keys from first page: %s", sample_keys)

            for obj in page["Contents"]:
                key = obj["Key"]
                # Only consider keys that match the timestamp and satellite
                if sat_code in key and timestamp_part in key and compiled_pattern.search(key):
                    matching_objects.append(key)

        LOGGER.info(
            "Search complete: Examined %s pages with %s total objects",
            page_count,
            total_objects,
        )
        LOGGER.info("Found %s matching objects", len(matching_objects))

        if not matching_objects:
            # Detailed error message with search parameters
            error_msg = f"No files found for {satellite.name} at {ts.isoformat()}"
            technical_details = (
                f"No files found matching: s3://{bucket}/{wildcard_key}\n"
                f"Search parameters:\n"
                f"  Prefix: {base_path}\n"
                f"  Satellite code: {sat_code}\n"
                f"  Timestamp part: {timestamp_part}\n"
                f"  Regex pattern: {regex_pattern}\n"
                f"  Pages examined: {page_count}\n"
                f"  Total objects: {total_objects}\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
                f"This data may not be available in the AWS S3 bucket. "
                f"Try a different timestamp or check the NOAA archives."
            )

            LOGGER.error(error_msg)
            LOGGER.error(technical_details)

            error = ResourceNotFoundError(
                message=error_msg,
                technical_details=technical_details,
                original_exception=FileNotFoundError("No matching files found in S3"),
            )
            raise error

        # Sort matching objects to get the most recent one
        matching_objects.sort()
        best_match_key = matching_objects[-1]

        LOGGER.info("Selected best match: s3://%s/%s", bucket, best_match_key)
        return str(best_match_key)

    async def download(
        self,
        ts: datetime,
        satellite: SatellitePattern,
        dest_path: Path,
        product_type: str = "RadC",
        band: int = 13,
    ) -> Path:
        """Download a file from S3.

        If the key contains wildcards, it will list matching objects and download the most recent one.
        Uses unsigned S3 access for public NOAA GOES buckets.

        Args:
            ts: Timestamp to download
            satellite: Satellite pattern enum
            dest_path: Destination path to save the file
            product_type: Product type ("RadF" for Full Disk, "RadC" for CONUS, "RadM" for Mesoscale)
            band: Band number (1-16, default 13 for Clean IR)

        Returns:
            Path to the downloaded file

        Raises:
            ResourceNotFoundError: If the file doesn't exist
            AuthenticationError: If there are AWS credential issues
            ConnectionError: If there are network connectivity issues
            RemoteStoreError: For other S3 errors
        """
        # Check if we should use exact match or wildcard
        bucket, key = self._get_bucket_and_key(ts, satellite, product_type=product_type, band=band, exact_match=True)
        s3 = await self._get_s3_client()

        # Enhanced logging for the download attempt
        LOGGER.info(
            "Attempting to download S3 file for %s at %s",
            satellite.name,
            ts.isoformat(),
        )
        LOGGER.info("Target S3 path: s3://%s/%s", bucket, key)
        LOGGER.info("Local destination: %s", dest_path)

        # Log timestamp information for debugging
        LOGGER.debug(
            "Timestamp details - ISO: %s, Year: %s, Day of Year: %s, HHMMSS: %s",
            ts.isoformat(),
            ts.year,
            ts.strftime("%j"),
            ts.strftime("%H%M%S"),
        )

        # Check if exact file exists first
        try:
            has_exact_match = await self._check_exact_file_exists(s3, bucket, key, ts, satellite)

            # If we have an exact match, download it directly
            if has_exact_match:
                return await self._download_exact_file(s3, bucket, key, dest_path, ts, satellite)
            # Try wildcard match
            bucket, wildcard_key = self._get_bucket_and_key(
                ts,
                satellite,
                exact_match=False,
                product_type=product_type,
                band=band,
            )

            # Find best match with wildcard
            best_match_key = await self._find_best_match_with_wildcard(s3, bucket, wildcard_key, ts, satellite)

            # Download the best match
            return await self._download_exact_file(s3, bucket, best_match_key, dest_path, ts, satellite)
        except botocore.exceptions.ClientError as e:
            # Enhanced logging for S3 client errors
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", "Unknown error")

            LOGGER.exception("S3 client error during download: %s - %s", error_code, error_message)
            LOGGER.exception("Path: s3://%s/%s", bucket, key)

            # Create a detailed error with context
            technical_details = (
                f"S3 {error_code}: {error_message}\n"
                f"Path: s3://{bucket}/{key}\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
            )

            # Create error object using helper function
            client_error = create_error_from_code(
                error_code=error_code,
                error_message=error_message,
                technical_details=technical_details,
                satellite_name=satellite.name,
                exception=e,
                error_msg=(
                    f"File not found for {satellite.name} at {ts.isoformat()}"
                    if error_code in {"NoSuchBucket", "NoSuchKey", "404"}
                    else (
                        f"Timeout accessing {satellite.name} data" if "timeout" in str(e).lower() else None
                    )  # Use default message
                ),
            )

            # Log and raise the error
            LOGGER.exception("S3 client error: %s", client_error.get_user_message())
            if client_error.technical_details:
                LOGGER.exception("Technical details: %s", client_error.technical_details)

            raise client_error
        except ResourceNotFoundError:
            LOGGER.exception("Resource not found error re-raised for: s3://%s/%s", bucket, key)
            raise  # Re-raise ResourceNotFoundError
        except (AuthenticationError, RemoteConnectionError, RemoteStoreError):
            LOGGER.exception("Custom error re-raised for: s3://%s/%s", bucket, key)
            raise  # Re-raise our custom errors
        except Exception as e:
            # Enhanced logging for unexpected errors
            LOGGER.exception("Unexpected error during download")
            LOGGER.exception("Exception type: %s", type(e).__name__)
            LOGGER.exception("Path: s3://%s/%s", bucket, key)

            # Create a detailed error with context
            technical_details = (
                f"Error: {e!s}\n"
                f"Path: s3://{bucket}/{key}\n"
                f"Destination: {dest_path}\n"
                f"Timestamp details: Year={ts.year}, DOY={ts.strftime('%j')}, "
                f"Hour={ts.strftime('%H')}, Minute={ts.strftime('%M')}\n"
            )

            # Determine error type based on error string
            error_code = (
                "timeout"
                if "timeout" in str(e).lower()
                else (
                    "access"
                    if "permission" in str(e).lower() or "access" in str(e).lower()
                    else ("disk" if "disk" in str(e).lower() or "space" in str(e).lower() else "unknown")
                )
            )

            # Create error object with the appropriate message
            final_error: RemoteErrorType = RemoteStoreError(
                message=f"An unknown error occurred while downloading the {satellite.name} data",
                technical_details=technical_details,
                original_exception=e,
                error_code="UNKNOWN-ERROR",
            )

            if error_code == "timeout":
                final_error = RemoteConnectionError(
                    message=f"Timeout downloading {satellite.name} data",
                    technical_details=technical_details + "Check your internet connection speed and stability.",
                    original_exception=e,
                )
            elif error_code == "access":
                final_error = AuthenticationError(
                    message=f"Permission error downloading {satellite.name} data",
                    technical_details=technical_details + "Check file system permissions at the destination.",
                    original_exception=e,
                )
            elif error_code == "disk":
                final_error = RemoteStoreError(
                    message=f"Disk error downloading {satellite.name} data",
                    technical_details=technical_details + "Check available disk space at the destination.",
                    original_exception=e,
                )
            else:
                final_error = RemoteStoreError(
                    message=f"Unexpected error downloading {satellite.name} data",
                    technical_details=technical_details,
                    original_exception=e,
                )

            # Log and raise the error
            LOGGER.exception("Download error: %s", final_error.get_user_message())
            if final_error.technical_details:
                LOGGER.exception("Technical details: %s", final_error.technical_details)

            raise final_error

    async def check_file_exists(self, timestamp: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists for the given timestamp and satellite.

        This method implements the abstract method from RemoteStore.
        """
        return await self.exists(timestamp, satellite)

    async def download_file(
        self,
        timestamp: datetime,
        satellite: SatellitePattern,
        destination: Path,
        progress_callback: Callable | None = None,
        cancel_check: Callable | None = None,
    ) -> Path:
        """Download a file for the given timestamp and satellite.

        This method implements the abstract method from RemoteStore.
        Note: progress_callback and cancel_check are not implemented in this stub.
        """
        return await self.download(timestamp, satellite, destination)

    async def get_file_url(self, timestamp: datetime, satellite: SatellitePattern) -> str:
        """Get the URL for a file.

        This method implements the abstract method from RemoteStore.
        """
        bucket, key = self._get_bucket_and_key(timestamp, satellite)
        return f"s3://{bucket}/{key}"
