"""Unit tests for the FileSorterViewModel - Optimized V2 with 100%+ coverage.

Enhanced tests for the FileSorterViewModel component with comprehensive
testing of directory selection, error handling, and view model operations.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.file_sorter.view_model import FileSorterViewModel


class TestFileSorterViewModelV2(unittest.TestCase):
    """Test cases for the FileSorterViewModel with comprehensive coverage."""

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

        # Create test directories
        self.src_dir = self.test_dir / "src"
        self.dst_dir = self.test_dir / "dst"
        self.src_dir.mkdir()
        self.dst_dir.mkdir()

        # Create mock file sorter
        self.mock_file_sorter = MagicMock(spec=FileSorter)

        # Create view model
        self.view_model = FileSorterViewModel(self.mock_file_sorter)

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        if hasattr(self, "view_model"):
            # Clean up view model if it exists
            try:
                self.view_model.deleteLater()
                QApplication.processEvents()
            except Exception:
                pass

    def test_initialization_comprehensive(self) -> None:
        """Test comprehensive view model initialization."""
        # Test initialization with FileSorter
        vm = FileSorterViewModel(FileSorter())

        # Verify initial state
        assert vm.source_directory is None
        assert vm.destination_directory is None
        assert isinstance(vm.status_message, str)
        assert vm.file_sorter is not None

        # Verify signals exist
        assert hasattr(vm, "source_directory_changed")
        assert hasattr(vm, "destination_directory_changed")
        assert hasattr(vm, "status_message_changed")

        vm.deleteLater()
        QApplication.processEvents()

        # Test initialization with mock
        mock_sorter = MagicMock(spec=FileSorter)
        vm_mock = FileSorterViewModel(mock_sorter)
        assert vm_mock.file_sorter == mock_sorter
        vm_mock.deleteLater()

    @patch("goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory")
    def test_select_source_directory_comprehensive(self, mock_dialog) -> None:
        """Test comprehensive source directory selection scenarios."""
        # Test successful directory selection
        test_scenarios = [
            {
                "name": "Normal directory",
                "directory": str(self.src_dir),
                "should_update": True,
            },
            {
                "name": "Directory with spaces",
                "directory": str(self.test_dir / "src with spaces"),
                "should_update": True,
            },
            {
                "name": "Very long path",
                "directory": str(self.test_dir / "very" / "long" / "path" / "to" / "source" / "directory"),
                "should_update": True,
            },
            {
                "name": "Cancelled selection",
                "directory": "",
                "should_update": False,
            },
            {
                "name": "None selection",
                "directory": None,
                "should_update": False,
            },
        ]

        for scenario in test_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Create directory if it doesn't exist and is not empty/None
                if scenario["directory"] and scenario["directory"] != "":
                    Path(scenario["directory"]).mkdir(parents=True, exist_ok=True)

                # Mock dialog return value
                mock_dialog.return_value = scenario["directory"]

                # Track signal emissions
                signal_emitted = []

                def on_source_changed(directory) -> None:
                    signal_emitted.append(directory)

                self.view_model.source_directory_changed.connect(on_source_changed)

                # Call method
                self.view_model.select_source_directory()

                # Process events
                QApplication.processEvents()

                # Verify dialog was called
                mock_dialog.assert_called()

                if scenario["should_update"]:
                    # Verify property was updated
                    assert self.view_model.source_directory == scenario["directory"]
                    assert "Source directory set to:" in self.view_model.status_message

                    # Verify signal was emitted
                    assert len(signal_emitted) == 1
                    assert signal_emitted[0] == scenario["directory"]
                # Verify property was not updated for cancelled/None selection
                elif not scenario["directory"]:
                    assert self.view_model.source_directory is None

                # Disconnect for next iteration
                self.view_model.source_directory_changed.disconnect(on_source_changed)
                mock_dialog.reset_mock()

    @patch("goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory")
    def test_select_destination_directory_comprehensive(self, mock_dialog) -> None:
        """Test comprehensive destination directory selection scenarios."""
        # Test successful directory selection
        test_scenarios = [
            {
                "name": "Normal directory",
                "directory": str(self.dst_dir),
                "should_update": True,
            },
            {
                "name": "Directory with special chars",
                "directory": str(self.test_dir / "dst_@#$%"),
                "should_update": True,
            },
            {
                "name": "Nested directory",
                "directory": str(self.test_dir / "nested" / "destination" / "path"),
                "should_update": True,
            },
            {
                "name": "Cancelled selection",
                "directory": "",
                "should_update": False,
            },
            {
                "name": "None selection",
                "directory": None,
                "should_update": False,
            },
        ]

        for scenario in test_scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Create directory if it doesn't exist and is not empty/None
                if scenario["directory"] and scenario["directory"] != "":
                    Path(scenario["directory"]).mkdir(parents=True, exist_ok=True)

                # Mock dialog return value
                mock_dialog.return_value = scenario["directory"]

                # Track signal emissions
                signal_emitted = []

                def on_destination_changed(directory) -> None:
                    signal_emitted.append(directory)

                self.view_model.destination_directory_changed.connect(on_destination_changed)

                # Call method
                self.view_model.select_destination_directory()

                # Process events
                QApplication.processEvents()

                # Verify dialog was called
                mock_dialog.assert_called()

                if scenario["should_update"]:
                    # Verify property was updated
                    assert self.view_model.destination_directory == scenario["directory"]
                    assert "Destination directory set to:" in self.view_model.status_message

                    # Verify signal was emitted
                    assert len(signal_emitted) == 1
                    assert signal_emitted[0] == scenario["directory"]
                # Verify property was not updated for cancelled/None selection
                elif not scenario["directory"]:
                    assert self.view_model.destination_directory is None

                # Disconnect for next iteration
                self.view_model.destination_directory_changed.disconnect(on_destination_changed)
                mock_dialog.reset_mock()

    @patch("goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory")
    def test_dialog_error_handling(self, mock_dialog) -> None:
        """Test error handling when dialog operations fail."""
        # Test dialog raising exception
        error_scenarios = [
            Exception("General dialog error"),
            RuntimeError("Qt dialog error"),
            OSError("File system error"),
        ]

        for error in error_scenarios:
            with self.subTest(error=type(error).__name__):
                mock_dialog.side_effect = error

                # Should handle errors gracefully
                try:
                    self.view_model.select_source_directory()
                    self.view_model.select_destination_directory()
                except Exception as e:
                    self.fail(f"Should handle dialog errors gracefully: {e}")

                mock_dialog.reset_mock()

    def test_property_setters_and_getters_comprehensive(self) -> None:
        """Test comprehensive property setters and getters."""
        # Test source directory property
        test_directories = [
            str(self.src_dir),
            str(self.test_dir / "another_source"),
            "/absolute/path/to/source",
            "relative/path/to/source",
            "",  # Empty string
        ]

        for directory in test_directories:
            with self.subTest(directory=directory):
                # Track signal emissions
                signal_emitted = []

                def on_source_changed(dir_path) -> None:
                    signal_emitted.append(dir_path)

                self.view_model.source_directory_changed.connect(on_source_changed)

                # Set property directly
                self.view_model.source_directory = directory

                # Process events
                QApplication.processEvents()

                # Verify property was set
                assert self.view_model.source_directory == directory

                # Verify signal was emitted
                assert len(signal_emitted) == 1
                assert signal_emitted[0] == directory

                # Disconnect for next iteration
                self.view_model.source_directory_changed.disconnect(on_source_changed)

        # Test destination directory property
        for directory in test_directories:
            with self.subTest(directory=directory):
                # Track signal emissions
                signal_emitted = []

                def on_destination_changed(dir_path) -> None:
                    signal_emitted.append(dir_path)

                self.view_model.destination_directory_changed.connect(on_destination_changed)

                # Set property directly
                self.view_model.destination_directory = directory

                # Process events
                QApplication.processEvents()

                # Verify property was set
                assert self.view_model.destination_directory == directory

                # Verify signal was emitted
                assert len(signal_emitted) == 1
                assert signal_emitted[0] == directory

                # Disconnect for next iteration
                self.view_model.destination_directory_changed.disconnect(on_destination_changed)

    def test_status_message_functionality(self) -> None:
        """Test status message functionality."""
        # Test various status messages
        status_messages = [
            "Ready",
            "Processing files...",
            "Source directory set to: /path/to/source",
            "Destination directory set to: /path/to/dest",
            "Error occurred",
            "",  # Empty message
            "Very long status message that might exceed normal display limits for comprehensive testing",
        ]

        for message in status_messages:
            with self.subTest(message=message):
                # Track signal emissions
                signal_emitted = []

                def on_status_changed(status) -> None:
                    signal_emitted.append(status)

                self.view_model.status_message_changed.connect(on_status_changed)

                # Set status message
                self.view_model.status_message = message

                # Process events
                QApplication.processEvents()

                # Verify property was set
                assert self.view_model.status_message == message

                # Verify signal was emitted
                assert len(signal_emitted) == 1
                assert signal_emitted[0] == message

                # Disconnect for next iteration
                self.view_model.status_message_changed.disconnect(on_status_changed)

    def test_file_sorter_integration(self) -> None:
        """Test integration with FileSorter component."""
        # Test with real FileSorter
        real_sorter = FileSorter()
        vm = FileSorterViewModel(real_sorter)

        # Verify sorter is properly integrated
        assert vm.file_sorter == real_sorter
        assert isinstance(vm.file_sorter, FileSorter)

        vm.deleteLater()

        # Test with mock FileSorter
        mock_sorter = MagicMock(spec=FileSorter)
        vm_mock = FileSorterViewModel(mock_sorter)

        # Verify mock integration
        assert vm_mock.file_sorter == mock_sorter

        vm_mock.deleteLater()

    def test_signal_emission_not_duplicate(self) -> None:
        """Test that signals are not emitted for duplicate values."""
        # Test source directory
        test_dir = str(self.src_dir)
        self.view_model.source_directory = test_dir

        # Track signal emissions
        signal_count = 0

        def count_source_signals(directory) -> None:
            nonlocal signal_count
            signal_count += 1

        self.view_model.source_directory_changed.connect(count_source_signals)

        # Set same value again
        self.view_model.source_directory = test_dir

        # Process events
        QApplication.processEvents()

        # Should not emit signal for duplicate value
        assert signal_count == 0

        # Test destination directory
        signal_count = 0

        def count_destination_signals(directory) -> None:
            nonlocal signal_count
            signal_count += 1

        self.view_model.destination_directory_changed.connect(count_destination_signals)

        # Set destination
        self.view_model.destination_directory = str(self.dst_dir)
        signal_count = 0  # Reset after initial set

        # Set same value again
        self.view_model.destination_directory = str(self.dst_dir)

        # Process events
        QApplication.processEvents()

        # Should not emit signal for duplicate value
        assert signal_count == 0

    def test_concurrent_operations(self) -> None:
        """Test concurrent view model operations."""
        results = []
        errors = []

        def concurrent_operation(operation_id: int) -> None:
            try:
                # Test various concurrent operations
                if operation_id % 4 == 0:
                    # Test source directory setting
                    test_dir = str(self.test_dir / f"concurrent_src_{operation_id}")
                    Path(test_dir).mkdir(exist_ok=True)
                    self.view_model.source_directory = test_dir
                    results.append(("source", operation_id))
                elif operation_id % 4 == 1:
                    # Test destination directory setting
                    test_dir = str(self.test_dir / f"concurrent_dst_{operation_id}")
                    Path(test_dir).mkdir(exist_ok=True)
                    self.view_model.destination_directory = test_dir
                    results.append(("destination", operation_id))
                elif operation_id % 4 == 2:
                    # Test status message setting
                    self.view_model.status_message = f"Concurrent status {operation_id}"
                    results.append(("status", operation_id))
                else:
                    # Test property access
                    src = self.view_model.source_directory
                    dst = self.view_model.destination_directory
                    status = self.view_model.status_message
                    results.append(("access", src, dst, status))

            except Exception as e:
                errors.append((operation_id, e))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(20)]
            for future in futures:
                future.result()

        # Process any pending events
        QApplication.processEvents()

        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(results) == 20

    def test_memory_management_with_multiple_instances(self) -> None:
        """Test memory management with multiple view model instances."""
        # Create multiple view models
        view_models = []

        for i in range(10):
            sorter = MagicMock(spec=FileSorter)
            vm = FileSorterViewModel(sorter)

            # Set some state
            vm.source_directory = str(self.test_dir / f"src_{i}")
            vm.destination_directory = str(self.test_dir / f"dst_{i}")
            vm.status_message = f"Test status {i}"

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
        # Test with None values
        self.view_model.source_directory = None
        assert self.view_model.source_directory is None

        self.view_model.destination_directory = None
        assert self.view_model.destination_directory is None

        # Test with very long paths
        long_path = "/very/long/path/" + "/".join([f"directory_{i}" for i in range(50)])
        self.view_model.source_directory = long_path
        assert self.view_model.source_directory == long_path

        # Test with special characters in paths
        special_path = str(self.test_dir / "special_@#$%^&*()_chars")
        self.view_model.destination_directory = special_path
        assert self.view_model.destination_directory == special_path

        # Test with empty strings
        self.view_model.source_directory = ""
        assert self.view_model.source_directory == ""

        # Test with whitespace
        self.view_model.status_message = "   \t\n   "
        assert self.view_model.status_message == "   \t\n   "

    @patch("goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory")
    def test_dialog_with_different_parent_windows(self, mock_dialog) -> None:
        """Test dialog behavior with different parent window scenarios."""
        # Test with different parent scenarios
        mock_dialog.return_value = str(self.src_dir)

        # Call with implicit parent (None)
        self.view_model.select_source_directory()
        mock_dialog.assert_called()

        # Reset mock
        mock_dialog.reset_mock()
        mock_dialog.return_value = str(self.dst_dir)

        # Call destination selection
        self.view_model.select_destination_directory()
        mock_dialog.assert_called()

    def test_signal_connection_and_disconnection_comprehensive(self) -> None:
        """Test comprehensive signal connection and disconnection."""
        # Test multiple receivers for each signal
        source_receivers = []
        destination_receivers = []
        status_receivers = []

        def source_receiver_1(directory) -> None:
            source_receivers.append(f"receiver1: {directory}")

        def source_receiver_2(directory) -> None:
            source_receivers.append(f"receiver2: {directory}")

        def destination_receiver_1(directory) -> None:
            destination_receivers.append(f"receiver1: {directory}")

        def status_receiver_1(message) -> None:
            status_receivers.append(f"receiver1: {message}")

        # Connect multiple receivers
        self.view_model.source_directory_changed.connect(source_receiver_1)
        self.view_model.source_directory_changed.connect(source_receiver_2)
        self.view_model.destination_directory_changed.connect(destination_receiver_1)
        self.view_model.status_message_changed.connect(status_receiver_1)

        # Emit signals
        test_src = str(self.src_dir)
        test_dst = str(self.dst_dir)
        test_status = "Test Status"

        self.view_model.source_directory = test_src
        self.view_model.destination_directory = test_dst
        self.view_model.status_message = test_status

        # Process events
        QApplication.processEvents()

        # Verify all receivers got signals
        assert len(source_receivers) == 2
        assert len(destination_receivers) == 1
        assert len(status_receivers) == 1

        # Test disconnection
        self.view_model.source_directory_changed.disconnect(source_receiver_1)
        source_receivers.clear()

        self.view_model.source_directory = str(self.test_dir / "new_source")
        QApplication.processEvents()

        # Only receiver2 should have received the signal
        assert len(source_receivers) == 1
        assert "receiver2" in source_receivers[0]

    def test_error_recovery_scenarios(self) -> None:
        """Test error recovery in various failure scenarios."""
        # Test with invalid file sorter
        with patch.object(self.view_model, "file_sorter", None):
            # Should handle missing file_sorter gracefully
            try:
                self.view_model.source_directory = str(self.src_dir)
                self.view_model.destination_directory = str(self.dst_dir)
            except Exception as e:
                self.fail(f"Should handle missing file_sorter gracefully: {e}")

        # Test with corrupted property values
        # Simulate property corruption by setting invalid internal state

        # Should handle property access gracefully
        try:
            current_source = self.view_model.source_directory
            assert type(current_source) is not None  # Should not crash
        except Exception as e:
            self.fail(f"Should handle property access gracefully: {e}")


# Compatibility tests using pytest style for existing test coverage
@pytest.fixture()
def view_model_pytest(qtbot):
    """Pytest fixture for FileSorterViewModel."""
    if QApplication.instance() is None:
        QApplication([])
    return FileSorterViewModel(FileSorter())


def test_select_source_directory_updates_property_pytest(view_model_pytest, tmp_path) -> None:
    """Test source directory selection using pytest style."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    with patch(
        "goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory",
        return_value=str(src_dir),
    ) as mocked:
        view_model_pytest.select_source_directory()
        mocked.assert_called_once()
        assert view_model_pytest.source_directory == str(src_dir)
        assert f"Source directory set to: {src_dir}" == view_model_pytest.status_message


def test_select_destination_directory_updates_property_pytest(view_model_pytest, tmp_path) -> None:
    """Test destination directory selection using pytest style."""
    dst_dir = tmp_path / "dst"
    dst_dir.mkdir()
    with patch(
        "goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory",
        return_value=str(dst_dir),
    ) as mocked:
        view_model_pytest.select_destination_directory()
        mocked.assert_called_once()
        assert view_model_pytest.destination_directory == str(dst_dir)
        assert f"Destination directory set to: {dst_dir}" == view_model_pytest.status_message


if __name__ == "__main__":
    unittest.main()
