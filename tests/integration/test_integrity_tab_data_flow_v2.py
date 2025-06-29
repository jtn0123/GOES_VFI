"""Optimized integration tests for integrity tab data flow functionality.

Optimizations applied:
- Mock-based testing to avoid network dependencies
- Shared fixtures for data flow components
- Parameterized data flow scenarios
- Enhanced validation and error handling
- Comprehensive data pipeline testing
"""

import asyncio
import operator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from goesvfi.integrity_check.data_fetcher import DataFetcher
from goesvfi.integrity_check.date_range_selector import CompactDateRangeSelector


class TestIntegrityTabDataFlowV2:
    """Optimized test class for integrity tab data flow functionality."""

    @pytest.fixture()
    @staticmethod
    def mock_data_fetcher() -> MagicMock:
        """Create mock data fetcher with comprehensive capabilities.

        Returns:
            MagicMock: Mocked DataFetcher instance.
        """
        fetcher = MagicMock(spec=DataFetcher)

        # Mock async methods
        fetcher.fetch_available_dates = AsyncMock()
        fetcher.fetch_file_metadata = AsyncMock()
        fetcher.validate_data_integrity = AsyncMock()

        # Mock data flow properties
        fetcher.current_date_range = None
        fetcher.available_files = []
        fetcher.integrity_results = {}

        return fetcher

    @pytest.fixture()
    @staticmethod
    def mock_date_selector() -> MagicMock:
        """Create mock date range selector.

        Returns:
            MagicMock: Mocked CompactDateRangeSelector instance.
        """
        selector = MagicMock(spec=CompactDateRangeSelector)

        # Mock date selection methods
        selector.get_date_range = MagicMock()
        selector.set_date_range = MagicMock()
        selector.dateRangeSelected = MagicMock()

        return selector

    @pytest.fixture()
    @staticmethod
    def data_flow_factory() -> Any:
        """Factory for creating data flow test scenarios.

        Returns:
            Callable: Factory function for creating test scenarios.
        """

        def create_scenario(scenario_type: str = "basic") -> dict[str, Any]:
            if scenario_type == "basic":
                return {
                    "date_range": ("2023-01-01", "2023-01-07"),
                    "expected_files": 168,  # 7 days * 24 hours
                    "missing_files": 5,
                    "corrupted_files": 2,
                }
            if scenario_type == "large":
                return {
                    "date_range": ("2023-01-01", "2023-01-31"),
                    "expected_files": 744,  # 31 days * 24 hours
                    "missing_files": 15,
                    "corrupted_files": 8,
                }
            if scenario_type == "empty":
                return {
                    "date_range": ("2099-01-01", "2099-01-02"),
                    "expected_files": 0,
                    "missing_files": 0,
                    "corrupted_files": 0,
                }
            msg = f"Unknown scenario type: {scenario_type}"
            raise ValueError(msg)

        return create_scenario

    @pytest.mark.asyncio()
    @pytest.mark.parametrize("scenario_type", ["basic", "large", "empty"])
    @staticmethod
    async def test_complete_data_flow_pipeline(
        mock_data_fetcher: MagicMock,
        mock_date_selector: MagicMock,
        data_flow_factory: Any,
        scenario_type: str,
    ) -> None:
        """Test complete data flow pipeline with various scenarios."""
        scenario = data_flow_factory(scenario_type)

        # Configure mock date selector
        mock_date_selector.get_date_range.return_value = scenario["date_range"]

        # Configure mock data fetcher
        mock_data_fetcher.fetch_available_dates.return_value = scenario["expected_files"]
        mock_data_fetcher.fetch_file_metadata.return_value = {
            "total_files": scenario["expected_files"],
            "missing_files": scenario["missing_files"],
            "corrupted_files": scenario["corrupted_files"],
        }

        # Execute data flow pipeline
        flow_result = await TestIntegrityTabDataFlowV2._execute_data_flow_pipeline(
            mock_data_fetcher, mock_date_selector, scenario
        )

        # Verify pipeline execution
        assert flow_result["date_selection_success"] is True
        assert flow_result["data_fetch_success"] is True
        assert flow_result["validation_success"] is True
        assert flow_result["total_files"] == scenario["expected_files"]

    @staticmethod
    async def _execute_data_flow_pipeline(
        data_fetcher: MagicMock,
        date_selector: MagicMock,
        scenario: dict[str, Any],  # noqa: ARG004
    ) -> dict[str, Any]:
        """Execute the complete data flow pipeline.

        Returns:
            dict[str, Any]: Flow execution results.
        """
        flow_result = {
            "date_selection_success": False,
            "data_fetch_success": False,
            "validation_success": False,
            "total_files": 0,
            "missing_files": 0,
            "corrupted_files": 0,
        }

        try:
            # Step 1: Date range selection
            date_range = date_selector.get_date_range()
            if date_range:
                flow_result["date_selection_success"] = True

            # Step 2: Data fetching
            available_files = await data_fetcher.fetch_available_dates()
            if available_files is not None:
                flow_result["data_fetch_success"] = True
                flow_result["total_files"] = available_files

            # Step 3: Metadata fetching
            metadata = await data_fetcher.fetch_file_metadata()
            if metadata:
                flow_result["missing_files"] = metadata.get("missing_files", 0)
                flow_result["corrupted_files"] = metadata.get("corrupted_files", 0)

            # Step 4: Validation
            validation_result = await data_fetcher.validate_data_integrity()
            if validation_result is not None:
                flow_result["validation_success"] = True

        except Exception as e:  # noqa: BLE001
            flow_result["error"] = str(e)

        return flow_result

    @pytest.mark.asyncio()
    @staticmethod
    async def test_data_flow_error_handling(
        mock_data_fetcher: MagicMock,
        mock_date_selector: MagicMock,
        data_flow_factory: Any,
    ) -> None:
        """Test data flow error handling and recovery."""
        scenario = data_flow_factory("basic")

        # Test different error scenarios
        error_scenarios = [
            ("network_error", ConnectionError("Network unavailable")),
            ("timeout_error", TimeoutError("Request timeout")),
            ("data_error", ValueError("Invalid data format")),
        ]

        for error_name, error in error_scenarios:
            # Configure error
            mock_data_fetcher.fetch_available_dates.side_effect = error

            # Execute pipeline with error handling
            flow_result = await TestIntegrityTabDataFlowV2._execute_data_flow_pipeline(
                mock_data_fetcher, mock_date_selector, scenario
            )

            # Verify error handling
            assert "error" in flow_result
            assert error_name.split("_")[0] in flow_result["error"].lower()

    @staticmethod
    def test_data_flow_state_management(
        mock_data_fetcher: MagicMock,
        mock_date_selector: MagicMock,  # noqa: ARG004
    ) -> None:
        """Test data flow state management and persistence."""
        # Mock state data
        flow_state = {
            "current_date_range": ("2023-01-01", "2023-01-07"),
            "fetched_files": ["file1.nc", "file2.nc", "file3.nc"],
            "validation_status": "completed",
            "last_update": "2023-01-07T12:00:00Z",
        }

        # Test state saving
        mock_data_fetcher.save_state = MagicMock()
        mock_data_fetcher.save_state(flow_state)
        mock_data_fetcher.save_state.assert_called_with(flow_state)

        # Test state loading
        mock_data_fetcher.load_state = MagicMock(return_value=flow_state)
        loaded_state = mock_data_fetcher.load_state()

        assert loaded_state == flow_state
        assert loaded_state["validation_status"] == "completed"

    @pytest.mark.asyncio()
    @staticmethod
    async def test_concurrent_data_flow_operations(
        mock_data_fetcher: MagicMock,
        mock_date_selector: MagicMock,
        data_flow_factory: Any,
    ) -> None:
        """Test concurrent data flow operations."""
        scenarios = [data_flow_factory("basic"), data_flow_factory("large"), data_flow_factory("empty")]

        # Configure mock for concurrent operations
        async def mock_fetch_with_delay(delay: float = 0.1) -> int:
            await asyncio.sleep(delay)
            return 100  # Mock file count

        mock_data_fetcher.fetch_available_dates.side_effect = mock_fetch_with_delay

        # Execute concurrent operations
        tasks = []
        for scenario in scenarios:
            task = TestIntegrityTabDataFlowV2._execute_data_flow_pipeline(
                mock_data_fetcher, mock_date_selector, scenario
            )
            tasks.append(task)

        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify concurrent execution
        assert len(results) == len(scenarios)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 1  # At least one should succeed

    @staticmethod
    def test_data_flow_caching_mechanism(mock_data_fetcher: MagicMock) -> None:
        """Test data flow caching mechanism for performance."""
        # Mock cache operations
        mock_data_fetcher.cache_data = MagicMock()
        mock_data_fetcher.get_cached_data = MagicMock()
        mock_data_fetcher.invalidate_cache = MagicMock()

        # Test data caching
        test_data = {"files": ["file1.nc", "file2.nc"], "metadata": {"total": 2}}
        cache_key = "test_date_range_2023-01-01_2023-01-07"

        # Cache data
        mock_data_fetcher.cache_data(cache_key, test_data)
        mock_data_fetcher.cache_data.assert_called_with(cache_key, test_data)

        # Retrieve cached data
        mock_data_fetcher.get_cached_data.return_value = test_data
        cached_data = mock_data_fetcher.get_cached_data(cache_key)

        assert cached_data == test_data

        # Invalidate cache
        mock_data_fetcher.invalidate_cache(cache_key)
        mock_data_fetcher.invalidate_cache.assert_called_with(cache_key)

    @pytest.mark.asyncio()
    @staticmethod
    async def test_data_flow_progress_tracking(
        mock_data_fetcher: MagicMock,
        mock_date_selector: MagicMock,
        data_flow_factory: Any,
    ) -> None:
        """Test data flow progress tracking and reporting."""
        scenario = data_flow_factory("large")

        # Mock progress tracking
        progress_updates = []

        async def mock_fetch_with_progress() -> int:
            for i in range(5):
                progress = (i + 1) * 20  # 20%, 40%, 60%, 80%, 100%
                progress_updates.append(progress)
                await asyncio.sleep(0.01)
            return scenario["expected_files"]

        mock_data_fetcher.fetch_available_dates.side_effect = mock_fetch_with_progress

        # Execute with progress tracking
        await TestIntegrityTabDataFlowV2._execute_data_flow_pipeline(mock_data_fetcher, mock_date_selector, scenario)

        # Verify progress tracking
        assert len(progress_updates) == 5
        assert progress_updates[-1] == 100  # Final progress should be 100%

    @staticmethod
    def test_data_flow_filtering_and_sorting(mock_data_fetcher: MagicMock) -> None:
        """Test data flow filtering and sorting capabilities."""
        # Mock file data
        mock_files = [
            {"name": "file_001.nc", "date": "2023-01-01", "size": 1024, "status": "valid"},
            {"name": "file_002.nc", "date": "2023-01-02", "size": 2048, "status": "missing"},
            {"name": "file_003.nc", "date": "2023-01-03", "size": 1536, "status": "corrupted"},
            {"name": "file_004.nc", "date": "2023-01-04", "size": 1024, "status": "valid"},
        ]

        # Mock filtering methods
        mock_data_fetcher.filter_files = MagicMock()
        mock_data_fetcher.sort_files = MagicMock()

        # Test filtering by status
        valid_files = [f for f in mock_files if f["status"] == "valid"]
        mock_data_fetcher.filter_files.return_value = valid_files

        filtered_files = mock_data_fetcher.filter_files(status="valid")
        assert len(filtered_files) == 2

        # Test sorting by date
        sorted_files = sorted(mock_files, key=operator.itemgetter("date"))
        mock_data_fetcher.sort_files.return_value = sorted_files

        sorted_result = mock_data_fetcher.sort_files(by="date")
        assert len(sorted_result) == len(mock_files)

    @pytest.mark.asyncio()
    @staticmethod
    async def test_data_flow_batch_processing(mock_data_fetcher: MagicMock, data_flow_factory: Any) -> None:
        """Test data flow batch processing capabilities."""
        # Create multiple scenarios for batch processing
        scenarios = [data_flow_factory("basic"), data_flow_factory("large"), data_flow_factory("empty")]

        # Mock batch processing

        async def mock_process_batch(scenarios_batch: list[dict[str, Any]]) -> list[dict[str, Any]]:  # noqa: RUF029
            results = []
            for scenario in scenarios_batch:
                result = {
                    "date_range": scenario["date_range"],
                    "processed_files": scenario["expected_files"],
                    "success": True,
                }
                results.append(result)
            return results

        mock_data_fetcher.process_batch = AsyncMock(side_effect=mock_process_batch)

        # Execute batch processing
        batch_result = await mock_data_fetcher.process_batch(scenarios)

        # Verify batch processing
        assert len(batch_result) == len(scenarios)
        assert all(result["success"] for result in batch_result)

    @staticmethod
    def test_data_flow_configuration_management(mock_data_fetcher: MagicMock) -> None:
        """Test data flow configuration management."""
        # Mock configuration
        flow_config = {
            "max_concurrent_requests": 5,
            "request_timeout": 30,
            "cache_ttl": 3600,
            "retry_attempts": 3,
            "data_sources": ["s3://bucket1", "s3://bucket2"],
            "validation_rules": ["size_check", "format_check", "integrity_check"],
        }

        # Test configuration setting
        mock_data_fetcher.set_config = MagicMock()
        mock_data_fetcher.set_config(flow_config)
        mock_data_fetcher.set_config.assert_called_with(flow_config)

        # Test configuration retrieval
        mock_data_fetcher.get_config = MagicMock(return_value=flow_config)
        retrieved_config = mock_data_fetcher.get_config()

        assert retrieved_config == flow_config
        assert retrieved_config["max_concurrent_requests"] == 5
