"""Base classes for image processing framework.

Provides the foundation for composable image processing that reduces complexity
in functions with extensive image manipulation logic.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from PyQt6.QtGui import QImage, QPixmap


class ImageProcessingError(Exception):
    """Base exception for image processing failures."""

    def __init__(self, message: str, stage: str | None = None, cause: Any = None) -> None:
        self.message = message
        self.stage = stage
        self.cause = cause
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with stage context."""
        if self.stage:
            return f"Image processing failed at '{self.stage}': {self.message}"
        return f"Image processing failed: {self.message}"


@dataclass
class ImageProcessingResult:
    """Result of an image processing operation."""

    success: bool
    data: np.ndarray | QImage | QPixmap | None
    errors: list[ImageProcessingError]
    warnings: list[str]
    metadata: dict[str, Any]

    @classmethod
    def success_result(
        cls: type["ImageProcessingResult"],
        data: Any,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageProcessingResult":
        """Create a successful processing result."""
        return cls(
            success=True,
            data=data,
            errors=[],
            warnings=[],
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls: type["ImageProcessingResult"],
        error: ImageProcessingError,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageProcessingResult":
        """Create a failed processing result."""
        return cls(
            success=False,
            data=None,
            errors=[error],
            warnings=[],
            metadata=metadata or {},
        )

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def add_error(self, error: ImageProcessingError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False


class ProcessorBase(ABC):
    """Base class for all image processors."""

    def __init__(self, stage_name: str) -> None:
        self.stage_name = stage_name

    @abstractmethod
    def process(self, input_data: Any, context: dict[str, Any] | None = None) -> ImageProcessingResult:
        """Process input data.

        Args:
            input_data: The data to process
            context: Optional context for processing (e.g., settings, metadata)

        Returns:
            ImageProcessingResult indicating success or failure
        """

    def _create_error(self, message: str, cause: Any = None) -> ImageProcessingError:
        """Create an ImageProcessingError with proper stage context."""
        return ImageProcessingError(message, stage=self.stage_name, cause=cause)


class CompositeProcessor(ProcessorBase):
    """Processor that combines multiple processors in sequence."""

    def __init__(self, processors: list[ProcessorBase], stage_name: str = "composite") -> None:
        super().__init__(stage_name)
        self.processors = processors

    def process(self, input_data: Any, context: dict[str, Any] | None = None) -> ImageProcessingResult:
        """Run all processors in sequence."""
        current_data = input_data
        combined_metadata = {}
        combined_warnings = []

        for processor in self.processors:
            result = processor.process(current_data, context)

            if not result.success:
                # If any processor fails, return the failure
                return result

            current_data = result.data
            combined_metadata.update(result.metadata)
            combined_warnings.extend(result.warnings)

        return ImageProcessingResult(
            success=True,
            data=current_data,
            errors=[],
            warnings=combined_warnings,
            metadata=combined_metadata,
        )


class ConditionalProcessor(ProcessorBase):
    """Processor that only runs if a condition is met."""

    def __init__(
        self,
        processor: ProcessorBase,
        condition_func: Callable[[Any, dict[str, Any] | None], bool],
        stage_name: str | None = None,
    ) -> None:
        super().__init__(stage_name or f"conditional_{processor.stage_name}")
        self.processor = processor
        self.condition_func = condition_func

    def process(self, input_data: Any, context: dict[str, Any] | None = None) -> ImageProcessingResult:
        """Run processor only if condition is true."""
        if self.condition_func(input_data, context):
            return self.processor.process(input_data, context)

        # If condition not met, pass through input unchanged
        return ImageProcessingResult.success_result(input_data, {"skipped": self.processor.stage_name})
