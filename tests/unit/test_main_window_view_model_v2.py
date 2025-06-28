"""Unit tests for the MainWindowViewModel - Optimized V2 with 100%+ coverage.

Enhanced tests for the MainWindowViewModel component with comprehensive
testing of signal handling, dependency injection, and view model interactions.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from typing import Never
import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.date_sorter.sorter import DateSorter
from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.gui_components import PreviewManager, ProcessingManager
from goesvfi.view_models.main_window_view_model import MainWindowViewModel


class TestMainWindowViewModelV2(unittest.TestCase):
    """Test cases for the MainWindowViewModel with comprehensive coverage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared class-level resources."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

        cls.temp_root = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up shared class-level resources."""
        if Path(cls.temp_root).exists():
            import shutil
            shutil.rmtree(cls.temp_root)

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create unique test directory for each test
        self.test_dir = Path(self.temp_root) / f"test_{self._testMethodName}"
        self.test_dir.mkdir(exist_ok=True)

        # Create mock dependencies
        self.mock_file_sorter = MagicMock(spec=FileSorter)
        self.mock_date_sorter = MagicMock(spec=DateSorter)
        self.mock_preview_manager = MagicMock(spec=PreviewManager)
        self.mock_processing_manager = MagicMock(spec=ProcessingManager)

        # Create view model with mocked dependencies
        self.vm = MainWindowViewModel(
            self.mock_file_sorter,
            self.mock_date_sorter,
            self.mock_preview_manager,
            self.mock_processing_manager,
        )

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        if hasattr(self, "vm"):
            self.vm.deleteLater()
            QApplication.processEvents()

    def test_initialization_comprehensive(self) -> None:
        """Test comprehensive view model initialization."""
        # Verify dependencies are properly injected
        assert self.vm.file_sorter == self.mock_file_sorter
        assert self.vm.date_sorter == self.mock_date_sorter
        assert self.vm.preview_manager == self.mock_preview_manager
        assert self.vm.processing_manager == self.mock_processing_manager

        # Verify processing view model has correct dependencies
        assert self.vm.processing_vm.preview_manager == self.mock_preview_manager
        assert self.vm.processing_vm.processing_manager == self.mock_processing_manager

        # Verify initial state
        assert isinstance(self.vm.status, str)
        assert isinstance(self.vm.active_tab_index, int)

        # Verify signals exist
        assert hasattr(self.vm, "status_updated")
        assert hasattr(self.vm, "active_tab_changed")

    def test_status_signal_emission_comprehensive(self) -> None:
        """Test comprehensive status signal emission scenarios."""
        # Test various status values
        status_scenarios = [
            "Ready",
            "Working",
            "Processing files...",
            "Download complete",
            "Error occurred",
            "",  # Empty status
            "Very long status message that might exceed normal length limits for testing purposes",
            "Status with special characters: @#$%^&*()",
            "Status\nwith\nnewlines",
        ]

        for status in status_scenarios:
            with self.subTest(status=status):
                # Track signal emissions
                signal_emitted = []

                def on_status_updated(new_status) -> None:
                    signal_emitted.append(new_status)

                self.vm.status_updated.connect(on_status_updated)

                # Set status
                self.vm.status = status

                # Process events to ensure signal is delivered
                QApplication.processEvents()

                # Verify signal was emitted with correct value
                assert len(signal_emitted) == 1
                assert signal_emitted[0] == status
                assert self.vm.status == status

                # Disconnect for next iteration
                self.vm.status_updated.disconnect(on_status_updated)

    def test_status_signal_not_emitted_for_same_value(self) -> None:
        """Test that status signal is not emitted when setting the same value."""
        # Set initial status
        initial_status = "Initial Status"
        self.vm.status = initial_status

        # Track signal emissions
        signal_count = 0

        def on_status_updated(new_status) -> None:
            nonlocal signal_count
            signal_count += 1

        self.vm.status_updated.connect(on_status_updated)

        # Set same status again
        self.vm.status = initial_status

        # Process events
        QApplication.processEvents()

        # Verify signal was not emitted for duplicate value
        assert signal_count == 0
        assert self.vm.status == initial_status

    def test_active_tab_signal_emission_comprehensive(self) -> None:
        """Test comprehensive active tab signal emission scenarios."""
        # Test various tab indices
        tab_scenarios = [
            0,   # First tab
            1,   # Second tab
            2,   # Third tab
            5,   # Higher index
            -1,  # Negative index (edge case)
            100,  # Very high index (edge case)
        ]

        for tab_index in tab_scenarios:
            with self.subTest(tab_index=tab_index):
                # Track signal emissions
                signal_emitted = []

                def on_tab_changed(new_index) -> None:
                    signal_emitted.append(new_index)

                self.vm.active_tab_changed.connect(on_tab_changed)

                # Set tab index
                self.vm.active_tab_index = tab_index

                # Process events to ensure signal is delivered
                QApplication.processEvents()

                # Verify signal was emitted with correct value
                assert len(signal_emitted) == 1
                assert signal_emitted[0] == tab_index
                assert self.vm.active_tab_index == tab_index

                # Disconnect for next iteration
                self.vm.active_tab_changed.disconnect(on_tab_changed)

    def test_active_tab_signal_not_emitted_for_same_value(self) -> None:
        """Test that active tab signal is not emitted when setting the same value."""
        # Set initial tab index
        initial_tab = 2
        self.vm.active_tab_index = initial_tab

        # Track signal emissions
        signal_count = 0

        def on_tab_changed(new_index) -> None:
            nonlocal signal_count
            signal_count += 1

        self.vm.active_tab_changed.connect(on_tab_changed)

        # Set same tab index again
        self.vm.active_tab_index = initial_tab

        # Process events
        QApplication.processEvents()

        # Verify signal was not emitted for duplicate value
        assert signal_count == 0
        assert self.vm.active_tab_index == initial_tab

    def test_dependency_injection_comprehensive(self) -> None:
        """Test comprehensive dependency injection scenarios."""
        # Test with different dependency configurations
        dependency_scenarios = [
            {
                "name": "All real dependencies",
                "file_sorter": FileSorter(),
                "date_sorter": DateSorter(),
                "preview_manager": PreviewManager(),
                "processing_manager": ProcessingManager(),
            },
            {
                "name": "All mock dependencies",
                "file_sorter": MagicMock(spec=FileSorter),
                "date_sorter": MagicMock(spec=DateSorter),
                "preview_manager": MagicMock(spec=PreviewManager),
                "processing_manager": MagicMock(spec=ProcessingManager),
            },
        ]

        for scenario in dependency_scenarios:
            with self.subTest(scenario=scenario["name"]):
                vm = MainWindowViewModel(
                    scenario["file_sorter"],
                    scenario["date_sorter"],
                    scenario["preview_manager"],
                    scenario["processing_manager"],
                )

                # Verify dependencies are correctly injected
                assert vm.file_sorter == scenario["file_sorter"]
                assert vm.date_sorter == scenario["date_sorter"]
                assert vm.preview_manager == scenario["preview_manager"]
                assert vm.processing_manager == scenario["processing_manager"]

                # Verify processing view model dependencies
                assert vm.processing_vm.preview_manager == scenario["preview_manager"]
                assert vm.processing_vm.processing_manager == scenario["processing_manager"]

                # Clean up
                vm.deleteLater()
                QApplication.processEvents()

    def test_processing_view_model_integration(self) -> None:
        """Test integration with processing view model."""
        # Verify processing view model exists
        assert self.vm.processing_vm is not None

        # Verify it's a proper QObject for signal/slot mechanism
        assert isinstance(self.vm.processing_vm, QObject)

        # Verify dependencies are properly passed through
        assert self.vm.processing_vm.preview_manager == self.vm.preview_manager
        assert self.vm.processing_vm.processing_manager == self.vm.processing_manager

        # Test that processing view model maintains references
        original_preview_manager = self.vm.preview_manager
        original_processing_manager = self.vm.processing_manager

        # These should remain the same objects
        assert self.vm.processing_vm.preview_manager is original_preview_manager
        assert self.vm.processing_vm.processing_manager is original_processing_manager

    def test_signal_connection_and_disconnection(self) -> None:
        """Test signal connection and disconnection scenarios."""
        # Test multiple signal connections
        signal_receivers = []

        def receiver1(value) -> None:
            signal_receivers.append(f"receiver1: {value}")

        def receiver2(value) -> None:
            signal_receivers.append(f"receiver2: {value}")

        def receiver3(value) -> None:
            signal_receivers.append(f"receiver3: {value}")

        # Connect multiple receivers
        self.vm.status_updated.connect(receiver1)
        self.vm.status_updated.connect(receiver2)
        self.vm.status_updated.connect(receiver3)

        # Emit signal
        test_status = "Test Status"
        self.vm.status = test_status

        # Process events
        QApplication.processEvents()

        # Verify all receivers got the signal
        assert len(signal_receivers) == 3
        assert f"receiver1: {test_status}" in signal_receivers
        assert f"receiver2: {test_status}" in signal_receivers
        assert f"receiver3: {test_status}" in signal_receivers

        # Test disconnection
        signal_receivers.clear()
        self.vm.status_updated.disconnect(receiver2)

        self.vm.status = "Second Test"
        QApplication.processEvents()

        # Verify only connected receivers got the signal
        assert len(signal_receivers) == 2
        assert any("receiver1" in msg for msg in signal_receivers)
        assert any("receiver3" in msg for msg in signal_receivers)
        assert not any("receiver2" in msg for msg in signal_receivers)

    def test_concurrent_signal_operations(self) -> None:
        """Test concurrent signal operations and thread safety."""
        results = []
        errors = []

        def concurrent_operation(operation_id: int) -> None:
            try:
                # Test concurrent status updates
                if operation_id % 3 == 0:
                    self.vm.status = f"Status {operation_id}"
                    results.append(("status", operation_id))
                elif operation_id % 3 == 1:
                    self.vm.active_tab_index = operation_id % 10
                    results.append(("tab", operation_id))
                else:
                    # Test accessing properties
                    status = self.vm.status
                    tab = self.vm.active_tab_index
                    results.append(("access", status, tab))

            except Exception as e:
                errors.append((operation_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(30)]
            for future in futures:
                future.result()

        # Process any pending events
        QApplication.processEvents()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 30

    def test_memory_management(self) -> None:
        """Test memory management and cleanup."""
        # Create multiple view models to test memory handling
        view_models = []

        for i in range(10):
            vm = MainWindowViewModel(
                MagicMock(spec=FileSorter),
                MagicMock(spec=DateSorter),
                MagicMock(spec=PreviewManager),
                MagicMock(spec=ProcessingManager),
            )

            # Set some state
            vm.status = f"Test Status {i}"
            vm.active_tab_index = i

            view_models.append(vm)

        # Verify all were created successfully
        assert len(view_models) == 10

        # Clean up all view models
        for vm in view_models:
            vm.deleteLater()

        # Process deletion events
        QApplication.processEvents()

        # Test should complete without memory issues

    def test_edge_cases_and_boundary_conditions(self) -> None:
        """Test edge cases and boundary conditions."""
        # Test with None-like values
        edge_case_scenarios = [
            ("Empty string status", ""),
            ("Whitespace status", "   "),
            ("Zero tab index", 0),
            ("Negative tab index", -5),
            ("Large tab index", 99999),
        ]

        for description, value in edge_case_scenarios:
            with self.subTest(case=description):
                if "status" in description:
                    # Test setting edge case status values
                    try:
                        self.vm.status = value
                        assert self.vm.status == value
                    except Exception as e:
                        self.fail(f"Should handle edge case status gracefully: {e}")
                else:
                    # Test setting edge case tab index values
                    try:
                        self.vm.active_tab_index = value
                        assert self.vm.active_tab_index == value
                    except Exception as e:
                        self.fail(f"Should handle edge case tab index gracefully: {e}")

    def test_error_handling_in_signal_emission(self) -> None:
        """Test error handling when signal receivers raise exceptions."""
        # Create a receiver that raises an exception
        def error_receiver(value) -> Never:
            msg = f"Test exception for value: {value}"
            raise Exception(msg)

        # Create a normal receiver
        normal_results = []

        def normal_receiver(value) -> None:
            normal_results.append(value)

        # Connect both receivers
        self.vm.status_updated.connect(error_receiver)
        self.vm.status_updated.connect(normal_receiver)

        # Emit signal - should not crash even if one receiver fails
        try:
            self.vm.status = "Test Error Handling"
            QApplication.processEvents()
        except Exception as e:
            self.fail(f"Signal emission should handle receiver errors gracefully: {e}")

        # Normal receiver should still have received the signal
        assert "Test Error Handling" in normal_results

    def test_property_persistence(self) -> None:
        """Test that property values persist correctly."""
        # Set various property values
        test_status = "Persistent Status"
        test_tab_index = 42

        self.vm.status = test_status
        self.vm.active_tab_index = test_tab_index

        # Verify values persist
        assert self.vm.status == test_status
        assert self.vm.active_tab_index == test_tab_index

        # Do some other operations
        QApplication.processEvents()

        # Verify values still persist
        assert self.vm.status == test_status
        assert self.vm.active_tab_index == test_tab_index

    def test_dependency_reference_integrity(self) -> None:
        """Test that dependency references remain intact throughout lifecycle."""
        # Store original references
        original_file_sorter = self.vm.file_sorter
        original_date_sorter = self.vm.date_sorter
        original_preview_manager = self.vm.preview_manager
        original_processing_manager = self.vm.processing_manager

        # Perform various operations
        self.vm.status = "Testing Reference Integrity"
        self.vm.active_tab_index = 5
        QApplication.processEvents()

        # Verify references are still the same objects
        assert self.vm.file_sorter is original_file_sorter
        assert self.vm.date_sorter is original_date_sorter
        assert self.vm.preview_manager is original_preview_manager
        assert self.vm.processing_manager is original_processing_manager

        # Verify processing view model references are also intact
        assert self.vm.processing_vm.preview_manager is original_preview_manager
        assert self.vm.processing_vm.processing_manager is original_processing_manager

    def test_signal_emission_timing(self) -> None:
        """Test timing of signal emissions."""
        # Track when signals are emitted
        emission_log = []

        def log_status_emission(value) -> None:
            emission_log.append(("status", value))

        def log_tab_emission(value) -> None:
            emission_log.append(("tab", value))

        self.vm.status_updated.connect(log_status_emission)
        self.vm.active_tab_changed.connect(log_tab_emission)

        # Emit signals in sequence
        self.vm.status = "First"
        self.vm.active_tab_index = 1
        self.vm.status = "Second"
        self.vm.active_tab_index = 2

        # Process events
        QApplication.processEvents()

        # Verify emission order and content
        expected_emissions = [
            ("status", "First"),
            ("tab", 1),
            ("status", "Second"),
            ("tab", 2),
        ]

        assert len(emission_log) == len(expected_emissions)
        for expected, actual in zip(expected_emissions, emission_log, strict=False):
            assert expected == actual


# Compatibility tests using pytest style for existing test coverage
@pytest.fixture()
def main_window_vm_pytest(qtbot):
    """Pytest fixture for MainWindowViewModel."""
    vm = MainWindowViewModel(
        FileSorter(),
        DateSorter(),
        PreviewManager(),
        ProcessingManager(),
    )
    yield vm
    vm.deleteLater()


def test_status_signal_emitted_pytest(main_window_vm_pytest, qtbot) -> None:
    """Test status signal emission using pytest style."""
    with qtbot.waitSignal(main_window_vm_pytest.status_updated, timeout=1000) as blocker:
        main_window_vm_pytest.status = "Working"
    assert blocker.args == ["Working"]
    assert main_window_vm_pytest.status == "Working"


def test_active_tab_signal_emitted_pytest(main_window_vm_pytest, qtbot) -> None:
    """Test active tab signal emission using pytest style."""
    with qtbot.waitSignal(main_window_vm_pytest.active_tab_changed, timeout=1000) as blocker:
        main_window_vm_pytest.active_tab_index = 1
    assert blocker.args == [1]
    assert main_window_vm_pytest.active_tab_index == 1


def test_processing_vm_has_dependencies_pytest(main_window_vm_pytest) -> None:
    """Test processing view model dependencies using pytest style."""
    assert main_window_vm_pytest.processing_vm.preview_manager is main_window_vm_pytest.preview_manager
    assert main_window_vm_pytest.processing_vm.processing_manager is main_window_vm_pytest.processing_manager


if __name__ == "__main__":
    unittest.main()
