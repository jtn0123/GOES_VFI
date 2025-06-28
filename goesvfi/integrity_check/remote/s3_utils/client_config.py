"""S3 client configuration for GOES data access.

This module provides configuration management for S3 clients,
including unsigned access configuration for public NOAA buckets.
"""

from dataclasses import dataclass
import logging
from typing import Any

from botocore import UNSIGNED
from botocore.config import Config

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


@dataclass
class S3ClientConfig:
    """Configuration for S3 client connections."""

    aws_profile: str | None = None
    aws_region: str = "us-east-1"
    timeout: int = 60
    connect_timeout: int = 10
    max_retries: int = 2
    enable_debug_logging: bool = False

    def get_session_kwargs(self) -> dict[str, Any]:
        """Get boto3 session keyword arguments.

        Returns:
            Dictionary of session kwargs
        """
        kwargs = {"region_name": self.aws_region}
        if self.aws_profile:
            kwargs["profile_name"] = self.aws_profile
        return kwargs

    def setup_debug_logging(self) -> None:
        """Configure debug logging for boto3/botocore if enabled."""
        if not self.enable_debug_logging:
            return

        if logging.getLogger().level > logging.DEBUG:
            return

        # Set up detailed logging for boto3/botocore
        loggers = [
            ("boto3", logging.DEBUG),
            ("botocore.hooks", logging.DEBUG),
            ("botocore.endpoint", logging.DEBUG),
            ("botocore.auth", logging.DEBUG),
            ("botocore.retryhandler", logging.DEBUG),
        ]

        for logger_name, level in loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

        LOGGER.debug("Enabled debug logging for boto3/botocore")


def create_s3_config(
    timeout: int,
    connect_timeout: int = 10,
    max_retries: int = 2,
    use_unsigned: bool = True,
) -> Config:
    """Create a botocore Config object for S3 client.

    Args:
        timeout: Read timeout in seconds
        connect_timeout: Connection timeout in seconds
        max_retries: Maximum number of retry attempts
        use_unsigned: Whether to use unsigned access (for public buckets)

    Returns:
        Configured botocore.config.Config object
    """
    config_args = {
        "connect_timeout": connect_timeout,
        "read_timeout": timeout,
        "retries": {"max_attempts": max_retries},
    }

    if use_unsigned:
        config_args["signature_version"] = UNSIGNED

    config = Config(**config_args)

    LOGGER.debug(
        "Created S3 config: timeout=%ds, connect_timeout=%ds, max_retries=%d, unsigned=%s",
        timeout,
        connect_timeout,
        max_retries,
        use_unsigned,
    )

    return config
