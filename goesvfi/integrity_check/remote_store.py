"""Remote store for fetching satellite imagery files.

This module defines interfaces and implementations for accessing remote
satellite imagery repositories, downloading missing files, and reporting progress.
"""

import os
import requests
# Import standard libraries
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse

from goesvfi.utils import log
from .time_index import SatellitePattern, generate_expected_filename

LOGGER = log.get_logger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, int, float], None]
CancelCallback = Callable[[], bool]


class RemoteStore(ABC):
    """Abstract base class for remote file stores."""
    
    @abstractmethod
    def construct_url(self, timestamp: datetime, pattern: SatellitePattern) -> str:
        """
        Construct a URL for a specific timestamp and satellite pattern.

        Args:
            timestamp: The datetime for the image
            pattern: The satellite pattern to use

        Returns:
            A URL string for the remote file
        """
    
    @abstractmethod
    def check_file_exists(self, url: str) -> bool:
        """
        Check if a file exists at the given URL.

        Args:
            url: The URL to check

        Returns:
            True if the file exists, False otherwise
        """
    
    @abstractmethod
    def download_file(self,
                     url: str,
                     destination: Path,
                     progress_callback: Optional[ProgressCallback] = None,
                     should_cancel: Optional[CancelCallback] = None) -> bool:
        """
        Download a file from the remote store.

        Args:
            url: The URL to download from
            destination: The local path to save to
            progress_callback: Optional callback for progress updates
            should_cancel: Optional callback to check if download should be cancelled

        Returns:
            True if download succeeded, False otherwise
        """


