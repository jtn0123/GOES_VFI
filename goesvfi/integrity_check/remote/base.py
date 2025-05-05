"""Base interface for remote data stores.

This module defines the abstract base class for remote data stores,
providing a common interface for accessing and downloading files
from different remote sources.
"""

import abc
from datetime import datetime
from pathlib import Path
from typing import Optional

from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


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
        """
        pass
    
    @abc.abstractmethod
    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """
        Download a file for the given timestamp and satellite.
        
        Args:
            ts: Datetime to download
            satellite: Satellite pattern (GOES_16 or GOES_18)
            dest_path: Destination path
            
        Returns:
            Path to the downloaded file
        """
        pass