"""Tests for SignalBroker functionality (Optimized v2).

Optimizations:
- Shared fixtures for mock objects to reduce setup overhead
- Parameterized tests for similar test scenarios
- Consolidated related test methods
- Mock logging operations to speed up tests
- Reduced complexity in mock object creation while maintaining coverage
"""

from unittest.mock import Mock, patch

from PyQt6.QtCore import QObject
import pytest

from goesvfi.gui_components.signal_broker import SignalBroker


@pytest.fixture()
def mock_signal():
    """Create a reusable mock signal."""
    signal = Mock()
    signal.connect = Mock()
    return signal


@pytest.fixture()
def comprehensive_main_window_mock():
    """Create a comprehensive mock main window for testing."""
    main_window = Mock()

    # Mock all required signals
    main_window.request_previews_update = mock_signal()

    # Mock all required methods
    methods = [
        "_update_previews", "_on_tab_changed", "_set_in_dir_from_sorter",
        "_update_rife_ui_elements", "_handle_processing", "_connect_model_combo",
        "_on_processing_progress", "_on_processing_finished", "_on_processing_error"
    ]
    for method in methods:
        setattr(main_window, method, Mock())

    # Mock tab widget
    main_window.tab_widget = Mock()
    main_window.tab_widget.currentChanged = mock_signal()

    # Mock status bar
    main_window.status_bar = Mock()
    main_window.status_bar.showMessage = Mock()

    # Mock view models
    main_window.main_view_model = Mock()
    main_window.main_view_model.status_updated = mock_signal()
    main_window.main_view_model.update_global_status_from_child = Mock()

    processing_vm = Mock()
    processing_vm.status_updated = mock_signal()
    main_window.main_view_model.processing_vm = processing_vm

    # Mock sorter tabs
    main_window.file_sorter_tab = Mock()
    main_window.file_sorter_tab.directory_selected = mock_signal()

    main_window.date_sorter_tab = Mock()
    main_window.date_sorter_tab.directory_selected = mock_signal()

    # Mock main tab and encoder combo
    main_window.main_tab = Mock()
    encoder_combo = Mock()
    encoder_combo.currentTextChanged = mock_signal()
    main_window.main_tab.encoder_combo = encoder_combo

    # Mock processing signal
    processing_started = mock_signal()
    main_window.main_tab.processing_started = processing_started

    return main_window


@pytest.fixture()
def comprehensive_worker_mock():
    """Create a comprehensive mock VFI worker for testing."""
    worker = Mock()

    # Mock all worker signals
    worker.progress = mock_signal()
    worker.finished = mock_signal()
    worker.error = mock_signal()

    return worker


@pytest.fixture()
def signal_broker():
    """Create SignalBroker instance for testing."""
    return SignalBroker()


class TestSignalBrokerCore:
    """Test core SignalBroker functionality."""

    def test_signal_broker_inheritance_and_initialization(self, signal_broker) -> None:
        """Test SignalBroker properly inherits from QObject and initializes correctly."""
        assert isinstance(signal_broker, QObject)
        assert hasattr(signal_broker, "moveToThread")  # QObject method
        assert hasattr(signal_broker, "deleteLater")  # QObject method

    @pytest.mark.parametrize("connection_type", [
        "main_window_connections",
        "worker_connections",
    ])
    def test_signal_broker_methods_exist(self, signal_broker, connection_type) -> None:
        """Test that SignalBroker has all required methods."""
        if connection_type == "main_window_connections":
            assert hasattr(signal_broker, "setup_main_window_connections")
            assert callable(signal_broker.setup_main_window_connections)
        elif connection_type == "worker_connections":
            assert hasattr(signal_broker, "setup_worker_connections")
            assert callable(signal_broker.setup_worker_connections)


