"""Enumerations for the main tab module."""

from enum import Enum


class InterpolationMethod(Enum):
    """Available interpolation methods for video processing."""

    NONE = "None"
    RIFE = "RIFE"
    FFMPEG = "FFmpeg"


class RawEncoderMethod(Enum):
    """Available raw encoding methods for processing."""

    NONE = "None"
    RIFE = "RIFE"
    SANCHEZ = "Sanchez"
