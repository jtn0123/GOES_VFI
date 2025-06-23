"""
Image processing framework for reducing complexity in image handling functions.

This module provides composable image processing pipelines that help reduce the 
complexity of functions with extensive image loading, processing, and display logic.
"""

from .base import ImageProcessingError, ImageProcessingResult, ProcessorBase
from .cache import CacheManager
from .converters import ArrayToImageConverter, ImageToPixmapConverter
from .pipeline import ImageProcessingPipeline
from .preview import PreviewProcessor

__all__ = [
    "ImageProcessingError",
    "ImageProcessingResult", 
    "ProcessorBase",
    "CacheManager",
    "ArrayToImageConverter",
    "ImageToPixmapConverter",
    "ImageProcessingPipeline",
    "PreviewProcessor",
]