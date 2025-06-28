"""Cache management for image processing operations.

Provides caching utilities that help reduce redundant processing operations
in image processing pipelines.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .base import ImageProcessingResult, ProcessorBase


class CacheManager:
    """Manages caching of processed image data."""

    def __init__(self, max_cache_size: int = 100) -> None:
        self.cache: dict[str, Any] = {}
        self.access_order: list[str] = []
        self.max_cache_size = max_cache_size

    def get(self, key: str) -> Any | None:
        """Get cached data by key."""
        if key in self.cache:
            # Move to end of access order (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None

    def put(self, key: str, data: Any) -> None:
        """Store data in cache with key."""
        if key in self.cache:
            # Update existing entry
            self.cache[key] = data
            self.access_order.remove(key)
            self.access_order.append(key)
        else:
            # Add new entry
            if len(self.cache) >= self.max_cache_size:
                # Remove least recently used item
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]

            self.cache[key] = data
            self.access_order.append(key)

    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        self.access_order.clear()

    def contains(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self.cache

    def remove(self, key: str) -> bool:
        """Remove specific key from cache."""
        if key in self.cache:
            del self.cache[key]
            self.access_order.remove(key)
            return True
        return False

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class CachedProcessor(ProcessorBase):
    """Processor that caches results to avoid redundant processing."""

    def __init__(
        self,
        processor: ProcessorBase,
        cache_manager: CacheManager,
        key_generator: Callable[[Any, dict[str, Any] | None], str],
        stage_name: str | None = None,
    ) -> None:
        super().__init__(stage_name or f"cached_{processor.stage_name}")
        self.processor = processor
        self.cache_manager = cache_manager
        self.key_generator = key_generator

    def process(self, input_data: Any, context: dict[str, Any] | None = None) -> ImageProcessingResult:
        """Process with caching."""
        try:
            # Generate cache key
            cache_key = self.key_generator(input_data, context)

            # Check cache first
            cached_result = self.cache_manager.get(cache_key)
            if cached_result is not None:
                return ImageProcessingResult.success_result(cached_result, {"cache_hit": True, "cache_key": cache_key})

            # Process normally
            result = self.processor.process(input_data, context)

            # Cache successful results
            if result.success and result.data is not None:
                self.cache_manager.put(cache_key, result.data)
                result.metadata["cache_stored"] = True
                result.metadata["cache_key"] = cache_key

            return result

        except Exception as e:
            return ImageProcessingResult.failure_result(self._create_error(f"Cache processing failed: {e}", e))


class SanchezCacheProcessor(ProcessorBase):
    """Specialized cache processor for Sanchez processing results."""

    def __init__(self, cache_dict: dict[Path, np.ndarray]) -> None:
        super().__init__("sanchez_cache")
        self.cache_dict = cache_dict

    def process(self, input_data: Any, context: dict[str, Any] | None = None) -> ImageProcessingResult:
        """Check for cached Sanchez results."""
        if not context or "image_path" not in context:
            return ImageProcessingResult.failure_result(self._create_error("No image_path in context for cache lookup"))

        image_path = context["image_path"]

        if image_path in self.cache_dict:
            cached_array = self.cache_dict[image_path]

            # Import here to avoid circular imports
            from goesvfi.pipeline.image_processing_interfaces import ImageData

            # Create ImageData from cached array
            image_data = ImageData(
                image_data=cached_array,
                metadata={"source_path": image_path, "cached": True},
            )

            return ImageProcessingResult.success_result(image_data, {"cache_hit": True, "source": "sanchez_cache"})

        return ImageProcessingResult.failure_result(self._create_error("No cached Sanchez result found"))

    def store_result(self, image_path: Path, processed_array: np.ndarray) -> None:
        """Store a processed Sanchez result in cache."""
        self.cache_dict[image_path] = processed_array
