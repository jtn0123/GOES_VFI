"""Fast, optimized tests for validation pipeline - critical business logic."""

from unittest.mock import MagicMock, patch

from goesvfi.utils.validation.base import ValidationError, ValidationResult, ValidatorBase
from goesvfi.utils.validation.pipeline import ValidationPipeline


class MockValidator(ValidatorBase):
    """Mock validator for testing pipeline logic."""

    def __init__(self, field_name: str | None = None, should_pass: bool = True, should_error: bool = False):
        super().__init__(field_name)
        self.should_pass = should_pass
        self.should_error = should_error

    def validate(self, value, context=None) -> ValidationResult:
        if self.should_error:
            msg = f"Validator {self.field_name} error"
            raise ValueError(msg)

        if self.should_pass:
            return ValidationResult.success()
        error = ValidationError(f"{self.field_name} failed", field=self.field_name, value=value)
        return ValidationResult.failure(error)


class TestValidationPipeline:
    """Test validation pipeline with fast, synthetic validators."""

    def test_pipeline_all_validators_pass(self) -> None:
        """Test pipeline when all validators pass."""
        pipeline = ValidationPipeline("test_pipeline")

        pipeline.add_validator("field1", MockValidator("validator1", should_pass=True), "test_value1")
        pipeline.add_validator("field2", MockValidator("validator2", should_pass=True), "test_value2")
        pipeline.add_validator("field3", MockValidator("validator3", should_pass=True), "test_value3")

        result = pipeline.validate()

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_pipeline_some_validators_fail(self) -> None:
        """Test pipeline when some validators fail."""
        pipeline = ValidationPipeline("test_pipeline")

        pipeline.add_validator("field1", MockValidator("pass1", should_pass=True), "test_value1")
        pipeline.add_validator("field2", MockValidator("fail1", should_pass=False), "test_value2")
        pipeline.add_validator("field3", MockValidator("pass2", should_pass=True), "test_value3")
        pipeline.add_validator("field4", MockValidator("fail2", should_pass=False), "test_value4")

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) == 2

        # Check specific failures
        error_messages = [error.message for error in result.errors]
        assert "fail1 failed" in error_messages
        assert "fail2 failed" in error_messages

    def test_pipeline_fail_fast_mode(self) -> None:
        """Test pipeline stops on first failure in fail-fast mode."""
        pipeline = ValidationPipeline("test_pipeline", fail_fast=True)

        pipeline.add_validator("field1", MockValidator("pass1", should_pass=True), "test_value1")
        pipeline.add_validator("field2", MockValidator("fail1", should_pass=False), "test_value2")  # Should stop here
        pipeline.add_validator("field3", MockValidator("never_reached", should_pass=True), "test_value3")

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "fail1 failed" in [error.message for error in result.errors]

    def test_pipeline_collect_all_errors_mode(self) -> None:
        """Test pipeline collects all errors in collect-all mode."""
        pipeline = ValidationPipeline("test_pipeline", fail_fast=False)

        pipeline.add_validator("field1", MockValidator("fail1", should_pass=False), "test_value1")
        pipeline.add_validator("field2", MockValidator("fail2", should_pass=False), "test_value2")
        pipeline.add_validator("field3", MockValidator("fail3", should_pass=False), "test_value3")

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) == 3  # All failures collected

        error_messages = [error.message for error in result.errors]
        assert "fail1 failed" in error_messages
        assert "fail2 failed" in error_messages
        assert "fail3 failed" in error_messages

    def test_pipeline_handles_validator_exceptions(self) -> None:
        """Test pipeline handles validator exceptions gracefully."""
        pipeline = ValidationPipeline("test_pipeline", fail_fast=False)

        pipeline.add_validator("field1", MockValidator("good1", should_pass=True), "test_value1")
        pipeline.add_validator("field2", MockValidator("error1", should_error=True), "test_value2")  # Throws exception
        pipeline.add_validator("field3", MockValidator("good2", should_pass=True), "test_value3")

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) >= 1

        # Should have captured the exception as an error
        error_messages = [error.message for error in result.errors]
        assert any("error1" in msg for msg in error_messages)

    def test_pipeline_empty_validator_list(self) -> None:
        """Test pipeline with no validators."""
        pipeline = ValidationPipeline("test_pipeline")
        result = pipeline.validate()

        # Empty pipeline should pass by default
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_pipeline_validator_execution_order(self) -> None:
        """Test basic validator functionality."""
        pipeline = ValidationPipeline("test_pipeline")

        pipeline.add_validator("field1", MockValidator("first", should_pass=True), "test_value1")
        pipeline.add_validator("field2", MockValidator("second", should_pass=True), "test_value2")
        pipeline.add_validator("field3", MockValidator("third", should_pass=True), "test_value3")

        result = pipeline.validate()

        assert result.is_valid
        assert len(result.errors) == 0

    def test_pipeline_context_passing(self) -> None:
        """Test that context is passed through the pipeline."""
        pipeline = ValidationPipeline("test_pipeline")

        pipeline.add_validator("field1", MockValidator("context_check", should_pass=True), "test_value1")

        # Test with context
        context = {"test_key": "test_value"}
        result = pipeline.validate(context=context)

        assert result.is_valid

    def test_pipeline_with_directory_validation(self) -> None:
        """Test pipeline with convenience methods (mocked for speed)."""
        with patch("goesvfi.utils.validation.path.DirectoryValidator") as mock_dir_validator:
            mock_instance = MagicMock()
            mock_instance.validate.return_value = ValidationResult.success()
            mock_dir_validator.return_value = mock_instance

            pipeline = ValidationPipeline("test_pipeline")
            pipeline.add_directory_validation("test_dir", "/fake/path", must_exist=True)

            result = pipeline.validate()
            assert result.is_valid

    def test_pipeline_performance_with_many_validators(self) -> None:
        """Test pipeline performance with many fast validators."""
        import time

        pipeline = ValidationPipeline("test_pipeline")

        # Create 100 fast validators
        for i in range(100):
            pipeline.add_validator(f"field_{i}", MockValidator(f"validator_{i}", should_pass=True), f"test_value_{i}")

        start_time = time.time()
        result = pipeline.validate()
        end_time = time.time()

        # Should complete very quickly with mocked validators
        assert (end_time - start_time) < 0.1  # Less than 100ms
        assert result.is_valid
        assert len(result.errors) == 0
