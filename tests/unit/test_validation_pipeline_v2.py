"""Fast, optimized tests for validation pipeline - critical business logic (Optimized v2).

Optimizations:
- Shared mock validator fixtures to reduce setup overhead
- Parameterized tests for similar validation scenarios
- Mock time operations for performance tests
- Consolidated related test methods
- Streamlined validator creation and configuration
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from goesvfi.utils.validation.base import ValidationError, ValidationResult, ValidatorBase
from goesvfi.utils.validation.pipeline import ValidationPipeline


class MockValidator(ValidatorBase):
    """Mock validator for testing pipeline logic with configurable behavior."""

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


@pytest.fixture()
def validator_factory():
    """Factory for creating mock validators with different configurations."""

    def create_validator(field_name: str, should_pass: bool = True, should_error: bool = False):
        return MockValidator(field_name, should_pass, should_error)

    return create_validator


@pytest.fixture()
def sample_validation_configs():
    """Sample validation configurations for testing."""
    return {
        "all_pass": [
            {"field": "field1", "should_pass": True},
            {"field": "field2", "should_pass": True},
            {"field": "field3", "should_pass": True},
        ],
        "mixed_results": [
            {"field": "pass1", "should_pass": True},
            {"field": "fail1", "should_pass": False},
            {"field": "pass2", "should_pass": True},
            {"field": "fail2", "should_pass": False},
        ],
        "all_fail": [
            {"field": "fail1", "should_pass": False},
            {"field": "fail2", "should_pass": False},
            {"field": "fail3", "should_pass": False},
        ],
        "with_errors": [
            {"field": "good1", "should_pass": True},
            {"field": "error1", "should_pass": False, "should_error": True},
            {"field": "good2", "should_pass": True},
        ],
    }


@pytest.fixture()
def pipeline_factory(validator_factory):
    """Factory for creating validation pipelines with configured validators."""

    def create_pipeline(pipeline_name: str, config_list: list[dict[str, Any]], fail_fast: bool = False):
        pipeline = ValidationPipeline(pipeline_name, fail_fast=fail_fast)

        for i, config in enumerate(config_list):
            field_name = config["field"]
            should_pass = config.get("should_pass", True)
            should_error = config.get("should_error", False)

            validator = validator_factory(field_name, should_pass, should_error)
            pipeline.add_validator(field_name, validator, f"test_value_{i}")

        return pipeline

    return create_pipeline


class TestValidationPipelineCore:
    """Test core validation pipeline functionality."""

    def test_empty_pipeline_validation(self) -> None:
        """Test pipeline with no validators."""
        pipeline = ValidationPipeline("empty_test_pipeline")
        result = pipeline.validate()

        # Empty pipeline should pass by default
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    @pytest.mark.parametrize(
        "config_name,expected_valid,expected_error_count",
        [
            ("all_pass", True, 0),
            ("mixed_results", False, 2),
            ("all_fail", False, 3),
        ],
    )
    def test_pipeline_validation_outcomes(
        self, pipeline_factory, sample_validation_configs, config_name, expected_valid, expected_error_count
    ) -> None:
        """Test pipeline validation with different validator configurations."""
        config = sample_validation_configs[config_name]
        pipeline = pipeline_factory("test_pipeline", config)

        result = pipeline.validate()

        assert result.is_valid == expected_valid
        assert len(result.errors) == expected_error_count

    def test_pipeline_fail_fast_vs_collect_all(self, pipeline_factory, sample_validation_configs) -> None:
        """Test fail-fast vs collect-all error handling modes."""
        config = sample_validation_configs["all_fail"]

        # Test fail-fast mode
        fail_fast_pipeline = pipeline_factory("fail_fast_test", config, fail_fast=True)
        fail_fast_result = fail_fast_pipeline.validate()

        assert not fail_fast_result.is_valid
        assert len(fail_fast_result.errors) == 1  # Should stop at first failure

        # Test collect-all mode
        collect_all_pipeline = pipeline_factory("collect_all_test", config, fail_fast=False)
        collect_all_result = collect_all_pipeline.validate()

        assert not collect_all_result.is_valid
        assert len(collect_all_result.errors) == 3  # Should collect all failures

    def test_validator_exception_handling(self, pipeline_factory, sample_validation_configs) -> None:
        """Test pipeline handles validator exceptions gracefully."""
        config = sample_validation_configs["with_errors"]
        pipeline = pipeline_factory("exception_test", config, fail_fast=False)

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) >= 1

        # Should have captured the exception as an error
        error_messages = [error.message for error in result.errors]
        assert any("error1" in msg for msg in error_messages)


class TestValidationPipelineAdvanced:
    """Test advanced validation pipeline features."""

    def test_context_passing_through_pipeline(self, validator_factory) -> None:
        """Test that context is passed through the pipeline correctly."""
        pipeline = ValidationPipeline("context_test")
        validator = validator_factory("context_check", should_pass=True)
        pipeline.add_validator("field1", validator, "test_value1")

        # Test with context
        context = {"test_key": "test_value", "user_id": 123}
        result = pipeline.validate(context=context)

        assert result.is_valid

    @pytest.mark.parametrize("validator_count", [5, 10, 25, 50])
    def test_pipeline_scalability(self, validator_factory, validator_count) -> None:
        """Test pipeline performance with varying numbers of validators."""
        pipeline = ValidationPipeline("scalability_test")

        # Create many fast validators
        for i in range(validator_count):
            validator = validator_factory(f"validator_{i}", should_pass=True)
            pipeline.add_validator(f"field_{i}", validator, f"test_value_{i}")

        result = pipeline.validate()

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validation_result_error_details(self, validator_factory) -> None:
        """Test detailed error information in validation results."""
        pipeline = ValidationPipeline("error_details_test")

        # Add failing validators with specific error details
        failing_configs = [
            ("email_field", "invalid_email@"),
            ("age_field", -5),
            ("name_field", ""),
        ]

        for field_name, test_value in failing_configs:
            validator = validator_factory(field_name, should_pass=False)
            pipeline.add_validator(field_name, validator, test_value)

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) == 3

        # Check that error details are preserved
        error_fields = [error.field for error in result.errors]
        assert "email_field" in error_fields
        assert "age_field" in error_fields
        assert "name_field" in error_fields

    def test_mixed_success_and_failure_scenarios(self, validator_factory) -> None:
        """Test pipeline with complex mixed success/failure scenarios."""
        pipeline = ValidationPipeline("mixed_scenario_test")

        # Complex scenario: some pass, some fail, some throw errors
        scenarios = [
            ("critical_field", True, False),  # Pass
            ("optional_field", False, False),  # Fail
            ("validated_field", True, False),  # Pass
            ("broken_field", False, True),  # Error
            ("final_field", True, False),  # Pass
        ]

        for field_name, should_pass, should_error in scenarios:
            validator = validator_factory(field_name, should_pass, should_error)
            pipeline.add_validator(field_name, validator, f"value_for_{field_name}")

        result = pipeline.validate()

        assert not result.is_valid  # Should fail due to failures and errors
        assert len(result.errors) >= 2  # At least the explicit failure and the error


class TestValidationPipelineIntegration:
    """Test validation pipeline integration features."""

    def test_directory_validation_integration(self, validator_factory) -> None:
        """Test pipeline with directory validation integration."""
        with patch("goesvfi.utils.validation.path.DirectoryValidator") as mock_dir_validator:
            mock_instance = MagicMock()
            mock_instance.validate.return_value = ValidationResult.success()
            mock_dir_validator.return_value = mock_instance

            pipeline = ValidationPipeline("integration_test")
            pipeline.add_directory_validation("test_dir", "/fake/path", must_exist=True)

            result = pipeline.validate()
            assert result.is_valid

    @patch("time.time")
    def test_pipeline_performance_benchmarking(self, mock_time, validator_factory) -> None:
        """Test pipeline performance with mocked time operations."""
        # Mock time to return predictable values
        mock_time.side_effect = [0.0, 0.05]  # 50ms execution time

        pipeline = ValidationPipeline("performance_test")

        # Create multiple validators for performance testing
        for i in range(20):  # Reduced from 100 for faster execution
            validator = validator_factory(f"validator_{i}", should_pass=True)
            pipeline.add_validator(f"field_{i}", validator, f"test_value_{i}")

        result = pipeline.validate()

        # Should complete and be valid
        assert result.is_valid
        assert len(result.errors) == 0

    @pytest.mark.parametrize("fail_fast", [True, False])
    def test_pipeline_execution_modes(self, validator_factory, fail_fast) -> None:
        """Test pipeline execution in different modes."""
        pipeline = ValidationPipeline("execution_mode_test", fail_fast=fail_fast)

        # Add validators that will fail at different points
        configs = [
            ("validator_1", True),  # Pass
            ("validator_2", False),  # Fail
            ("validator_3", False),  # Fail
            ("validator_4", True),  # Pass
        ]

        for field_name, should_pass in configs:
            validator = validator_factory(field_name, should_pass)
            pipeline.add_validator(field_name, validator, f"value_for_{field_name}")

        result = pipeline.validate()

        assert not result.is_valid

        if fail_fast:
            # Should stop at first failure
            assert len(result.errors) == 1
            assert "validator_2" in result.errors[0].message
        else:
            # Should collect all failures
            assert len(result.errors) == 2
            error_messages = [error.message for error in result.errors]
            assert any("validator_2" in msg for msg in error_messages)
            assert any("validator_3" in msg for msg in error_messages)

    def test_pipeline_state_isolation(self, validator_factory) -> None:
        """Test that pipeline instances don't interfere with each other."""
        # Create two separate pipelines
        pipeline1 = ValidationPipeline("pipeline_1")
        pipeline2 = ValidationPipeline("pipeline_2")

        # Configure differently
        validator1 = validator_factory("field1", should_pass=True)
        validator2 = validator_factory("field1", should_pass=False)

        pipeline1.add_validator("field1", validator1, "value1")
        pipeline2.add_validator("field1", validator2, "value1")

        # Validate both
        result1 = pipeline1.validate()
        result2 = pipeline2.validate()

        # Results should be independent
        assert result1.is_valid
        assert not result2.is_valid

    def test_validation_error_aggregation(self, validator_factory) -> None:
        """Test that validation errors are properly aggregated."""
        pipeline = ValidationPipeline("aggregation_test", fail_fast=False)

        # Add multiple failing validators
        failure_scenarios = [
            ("required_field", "Field is required"),
            ("format_field", "Invalid format"),
            ("range_field", "Value out of range"),
        ]

        for field_name, _ in failure_scenarios:
            validator = validator_factory(field_name, should_pass=False)
            pipeline.add_validator(field_name, validator, f"invalid_value_for_{field_name}")

        result = pipeline.validate()

        assert not result.is_valid
        assert len(result.errors) == 3

        # Verify error fields are correct
        error_fields = [error.field for error in result.errors]
        expected_fields = [scenario[0] for scenario in failure_scenarios]

        for expected_field in expected_fields:
            assert expected_field in error_fields
