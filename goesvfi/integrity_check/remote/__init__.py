"""Remote fetching module for retrieving satellite imagery.

This package provides implementations for accessing and downloading 
satellite imagery from various remote sources.
"""

from .base import RemoteStore
from .cdn_store import CDNStore
from .s3_store import S3Store

__all__ = ["RemoteStore", "CDNStore", "S3Store"]