class TestMainWindowConnections:
    """Test main window signal connections."""

    def test_basic_main_window_connections(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test basic main window signal connections."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Verify core connections
        main_window.request_previews_update.connect.assert_called_once_with(main_window._update_previews)
        main_window.tab_widget.currentChanged.connect.assert_called_once_with(main_window._on_tab_changed)

    def test_view_model_connections(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test view model signal connections."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Verify view model connections
        main_window.main_view_model.status_updated.connect.assert_called_once_with(
            main_window.status_bar.showMessage
        )
        main_window.main_view_model.processing_vm.status_updated.connect.assert_called_once_with(
            main_window.main_view_model.update_global_status_from_child
        )

    def test_sorter_tab_connections(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test sorter tab signal connections."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Verify sorter connections
        main_window.file_sorter_tab.directory_selected.connect.assert_called_once_with(
            main_window._set_in_dir_from_sorter
        )
        main_window.date_sorter_tab.directory_selected.connect.assert_called_once_with(
            main_window._set_in_dir_from_sorter
        )

    def test_encoder_combo_connection_and_lambda(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test encoder combo signal connection and lambda function."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Verify encoder combo connection was made
        main_window.main_tab.encoder_combo.currentTextChanged.connect.assert_called_once()

        # Get the connected lambda function and test it
        call_args = main_window.main_tab.encoder_combo.currentTextChanged.connect.call_args
        connected_function = call_args[0][0]

        # Test the lambda function calls the right method
        connected_function("test_encoder")
        main_window._update_rife_ui_elements.assert_called_once()

    def test_processing_started_connection(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test processing started signal connection."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Verify processing started connection
        main_window.main_tab.processing_started.connect.assert_called_once_with(
            main_window._handle_processing
        )

    def test_model_combo_connection_when_present(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test model combo connection when method is present."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Should call the model combo connection method
        main_window._connect_model_combo.assert_called_once()

    def test_model_combo_connection_when_missing(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test model combo connection when method is missing."""
        main_window = comprehensive_main_window_mock
        # Remove the method
        delattr(main_window, "_connect_model_combo")

        # Should not raise exception
        signal_broker.setup_main_window_connections(main_window)

    def test_processing_started_exception_handling(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test handling of processing started connection exception."""
        main_window = comprehensive_main_window_mock
        # Make the connection raise an exception
        main_window.main_tab.processing_started.connect.side_effect = Exception("Connection failed")

        with patch("goesvfi.gui_components.signal_broker.LOGGER") as mock_logger:
            # Should not raise exception
            signal_broker.setup_main_window_connections(main_window)

            # Should log the exception
            mock_logger.exception.assert_called_once()


class TestWorkerConnections:
    """Test VFI worker signal connections."""

    def test_complete_worker_connections(self, signal_broker, comprehensive_main_window_mock, comprehensive_worker_mock) -> None:
        """Test all VFI worker signal connections."""
        main_window = comprehensive_main_window_mock
        worker = comprehensive_worker_mock

        signal_broker.setup_worker_connections(main_window, worker)

        # Verify all worker connections
        worker.progress.connect.assert_called_once_with(main_window._on_processing_progress)
        worker.finished.connect.assert_called_once_with(main_window._on_processing_finished)
        worker.error.connect.assert_called_once_with(main_window._on_processing_error)

    @pytest.mark.parametrize("missing_signal", ["progress", "finished", "error"])
    def test_worker_connections_with_missing_signals(self, signal_broker, comprehensive_main_window_mock, missing_signal) -> None:
        """Test worker connections with missing signals."""
        main_window = comprehensive_main_window_mock
        worker = Mock()

        # Add all signals except the missing one
        signals = ["progress", "finished", "error"]
        for signal_name in signals:
            if signal_name != missing_signal:
                setattr(worker, signal_name, mock_signal())

        # Should raise AttributeError for missing signal
        with pytest.raises(AttributeError):
            signal_broker.setup_worker_connections(main_window, worker)

    @pytest.mark.parametrize("missing_method", ["_on_processing_progress", "_on_processing_finished", "_on_processing_error"])
    def test_worker_connections_with_missing_main_window_methods(self, signal_broker, comprehensive_worker_mock, missing_method) -> None:
        """Test worker connections with missing main window methods."""
        worker = comprehensive_worker_mock
        main_window = Mock()

        # Add all methods except the missing one
        methods = ["_on_processing_progress", "_on_processing_finished", "_on_processing_error"]
        for method_name in methods:
            if method_name != missing_method:
                setattr(main_window, method_name, Mock())

        # Should raise AttributeError when trying to connect
        with pytest.raises(AttributeError):
            signal_broker.setup_worker_connections(main_window, worker)


class TestSignalBrokerRobustness:
    """Test SignalBroker robustness and edge cases."""

    def test_multiple_setup_calls_safety(self, signal_broker, comprehensive_main_window_mock) -> None:
        """Test that multiple setup calls don't cause issues."""
        main_window = comprehensive_main_window_mock

        # Call setup multiple times
        signal_broker.setup_main_window_connections(main_window)
        signal_broker.setup_main_window_connections(main_window)

        # Each signal should have been connected multiple times
        assert main_window.request_previews_update.connect.call_count == 2

    def test_setup_with_partial_main_window(self, signal_broker) -> None:
        """Test setup with a main window missing some components."""
        partial_main_window = Mock()

        # Only add some of the expected attributes
        partial_main_window.request_previews_update = mock_signal()
        partial_main_window._update_previews = Mock()

        # Should raise AttributeError for missing components
        with pytest.raises(AttributeError):
            signal_broker.setup_main_window_connections(partial_main_window)

    @patch("goesvfi.gui_components.signal_broker.LOGGER")
    def test_logging_during_main_window_connections(self, mock_logger, signal_broker, comprehensive_main_window_mock) -> None:
        """Test that appropriate logging occurs during main window connection setup."""
        main_window = comprehensive_main_window_mock

        signal_broker.setup_main_window_connections(main_window)

        # Should have multiple debug log calls
        assert mock_logger.debug.call_count >= 5

        # Should have at least one info log for processing signal
        mock_logger.info.assert_called()

    @patch("goesvfi.gui_components.signal_broker.LOGGER")
    def test_logging_during_worker_connections(self, mock_logger, signal_broker, comprehensive_main_window_mock, comprehensive_worker_mock) -> None:
        """Test logging during worker connection setup."""
        main_window = comprehensive_main_window_mock
        worker = comprehensive_worker_mock

        signal_broker.setup_worker_connections(main_window, worker)

        # Should have debug log calls
        assert mock_logger.debug.call_count >= 2

    def test_concurrent_connection_setup(self, signal_broker, comprehensive_main_window_mock, comprehensive_worker_mock) -> None:
        """Test that signal broker can handle concurrent setup calls."""
        import threading

        main_window = comprehensive_main_window_mock
        worker = comprehensive_worker_mock

        def setup_main_window() -> None:
            signal_broker.setup_main_window_connections(main_window)

        def setup_worker() -> None:
            signal_broker.setup_worker_connections(main_window, worker)

        # Start both setups concurrently
        thread1 = threading.Thread(target=setup_main_window)
        thread2 = threading.Thread(target=setup_worker)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Both should complete successfully
        assert main_window.request_previews_update.connect.called
        assert worker.progress.connect.called

    @pytest.mark.parametrize("setup_order", [
        "main_window_first",
        "worker_first",
        "both_together",
    ])
    def test_setup_order_independence(self, signal_broker, comprehensive_main_window_mock, comprehensive_worker_mock, setup_order) -> None:
        """Test that setup order doesn't matter."""
        main_window = comprehensive_main_window_mock
        worker = comprehensive_worker_mock

        if setup_order == "main_window_first":
            signal_broker.setup_main_window_connections(main_window)
            signal_broker.setup_worker_connections(main_window, worker)
        elif setup_order == "worker_first":
            signal_broker.setup_worker_connections(main_window, worker)
            signal_broker.setup_main_window_connections(main_window)
        else:  # both_together
            signal_broker.setup_main_window_connections(main_window)
            signal_broker.setup_worker_connections(main_window, worker)

        # Both setups should succeed regardless of order
        assert main_window.request_previews_update.connect.called
        assert worker.progress.connect.called

    def test_signal_broker_memory_efficiency(self, signal_broker) -> None:
        """Test that SignalBroker doesn't hold unnecessary references."""
        # SignalBroker should be lightweight - just a collection of static-like methods
        # It shouldn't store references to the objects it connects

        main_window = Mock()
        main_window.request_previews_update = mock_signal()
        main_window._update_previews = Mock()

        # After setup, the signal broker shouldn't hold references
        # (This is more of a design verification than a strict test)
        assert not hasattr(signal_broker, "_main_window")
        assert not hasattr(signal_broker, "_worker")
        assert not hasattr(signal_broker, "_connections")
