"""
CDN Store implementation for accessing GOES imagery via NOAA STAR CDN.

This module provides a RemoteStore implementation that fetches GOES Band 13
imagery from the NOAA STAR CDN using asynchronous HTTP requests.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError

from goesvfi.integrity_check.time_index import TimeIndex, SatellitePattern
from goesvfi.integrity_check.remote.base import RemoteStore
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

class CDNStore(RemoteStore):
    """Store implementation for the NOAA STAR CDN."""
    
    def __init__(self, resolution: Optional[str] = None, timeout: int = 30):
        """Initialize with optional resolution and timeout parameters.
        
        Args:
            resolution: Image resolution to fetch (default: TimeIndex.CDN_RES)
            timeout: HTTP timeout in seconds (default: 30)
        """
        self.resolution = resolution or TimeIndex.CDN_RES
        self.timeout = timeout
        self._session = None
    
    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={'User-Agent': 'GOES-VFI/1.0'}
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.session
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """Check if a file exists in the CDN for the timestamp and satellite.
        
        Args:
            ts: Timestamp to check
            satellite: Satellite pattern enum
            
        Returns:
            True if the file exists, False otherwise
        """
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)
        session = await self.session
        
        try:
            async with session.head(url, allow_redirects=True) as response:
                return response.status == 200
        except ClientError as e:
            LOGGER.debug(f"CDN check failed for {url}: {e}")
            return False
    
    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """Download a file from the CDN.
        
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
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)
        session = await self.session
        
        try:
            # First check if the file exists
            async with session.head(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise FileNotFoundError(f"File not found at {url} (status: {response.status})")
        
            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download the file with progress tracking
            LOGGER.debug(f"Downloading {url} to {dest_path}")
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise FileNotFoundError(f"File not found at {url} (status: {response.status})")
                
                total_size = int(response.headers.get('Content-Length', 0))
                LOGGER.debug(f"Total size: {total_size} bytes")
                
                with open(dest_path, 'wb') as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress every ~10%
                        if total_size > 0 and downloaded % (total_size // 10) < 8192:
                            progress = downloaded / total_size * 100
                            LOGGER.debug(f"Download progress: {progress:.1f}%")
            
            LOGGER.debug(f"Download complete: {dest_path}")
            return dest_path
            
        except ClientResponseError as e:
            if e.status == 404:
                raise FileNotFoundError(f"File not found at {url}")
            raise IOError(f"Failed to download {url}: {e}")
        except ClientError as e:
            raise IOError(f"Failed to download {url}: {e}")
        except Exception as e:
            raise IOError(f"Unexpected error downloading {url}: {e}")