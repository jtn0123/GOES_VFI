"""Base interface for remote data stores.

This module defines the abstract base class for remote data stores,
providing a common interface for accessing and downloading files
from different remote sources.
"""

import abc
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from goesvfi.exceptions import GoesvfiError
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class RemoteStoreError(GoesvfiError):
    """Base exception for remote store errors.

    This class provides structured error information for remote store operations,
    including a user-friendly message and optional technical details that can
    be logged for debugging.
    """

    def __init__(
        self,
        message: str,
        technical_details: Optional[str] = None,
        original_exception: Optional[Exception] = None,
        troubleshooting_tips: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize a remote store error.

        Args:
            message: User-friendly error message
            technical_details: Technical error details for logs
            original_exception: Original exception that caused this error
            troubleshooting_tips: Specific tips to help users resolve the issue
            error_code: An optional error code for categorization
        """
        super().__init__(message)
        self.message = message
        self.technical_details = technical_details
        self.original_exception = original_exception
        self.troubleshooting_tips = troubleshooting_tips
        self.error_code = error_code

    def get_user_message(self) -> str:
        """Get a comprehensive user-friendly error message with troubleshooting tips."""
        if self.troubleshooting_tips:
            return (
                f"{self.message}\n\nTroubleshooting tips:\n{self.troubleshooting_tips}"
            )
        return self.message

    def get_detailed_message(self) -> str:
        """Get a detailed message including error code and core issue."""
        if self.error_code:
            return f"[Error {self.error_code}] {self.message}"
        return self.message

    def get_technical_details(self) -> Dict[str, Any]:
        """Get technical details for logging."""
        details = {
            "message": self.message,
            "technical_details": self.technical_details,
            "troubleshooting_tips": self.troubleshooting_tips,
            "error_code": self.error_code,
        }

        # Add original exception details if available
        if self.original_exception:
            exc_type = type(self.original_exception).__name__
            details["exception_type"] = exc_type
            details["exception_str"] = str(self.original_exception)

            # Add AWS error details if available
            if hasattr(self.original_exception, "response"):
                try:
                    error_code = self.original_exception.response.get("Error", {}).get(
                        "Code"
                    )
                    error_message = self.original_exception.response.get(
                        "Error", {}
                    ).get("Message")
                    request_id = self.original_exception.response.get(
                        "ResponseMetadata", {}
                    ).get("RequestId")

                    if error_code:
                        details["aws_error_code"] = error_code
                    if error_message:
                        details["aws_error_message"] = error_message
                    if request_id:
                        details["aws_request_id"] = request_id
                except (AttributeError, TypeError, KeyError):
                    pass

            # Try to extract any connection-related details
            has_timeout = "timeout" in str(self.original_exception).lower()
            has_connect = "connect" in str(self.original_exception).lower()

            if has_timeout:
                details["timing_issue"] = "Timeout detected"
            else:
                details["timing_issue"] = None

            if has_connect:
                details["connectivity_issue"] = "Connectivity issue detected"
            else:
                details["connectivity_issue"] = None

        return details

    def log_error(self, logger: logging.Logger = LOGGER) -> None:
        """Log the error with appropriate level based on error type."""
        error_prefix = f"[{self.error_code}] " if self.error_code else ""
        logger.error(f"RemoteStore Error: {error_prefix}{self.message}")

        if self.troubleshooting_tips:
            logger.info(f"Troubleshooting tips: {self.troubleshooting_tips}")

        if self.technical_details:
            logger.debug(f"Technical details: {self.technical_details}")

        if self.original_exception:
            exc_type = type(self.original_exception).__name__
            logger.debug(f"Original exception: {exc_type}: {self.original_exception}")

            # Log extra AWS details if available
            if hasattr(self.original_exception, "response"):
                try:
                    error_info = self.original_exception.response.get("Error", {})
                    response_meta = self.original_exception.response.get(
                        "ResponseMetadata", {}
                    )

                    if error_info:
                        logger.debug(f"AWS Error details: {error_info}")
                    if response_meta:
                        logger.debug(f"AWS Response metadata: {response_meta}")
                except (AttributeError, TypeError, KeyError):
                    pass


class AuthenticationError(RemoteStoreError):
    """Authentication error for remote stores."""

    pass


class ConnectionError(RemoteStoreError):
    """Connection error for remote stores."""

    pass


class ResourceNotFoundError(RemoteStoreError):
    """Resource not found error for remote stores."""

    pass


class RemoteStore(abc.ABC):
    """Abstract base class for remote data stores."""

    @abc.abstractmethod
    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """
        Check if a file exists for the given timestamp and satellite.

        Args:
            ts: Datetime to check
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            True if the file exists, False otherwise

        Raises:
            RemoteStoreError: If an error occurs during the check
        """
        pass

    @abc.abstractmethod
    async def download(
        self, ts: datetime, satellite: SatellitePattern, dest_path: Path
    ) -> Path:
        """
        Download a file for the given timestamp and satellite.

        Args:
            ts: Datetime to download
            satellite: Satellite pattern (GOES_16 or GOES_18)
            dest_path: Destination path

        Returns:
            Path to the downloaded file

        Raises:
            RemoteStoreError: If an error occurs during the download
            ResourceNotFoundError: If the file doesn't exist remotely
        """
        pass

    def handle_error(
        self,
        error: Exception,
        operation: str,
        ts: datetime,
        satellite: SatellitePattern,
    ) -> RemoteStoreError:
        """
        Convert standard exceptions to RemoteStoreError types with user-friendly messages.

        Args:
            error: Original exception
            operation: Operation description (e.g., "download", "check")
            ts: Timestamp of the file
            satellite: Satellite pattern

        Returns:
            An appropriate RemoteStoreError subclass with detailed troubleshooting info
        """
        # Generate ISO format and other common timestamp formats for diagnostics
        ts_iso = ts.isoformat()
        ts_year = ts.year
        ts_doy = ts.strftime("%j")  # Day of year
        ts_hour = ts.strftime("%H")
        ts_minute = ts.strftime("%M")
        ts_second = ts.strftime("%S")

        # Get the timestamp info for all errors
        timestamp_info = (
            f"Timestamp details:\n"
            f"- ISO: {ts_iso}\n"
            f"- Year: {ts_year}\n"
            f"- Day of Year: {ts_doy}\n"
            f"- Hour: {ts_hour}\n"
            f"- Minute: {ts_minute}\n"
            f"- Second: {ts_second}"
        )

        # Handle boto3/botocore specific errors
        if "botocore.exceptions" in str(type(error).__module__):
            # Extract more detailed information
            error_response = getattr(error, "response", {})
            error_info = error_response.get("Error", {})
            error_code = error_info.get("Code", "")
            error_message = error_info.get("Message", "")
            request_id = error_response.get("ResponseMetadata", {}).get("RequestId", "")

            # Enhanced AWS technical details with request info
            aws_tech_details = (
                f"AWS Error: {error_code} - {error_message}\n"
                f"Operation: {operation}\n"
                f"Satellite: {satellite.name}\n"
                f"Request ID: {request_id}\n"
                f"{timestamp_info}"
            )

            # Authentication errors
            if error_code in [
                "InvalidAccessKeyId",
                "SignatureDoesNotMatch",
                "AccessDenied",
                "403",
            ]:
                error_id = "AUTH-001"
                # Special case for common credential errors with NOAA buckets
                if "noaa" in str(error).lower() or "goes" in str(error).lower():
                    tips = (
                        "1. NOAA data should be accessible without AWS credentials\n"
                        "2. Check if you have AWS credentials set that might be interfering\n"
                        "3. Try clearing AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                        "4. Verify that your computer's time is synchronized correctly\n"
                        "5. Check if a VPN or proxy is blocking access to AWS S3 services"
                    )
                    return AuthenticationError(
                        message="Error accessing NOAA GOES data: Access denied despite using public access configuration",
                        technical_details=f"{aws_tech_details}\nThis is unusual as NOAA buckets are public.",
                        original_exception=error,
                        troubleshooting_tips=tips,
                        error_code=error_id,
                    )

                tips = (
                    "1. Check your AWS credentials if you're using custom credentials\n"
                    "2. Try without credentials for NOAA public buckets\n"
                    "3. Verify that the satellite selection is correct\n"
                    "4. Check if a VPN or proxy is blocking access to AWS S3 services"
                )
                return AuthenticationError(
                    message=f"Unable to access {satellite.name} data: Authentication error ({error_code})",
                    technical_details=aws_tech_details,
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

            # Not found errors
            elif error_code in ["404", "NoSuchKey", "NoSuchBucket"]:
                error_id = "NF-001"

                if error_code == "NoSuchBucket":
                    tips = (
                        "1. Verify that you have selected the correct satellite (GOES-16 or GOES-18)\n"
                        "2. Check if AWS has changed the bucket structure for NOAA data\n"
                        "3. Try using the CDN source instead of S3 direct access\n"
                        "4. Check the NOAA GOES website to confirm data availability"
                    )
                    return ResourceNotFoundError(
                        message=f"S3 bucket for {satellite.name} not found",
                        technical_details=f"{aws_tech_details}\nBucket does not exist or is inaccessible.",
                        original_exception=error,
                        troubleshooting_tips=tips,
                        error_code="NF-002",
                    )

                tips = (
                    "1. This timestamp may not be available in the NOAA archive\n"
                    "2. Try a different time period (data gaps are common)\n"
                    "3. Verify that the date is within the operational period for this satellite\n"
                    f"4. For {satellite.name}, check if the timestamp ({ts_year}/{ts_doy} {ts_hour}:{ts_minute}) is valid\n"
                    "5. GOES-16 (East) has data from December 2017 onward\n"
                    "6. GOES-18 (West) has data from May 2022 onward\n"
                    "7. Check the NOAA GOES website to confirm data availability"
                )
                return ResourceNotFoundError(
                    message=f"File not found for {satellite.name} at {ts_iso}",
                    technical_details=f"{aws_tech_details}\nThe requested file does not exist in the NOAA archive.",
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

            # Connection errors
            elif error_code in [
                "ConnectionError",
                "ConnectTimeoutError",
                "RequestTimeout",
            ]:
                error_id = "CONN-001"
                tips = (
                    "1. Check your internet connection\n"
                    "2. Verify that you can access other websites and services\n"
                    "3. Try disabling any VPN or proxy services\n"
                    "4. AWS S3 might be experiencing service issues - check the AWS Service Health Dashboard\n"
                    "5. Your ISP might be blocking or throttling AWS S3 traffic\n"
                    "6. Try again later as this may be a temporary network issue"
                )
                return ConnectionError(
                    message=f"Connection timeout while accessing {satellite.name} data ({error_code})",
                    technical_details=f"{aws_tech_details}\nRequest timed out before completion.",
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

            # Too many requests
            elif error_code in [
                "ThrottlingException",
                "RequestLimitExceeded",
                "Throttling",
            ]:
                error_id = "RATE-001"
                tips = (
                    "1. Reduce the number of concurrent requests\n"
                    "2. Implement a delay between requests\n"
                    "3. Try downloading fewer files at once\n"
                    "4. AWS might be limiting requests to the public NOAA buckets\n"
                    "5. Wait a few minutes and try again"
                )
                return RemoteStoreError(
                    message=f"Rate limit exceeded while accessing {satellite.name} data",
                    technical_details=f"{aws_tech_details}\nToo many requests sent to AWS S3.",
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

            # Internal server errors
            elif error_code in ["InternalError", "ServiceUnavailable", "500", "503"]:
                error_id = "AWS-001"
                tips = (
                    "1. This is an AWS server-side issue\n"
                    "2. Try again later as AWS services might be experiencing problems\n"
                    "3. Check the AWS Service Health Dashboard for S3 issues\n"
                    "4. Try using the CDN source instead of direct S3 access"
                )
                return RemoteStoreError(
                    message=f"AWS S3 service error while accessing {satellite.name} data ({error_code})",
                    technical_details=f"{aws_tech_details}\nAWS S3 is experiencing internal server issues.",
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

            # Generic S3 errors with user-friendly message
            else:
                error_id = "S3-001"
                tips = (
                    "1. Check your internet connection\n"
                    "2. Verify that you've selected the correct satellite\n"
                    "3. Try using the CDN source instead of direct S3 access\n"
                    "4. AWS S3 might be experiencing service issues\n"
                    "5. Try again later"
                )
                return RemoteStoreError(
                    message=f"Error accessing {satellite.name} data: {error_code}",
                    technical_details=f"{aws_tech_details}\nUnrecognized AWS error code.",
                    original_exception=error,
                    troubleshooting_tips=tips,
                    error_code=error_id,
                )

        # Generic FileNotFound errors
        elif isinstance(error, FileNotFoundError):
            error_id = "FILE-001"
            tips = (
                "1. Check if the selected directory exists and is accessible\n"
                "2. Verify that you have permission to write to the directory\n"
                "3. If downloading to an external drive, check that it's properly connected\n"
                "4. Verify that you have sufficient disk space"
            )
            return ResourceNotFoundError(
                message=f"Cannot save file for {satellite.name} at {ts_iso}",
                technical_details=f"File system error during {operation}:\n{str(error)}\n{timestamp_info}",
                original_exception=error,
                troubleshooting_tips=tips,
                error_code=error_id,
            )

        # Network and connectivity errors
        elif isinstance(error, IOError):
            error_id = "NET-001"
            error_desc = str(error).lower()

            # Customize tips based on the type of IO error
            if "timeout" in error_desc:
                tips = (
                    "1. Your internet connection may be slow or unstable\n"
                    "2. Check if other large downloads work properly\n"
                    "3. Try disabling any VPN or proxy services\n"
                    "4. Your ISP might be throttling S3 traffic\n"
                    "5. Try again during off-peak hours"
                )
                error_id = "NET-002"
            elif "permission" in error_desc:
                tips = (
                    "1. Check if you have permission to write to the selected directory\n"
                    "2. Try running the application with administrator privileges\n"
                    "3. If using an external drive, check that it's not write-protected\n"
                    "4. Verify that any antivirus software isn't blocking write operations"
                )
                error_id = "PERM-001"
            elif "disk" in error_desc or "space" in error_desc:
                tips = (
                    "1. Free up disk space on the destination drive\n"
                    "2. Choose a different directory with more available space\n"
                    "3. Remove any temporary files that might be taking up space\n"
                    "4. Check if the drive has a size limit for individual files"
                )
                error_id = "DISK-001"
            else:
                tips = (
                    "1. Check your internet connection\n"
                    "2. Verify that you can access other websites\n"
                    "3. Your firewall might be blocking the connection\n"
                    "4. Try disabling any VPN or proxy services temporarily\n"
                    "5. Try again later"
                )

            return ConnectionError(
                message=f"Network error accessing {satellite.name} data",
                technical_details=f"IO error during {operation}:\n{str(error)}\n{timestamp_info}",
                original_exception=error,
                troubleshooting_tips=tips,
                error_code=error_id,
            )

        # Catch DNS errors separately
        elif "DNSLookupError" in str(type(error).__name__):
            error_id = "DNS-001"
            tips = (
                "1. Your computer cannot resolve AWS domain names\n"
                "2. Check if your DNS settings are working correctly\n"
                "3. Try using a different DNS server (e.g., 8.8.8.8)\n"
                "4. Verify that you can access other websites\n"
                "5. Your ISP might be having DNS issues"
            )
            return ConnectionError(
                message=f"DNS error accessing {satellite.name} data",
                technical_details=f"DNS lookup error during {operation}:\n{str(error)}\n{timestamp_info}",
                original_exception=error,
                troubleshooting_tips=tips,
                error_code=error_id,
            )

        # SSL/TLS errors
        elif "SSL" in str(type(error).__name__) or "Certificate" in str(error):
            error_id = "SSL-001"
            tips = (
                "1. Your system has SSL/TLS certificate validation issues\n"
                "2. Check if your system date and time are correct\n"
                "3. Update your SSL/TLS certificates\n"
                "4. Your network might be intercepting secure connections\n"
                "5. A security product might be interfering with secure connections"
            )
            return ConnectionError(
                message=f"SSL/TLS error accessing {satellite.name} data",
                technical_details=f"SSL error during {operation}:\n{str(error)}\n{timestamp_info}",
                original_exception=error,
                troubleshooting_tips=tips,
                error_code=error_id,
            )

        # Generic catch-all
        else:
            error_id = "GEN-001"
            error_type = type(error).__name__
            error_desc = str(error).lower()

            # Try to provide more specific troubleshooting based on error text
            if "timeout" in error_desc:
                tips = (
                    "1. The operation took too long to complete\n"
                    "2. Check your internet connection speed and stability\n"
                    "3. The NOAA servers might be under heavy load\n"
                    "4. Try again later or try downloading fewer files at once"
                )
                error_id = "GEN-002"
            elif "memory" in error_desc:
                tips = (
                    "1. Your system may be low on memory\n"
                    "2. Close other applications to free up memory\n"
                    "3. Restart the application and try downloading fewer files at once\n"
                    "4. Consider upgrading your system memory if this happens frequently"
                )
                error_id = "MEM-001"
            else:
                tips = (
                    "1. Check the application logs for more details\n"
                    "2. Verify that you've selected the correct satellite and time period\n"
                    "3. Try using a different fetch source (CDN vs S3)\n"
                    "4. Restart the application and try again\n"
                    "5. If the problem persists, report this error with the timestamp details"
                )

            return RemoteStoreError(
                message=f"Unexpected error ({error_type}) accessing {satellite.name} data",
                technical_details=f"Error during {operation}:\n{str(error)}\n{timestamp_info}",
                original_exception=error,
                troubleshooting_tips=tips,
                error_code=error_id,
            )