class HttpRemoteStore(RemoteStore):
    """HTTP-based remote store implementation."""
    
    def __init__(self,
                 base_url: str,
                 timeout: int = 30,
                 verify_ssl: bool = True):
        """
        Initialize the HTTP remote store.
        
        Args:
            base_url: The base URL for the remote repository
            timeout: Connection timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Create a session for connection pooling
        self.session = requests.Session()
        
        # Ensure base URL is accessible
        try:
            response = self.session.head(
                self.base_url,
                 timeout=self.timeout,
                 verify=self.verify_ssl
            )
            if response.status_code not in [200, 301, 302]:
                LOGGER.warning("Base URL may not be accessible: %s, status: %d", self.base_url, response.status_code)
        except requests.RequestException as e:
            LOGGER.error("Error connecting to base URL %s: %s", self.base_url, e)
    
    def construct_url(self, timestamp: datetime, pattern: SatellitePattern) -> str:
        """
        Construct a URL for a specific timestamp and satellite pattern.
        
        This implementation creates URLs with date-based directory structure:
        {base_url}/{year}/{month}/{day}/{filename}
        
        Args:
            timestamp: The datetime for the image
            pattern: The satellite pattern to use
            
        Returns:
            A URL string for the remote file
        """
        # Extract year, month, day components
        year = timestamp.strftime("%Y")
        month = timestamp.strftime("%m")
        day = timestamp.strftime("%d")
        
        # Generate the expected filename
        filename = generate_expected_filename(timestamp, pattern)
        
        # Construct the URL with date-based directory structure
        url = f"{self.base_url}/{year}/{month}/{day}/{filename}"
        
        return url
    
    def check_file_exists(self, url: str) -> bool:
        """
        Check if a file exists at the given URL using a HEAD request.
        
        Args:
            url: The URL to check
            
        Returns:
            True if the file exists (HTTP 200), False otherwise
        """
        try:
            response = self.session.head(
                url, 
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            return response.status_code == 200
        except requests.RequestException as e:
            LOGGER.debug("Error checking if file exists at %s: %s", url, e)
            return False
    
    def download_file(self, 
 {21}url: str, 
 {21}destination: Path,
 {21}progress_callback: Optional[ProgressCallback] = None,
 {21}should_cancel: Optional[CancelCallback] = None) -> bool:
        """
        Download a file from the remote store.
        
        Args:
            url: The URL to download from
            destination: The local path to save to
            progress_callback: Optional callback for progress updates
            should_cancel: Optional callback to check if download should be cancelled
            
        Returns:
            True if download succeeded, False otherwise
        """
        # Ensure destination directory exists
        os.makedirs(destination.parent, exist_ok=True)
        
        try:
            # Get file information to determine size if possible
            response = self.session.head(
                url, 
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code != 200:
                LOGGER.error(f"File not found or not accessible: {url}, status: {response.status_code}")
                return False
            
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            # Begin the download with streaming to handle large files
            with self.session.get(
                url, 
                stream=True, 
                timeout=self.timeout,
                verify=self.verify_ssl
            ) as response:
                
                response.raise_for_status()
                
                # Open destination file
                with open(destination, 'wb') as f:
                    downloaded = 0
                    last_progress_time = datetime.now()
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        # Check for cancellation
                        if should_cancel and should_cancel():
                            LOGGER.info(f"Download cancelled for {url}")
                            return False
                        
                        if chunk:  # Filter out keep-alive chunks
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Report progress (not too frequently)
                            now = datetime.now()
                            if progress_callback and (now - last_progress_time).total_seconds() >= 0.25:
                                progress_callback(
                                    downloaded, 
                                    total_size if total_size > 0 else 1, 
                                    0.0  # No ETA calculation here
                                )
                                last_progress_time = now
            
            # Final progress update
            if progress_callback:
                progress_callback(
                    total_size, 
                    total_size, 
                    0.0  # Download complete
                )
            
            LOGGER.info(f"Successfully downloaded {url} to {destination}")
            return True
            
        except requests.RequestException as e:
            LOGGER.error(f"Error downloading file from {url}: {e}")
            return False
        except IOError as e:
            LOGGER.error(f"IO error writing to {destination}: {e}")
            return False


class FileSystemRemoteStore(RemoteStore):
    """
    File system-based 'remote' store implementation.
    
    This is useful for testing or when the 'remote' repository
    is actually a different folder on the same system.
    """
    
    def __init__(self, base_path: Path):
        """
        Initialize the file system remote store.
        
        Args:
            base_path: The base directory path for the repository
        """
        self.base_path = base_path
        
        if not self.base_path.exists() or not self.base_path.is_dir():
            LOGGER.warning(f"Base directory does not exist: {self.base_path}")
    
    def construct_url(self, timestamp: datetime, pattern: SatellitePattern) -> str:
        """
        Construct a file path for a specific timestamp and satellite pattern.
        
        This implementation creates paths with date-based directory structure:
        {base_path}/{year}/{month}/{day}/{filename}
        
        Args:
            timestamp: The datetime for the image
            pattern: The satellite pattern to use
            
        Returns:
            A file path string for the remote file
        """
        # Extract year, month, day components
        year = timestamp.strftime("%Y")
        month = timestamp.strftime("%m")
        day = timestamp.strftime("%d")
        
        # Generate the expected filename
        filename = generate_expected_filename(timestamp, pattern)
        
        # Construct the path with date-based directory structure
        path = str(self.base_path / year / month / day / filename)
        
        return path
    
    def check_file_exists(self, url: str) -> bool:
        """
        Check if a file exists at the given path.
        
        Args:
            url: The file path to check
            
        Returns:
            True if the file exists, False otherwise
        """
        path = Path(url)
        return path.exists() and path.is_file()
    
    def download_file(self, 
 {21}url: str, 
 {21}destination: Path,
 {21}progress_callback: Optional[ProgressCallback] = None,
 {21}should_cancel: Optional[CancelCallback] = None) -> bool:
        """
        Copy a file from one location to another.
        
        Args:
            url: The source file path
            destination: The destination file path
            progress_callback: Optional callback for progress updates
            should_cancel: Optional callback to check if copy should be cancelled
            
        Returns:
            True if copy succeeded, False otherwise
        """
        # Ensure destination directory exists
        os.makedirs(destination.parent, exist_ok=True)
        
        try:
            # Get source file size
            source_path = Path(url)
            if not source_path.exists() or not source_path.is_file():
                LOGGER.error(f"Source file not found: {source_path}")
                return False
                
            total_size = source_path.stat().st_size
            
            # Check for cancellation before starting
            if should_cancel and should_cancel():
                LOGGER.info(f"File copy cancelled for {url}")
                return False
            
            # Copy the file in chunks to allow progress reporting
            with open(source_path, 'rb') as src, open(destination, 'wb') as dst:
                copied = 0
                last_progress_time = datetime.now()
                
                while True:
                    # Check for cancellation
                    if should_cancel and should_cancel():
                        LOGGER.info(f"File copy cancelled for {url}")
                        return False
                    
                    # Read a chunk
                    chunk = src.read(8192)
                    if not chunk:
                        break  # End of file
                    
                    # Write chunk to destination
                    dst.write(chunk)
                    copied += len(chunk)
                    
                    # Report progress (not too frequently)
                    now = datetime.now()
                    if progress_callback and (now - last_progress_time).total_seconds() >= 0.25:
                        progress_callback(
                            copied, 
                            total_size, 
                            0.0  # No ETA calculation here
                        )
                        last_progress_time = now
            
            # Final progress update
            if progress_callback:
                progress_callback(
                    total_size, 
                    total_size, 
                    0.0  # Copy complete
                )
            
            LOGGER.info(f"Successfully copied {url} to {destination}")
            return True
            
        except IOError as e:
            LOGGER.error(f"IO error copying {url} to {destination}: {e}")
            return False


def create_remote_store(source: str) -> RemoteStore:
    """
    Factory function to create an appropriate RemoteStore implementation.
    
    Args:
        source: The source URL or path string
        
    Returns:
        A RemoteStore implementation
    """
    # Check if it's a URL or local path
    parsed = urlparse(source)
    
    if parsed.scheme in ('http', 'https'):
        # HTTP/HTTPS URL
        return HttpRemoteStore(source)
    elif parsed.scheme == 'file' or not parsed.scheme:
        # Local file system path
        if not parsed.scheme:  # No scheme, assume local path
            path = Path(source)
        else:  # file:// URL
            path = Path(parsed.path)
        
        return FileSystemRemoteStore(path)
    else:
        LOGGER.error(f"Unsupported scheme in source: {source}")
        raise ValueError(f"Unsupported scheme in source: {source}")