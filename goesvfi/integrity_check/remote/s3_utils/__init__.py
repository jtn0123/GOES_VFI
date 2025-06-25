"""S3 utilities package for GOES satellite data access.

This package provides modular components for S3 operations, statistics tracking,
client configuration, and error handling.
"""

from .client_config import S3ClientConfig, create_s3_config
from .download_stats import DownloadStats, DownloadStatsTracker
from .error_converter import S3ErrorConverter
from .network_diagnostics import NetworkDiagnostics

__all__ = [
    "S3ClientConfig",
    "create_s3_config",
    "DownloadStats",
    "DownloadStatsTracker",
    "S3ErrorConverter",
    "NetworkDiagnostics",
]
