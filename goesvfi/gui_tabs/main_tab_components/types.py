"""Type definitions for the main tab module."""

from typing import TypedDict


class RIFEModelDetails(TypedDict, total=False):
    """Details about a RIFE model."""

    version: str | None
    capabilities: dict[str, bool]
    supported_args: list[str]
    help_text: str | None
    _mtime: float  # Add _mtime used for caching
