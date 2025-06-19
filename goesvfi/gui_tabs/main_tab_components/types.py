"""Type definitions for the main tab module."""

from typing import Dict, List, Optional, TypedDict


class RIFEModelDetails(TypedDict, total=False):
    """Details about a RIFE model."""

    version: Optional[str]
    capabilities: Dict[str, bool]
    supported_args: List[str]
    help_text: Optional[str]
    _mtime: float  # Add _mtime used for caching
