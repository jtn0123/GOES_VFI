"""
Image processing pipeline for composing multiple processing operations.

Provides pipeline utilities that help organize and execute complex image
processing workflows with proper error handling and logging.
"""

from typing import Any, Callable, Dict, List, Optional, cast

from .base import CompositeProcessor, ImageProcessingResult, ProcessorBase


class ImageProcessingPipeline(CompositeProcessor):
    """Pipeline for executing multiple image processing steps in sequence."""

    def __init__(self, processors: List[ProcessorBase]) -> None:
        super().__init__(processors, "image_processing_pipeline")

    def process(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> ImageProcessingResult:
        """Execute all processors in the pipeline."""
        # Import logging here to avoid circular imports
        from goesvfi.utils import log

        logger = log.get_logger(__name__)

        logger.debug(f"Starting image processing pipeline with {len(self.processors)} stages")

        current_data = input_data
        combined_metadata: Dict[str, Any] = {"pipeline_stages": []}
        combined_warnings = []

        for i, processor in enumerate(self.processors):
            logger.debug(f"Executing stage {i + 1}/{len(self.processors)}: {processor.stage_name}")

            try:
                result = processor.process(current_data, context)

                # Track stage execution
                stage_info = {
                    "stage": processor.stage_name,
                    "success": result.success,
                    "warnings": len(result.warnings),
                    "errors": len(result.errors),
                }
                combined_metadata["pipeline_stages"].append(stage_info)

                if not result.success:
                    logger.error(f"Pipeline failed at stage {processor.stage_name}: {result.errors}")
                    # Add pipeline context to the error
                    for error in result.errors:
                        error.message = (
                            f"Pipeline stage {i + 1}/{len(self.processors)} ({processor.stage_name}): {error.message}"
                        )
                    return result

                current_data = result.data
                combined_metadata.update(result.metadata)
                combined_warnings.extend(result.warnings)

                if result.warnings:
                    logger.warning(f"Stage {processor.stage_name} completed with warnings: {result.warnings}")
                else:
                    logger.debug(f"Stage {processor.stage_name} completed successfully")

            except Exception as e:
                logger.exception(f"Unhandled exception in pipeline stage {processor.stage_name}")
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Unhandled exception in stage {processor.stage_name}: {e}", e)
                )

        logger.debug("Image processing pipeline completed successfully")

        return ImageProcessingResult(
            success=True,
            data=current_data,
            errors=[],
            warnings=combined_warnings,
            metadata=combined_metadata,
        )


class ConditionalPipeline(ProcessorBase):
    """Pipeline that executes different processors based on conditions."""

    def __init__(
        self,
        condition_map: Dict[str, ProcessorBase],
        default_processor: Optional[ProcessorBase] = None,
    ) -> None:
        super().__init__("conditional_pipeline")
        self.condition_map = condition_map
        self.default_processor = default_processor

    def process(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> ImageProcessingResult:
        """Execute processor based on context conditions."""
        if not context:
            if self.default_processor:
                return self.default_processor.process(input_data, context)
            return ImageProcessingResult.failure_result(
                self._create_error("No context provided for conditional pipeline")
            )

        # Check conditions in order
        for condition_key, processor in self.condition_map.items():
            if context.get(condition_key, False):
                return processor.process(input_data, context)

        # No conditions met, use default
        if self.default_processor:
            return self.default_processor.process(input_data, context)

        return ImageProcessingResult.failure_result(
            self._create_error("No matching condition found in conditional pipeline")
        )


class ParallelPipeline(ProcessorBase):
    """Pipeline that executes multiple processors in parallel and combines results."""

    def __init__(
        self,
        processors: List[ProcessorBase],
        combiner_func: Optional[Callable[..., Any]] = None,
    ) -> None:
        super().__init__("parallel_pipeline")
        self.processors = processors
        self.combiner_func = combiner_func or self._default_combiner

    def process(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> ImageProcessingResult:
        """Execute all processors in parallel."""
        # For now, execute sequentially (true parallelism would require threading)
        results = []

        for processor in self.processors:
            result = processor.process(input_data, context)
            results.append(result)

            # If any processor fails critically, abort
            if not result.success and context and context.get("abort_on_failure", True):
                return result

        # Combine results
        try:
            combined_result = self.combiner_func(results, input_data, context)
            return cast(ImageProcessingResult, combined_result)
        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"Failed to combine parallel results: {e}", e)
            )

    def _default_combiner(
        self,
        results: List[ImageProcessingResult],
        input_data: Any,
        context: Optional[Dict[str, Any]],
    ) -> ImageProcessingResult:
        """Default combiner that returns the first successful result."""
        successful_results = [r for r in results if r.success]

        if not successful_results:
            # All failed, return the first failure
            return (
                results[0]
                if results
                else ImageProcessingResult.failure_result(self._create_error("No processors in parallel pipeline"))
            )

        # Return first successful result with combined metadata
        result = successful_results[0]
        combined_metadata = {"parallel_results": len(successful_results)}
        combined_metadata.update(result.metadata)

        return ImageProcessingResult(
            success=True,
            data=result.data,
            errors=[],
            warnings=result.warnings,
            metadata=combined_metadata,
        )
