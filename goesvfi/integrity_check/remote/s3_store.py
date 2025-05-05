"""
S3 Store implementation for accessing GOES imagery via AWS S3 buckets.

This module provides a RemoteStore implementation that fetches GOES Band 13
NetCDF data from AWS S3 buckets using asynchronous boto3 operations.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import aioboto3
import botocore.exceptions

from goesvfi.integrity_check.time_index import TimeIndex, SatellitePattern
from goesvfi.integrity_check.remote.base import RemoteStore
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

class S3Store(RemoteStore):
    """Store implementation for AWS S3 buckets containing GOES data."""
    
    def __init__(
        self,
        aws_profile: Optional[str] = None,
        aws_region: str = "us-east-1",
        timeout: int = 60
    ):
        """Initialize with optional AWS profile and timeout parameters.
        
        Args:
            aws_profile: AWS profile name to use (optional)
            aws_region: AWS region name
            timeout: Operation timeout in seconds
        """
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.timeout = timeout
        self._session = None
        self._s3_client = None
        
    @property
    def session_kwargs(self) -> Dict[str, Any]:
        """Get boto3 session keyword arguments."""
        kwargs = {
            "region_name": self.aws_region
        }
        if self.aws_profile:
            kwargs["profile_name"] = self.aws_profile
        return kwargs
    
    async def _get_s3_client(self):
        """Get or create an S3 client."""
        if self._s3_client is None:
            session = aioboto3.Session(**self.session_kwargs)
            self._s3_client = await session.client("s3").__aenter__()
        return self._s3_client
    
    async def close(self):
        """Close the S3 client."""
        if self._s3_client is not None:
            await self._s3_client.__aexit__(None, None, None)
            self._s3_client = None
    
    async def __aenter__(self):
        """Context manager entry."""
        await self._get_s3_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    def _get_bucket_and_key(self, ts: datetime, satellite: SatellitePattern, exact_match: bool = False) -> Tuple[str, str]:
        """Get the S3 bucket and key for the given timestamp and satellite.
        
        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            exact_match: If True, return a concrete filename without wildcards
            
        Returns:
            Tuple of (bucket_name, object_key)
        """
        bucket = TimeIndex.S3_BUCKETS[satellite]
        key = TimeIndex.to_s3_key(ts, satellite, exact_match=exact_match)
        return bucket, key
    
    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists in S3 for the timestamp and satellite.
        
        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            
        Returns:
            True if the file exists, False otherwise
        """
        # Use exact_match=True for head_object operations
        bucket, key = self._get_bucket_and_key(ts, satellite, exact_match=True)
        s3 = await self._get_s3_client()
        
        try:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                LOGGER.debug(f"S3 object not found: s3://{bucket}/{key}")
                return False
            LOGGER.debug(f"S3 check failed for s3://{bucket}/{key}: {e}")
            return False
    
    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """Download a file from S3.
        
        Args:
            ts: Timestamp to download
            satellite: Satellite pattern enum
            dest_path: Destination path to save the file
            
        Returns:
            Path to the downloaded file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            IOError: If there's an error during download
        """
        # Use exact_match=True for head_object and download operations
        bucket, key = self._get_bucket_and_key(ts, satellite, exact_match=True)
        s3 = await self._get_s3_client()
        
        try:
            # First check if the file exists
            try:
                await s3.head_object(Bucket=bucket, Key=key)
            except botocore.exceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == '404':
                    raise FileNotFoundError(f"File not found: s3://{bucket}/{key}")
                raise IOError(f"Failed to check s3://{bucket}/{key}: {e}")
            
            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file
            LOGGER.debug(f"Downloading s3://{bucket}/{key} to {dest_path}")
            # Note: Download progress not directly supported by aioboto3, 
            # could add a callback in future versions
            await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))
            
            LOGGER.debug(f"Download complete: {dest_path}")
            return dest_path
            
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                raise FileNotFoundError(f"File not found: s3://{bucket}/{key}")
            raise IOError(f"Failed to download s3://{bucket}/{key}: {e}")
        except Exception as e:
            raise IOError(f"Unexpected error downloading s3://{bucket}/{key}: {e}")