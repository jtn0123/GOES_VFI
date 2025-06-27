"""Tests for SignalBroker functionality."""

from unittest.mock import Mock, patch

from PyQt6.QtCore import QObject
import pytest

from goesvfi.gui_components.signal_broker import SignalBroker


class TestSignalBroker:
    """Test SignalBroker functionality."""

    @pytest.fixture()
    def signal_broker(self):
        """Create SignalBroker instance for testing."""
        return SignalBroker()

    @pytest.fixture()
    def mock_main_window(self):
        """Create a comprehensive mock main window for testing."""
        main_window = Mock()

        # Mock signals
        main_window.request_previews_update = Mock()
        main_window.request_previews_update.connect = Mock()

        # Mock methods
        main_window._update_previews = Mock()
        main_window._on_tab_changed = Mock()
        main_window._set_in_dir_from_sorter = Mock()
        main_window._update_rife_ui_elements = Mock()
        main_window._handle_processing = Mock()
        main_window._connect_model_combo = Mock()
        main_window._on_processing_progress = Mock()
        main_window._on_processing_finished = Mock()
        main_window._on_processing_error = Mock()

        # Mock tab widget
        main_window.tab_widget = Mock()
        main_window.tab_widget.currentChanged = Mock()
        main_window.tab_widget.currentChanged.connect = Mock()

        # Mock status bar
        main_window.status_bar = Mock()
        main_window.status_bar.showMessage = Mock()

        # Mock view models
        main_window.main_view_model = Mock()
        main_window.main_view_model.status_updated = Mock()
        main_window.main_view_model.status_updated.connect = Mock()
        main_window.main_view_model.update_global_status_from_child = Mock()

        processing_vm = Mock()
        processing_vm.status_updated = Mock()
        processing_vm.status_updated.connect = Mock()
        main_window.main_view_model.processing_vm = processing_vm

        # Mock sorter tabs
        main_window.file_sorter_tab = Mock()
        main_window.file_sorter_tab.directory_selected = Mock()
        main_window.file_sorter_tab.directory_selected.connect = Mock()

        main_window.date_sorter_tab = Mock()
        main_window.date_sorter_tab.directory_selected = Mock()
        main_window.date_sorter_tab.directory_selected.connect = Mock()

        # Mock main tab
        main_window.main_tab = Mock()

        # Mock encoder combo
        encoder_combo = Mock()
        encoder_combo.currentTextChanged = Mock()
        encoder_combo.currentTextChanged.connect = Mock()
        main_window.main_tab.encoder_combo = encoder_combo

        # Mock processing signal
        processing_started = Mock()
        processing_started.connect = Mock()
        main_window.main_tab.processing_started = processing_started

        return main_window

    @pytest.fixture()
    def mock_worker(self):
        """Create a mock VFI worker for testing."""
        worker = Mock()

        # Mock worker signals
        worker.progress = Mock()
        worker.progress.connect = Mock()
        worker.finished = Mock()
        worker.finished.connect = Mock()
        worker.error = Mock()
        worker.error.connect = Mock()

        return worker

    def test_initialization(self, signal_broker) -> None:
        """Test SignalBroker initialization."""
        assert isinstance(signal_broker, QObject)

    def test_setup_main_window_connections_basic(self, signal_broker, mock_main_window) -> None:
        """Test basic main window signal connections."""
        signal_broker.setup_main_window_connections(mock_main_window)

        # Verify preview update connection
        mock_main_window.request_previews_update.connect.assert_called_once_with(mock_main_window._update_previews)

        # Verify tab widget connection
        mock_main_window.tab_widget.currentChanged.connect.assert_called_once_with(mock_main_window._on_tab_changed)

        # Verify view model connections
        mock_main_window.main_view_model.status_updated.connect.assert_called_once_with(
            mock_main_window.status_bar.showMessage
        )
        mock_main_window.main_view_model.processing_vm.status_updated.connect.assert_called_once_with(
            mock_main_window.main_view_model.update_global_status_from_child
        )

    def test_setup_main_window_connections_sorter_tabs(self, signal_broker, mock_main_window) -> None:
        """Test sorter tab signal connections."""
        signal_broker.setup_main_window_connections(mock_main_window)

        # Verify file sorter connection
        mock_main_window.file_sorter_tab.directory_selected.connect.assert_called_once_with(
            mock_main_window._set_in_dir_from_sorter
        )

        # Verify date sorter connection
        mock_main_window.date_sorter_tab.directory_selected.connect.assert_called_once_with(
            mock_main_window._set_in_dir_from_sorter
        )

    def test_setup_main_window_connections_encoder_combo(self, signal_broker, mock_main_window) -> None:
        """Test encoder combo signal connection."""
        signal_broker.setup_main_window_connections(mock_main_window)

        # Verify encoder combo connection was made
        mock_main_window.main_tab.encoder_combo.currentTextChanged.connect.assert_called_once()

        # Get the connected lambda function
        call_args = mock_main_window.main_tab.encoder_combo.currentTextChanged.connect.call_args
        connected_function = call_args[0][0]

        # Test the lambda function calls the right method
        connected_function("test_encoder")
        mock_main_window._update_rife_ui_elements.assert_called_once()

    def test_setup_main_window_connections_processing_started(self, signal_broker, mock_main_window) -> None:
        """Test processing started signal connection."""
        signal_broker.setup_main_window_connections(mock_main_window)

        # Verify processing started connection
        mock_main_window.main_tab.processing_started.connect.assert_called_once_with(
            mock_main_window._handle_processing
        )

    def test_setup_main_window_connections_processing_started_exception(self, signal_broker, mock_main_window) -> None:
        """Test handling of processing started connection exception."""
        # Make the connection raise an exception
        mock_main_window.main_tab.processing_started.connect.side_effect = Exception("Connection failed")

        with patch("goesvfi.gui_components.signal_broker.LOGGER") as mock_logger:
            # Should not raise exception
            signal_broker.setup_main_window_connections(mock_main_window)

            # Should log the exception
            mock_logger.exception.assert_called_once()

    def test_setup_main_window_connections_model_combo_present(self, signal_broker, mock_main_window) -> None:
        """Test model combo connection when method is present."""
        signal_broker.setup_main_window_connections(mock_main_window)

        # Should call the model combo connection method
        mock_main_window._connect_model_combo.assert_called_once()

    def test_setup_main_window_connections_model_combo_missing(self, signal_broker, mock_main_window) -> None:
        """Test model combo connection when method is missing."""
        # Remove the method
        delattr(mock_main_window, "_connect_model_combo")

        # Should not raise exception
        signal_broker.setup_main_window_connections(mock_main_window)

    def test_setup_worker_connections(self, signal_broker, mock_main_window, mock_worker) -> None:
        """Test VFI worker signal connections."""
        signal_broker.setup_worker_connections(mock_main_window, mock_worker)

        # Verify all worker connections
        mock_worker.progress.connect.assert_called_once_with(mock_main_window._on_processing_progress)
        mock_worker.finished.connect.assert_called_once_with(mock_main_window._on_processing_finished)
        mock_worker.error.connect.assert_called_once_with(mock_main_window._on_processing_error)

    def test_setup_worker_connections_missing_signals(self, signal_broker, mock_main_window) -> None:
        """Test worker connections with missing signals."""
        # Worker with missing signals
        incomplete_worker = Mock()
        delattr(incomplete_worker, "progress")

        # Should raise AttributeError
        with pytest.raises(AttributeError):
            signal_broker.setup_worker_connections(mock_main_window, incomplete_worker)

    def test_setup_worker_connections_missing_main_window_methods(self, signal_broker, mock_worker) -> None:
        """Test worker connections with missing main window methods."""
        incomplete_main_window = Mock()
        delattr(incomplete_main_window, "_on_processing_progress")

        # Should raise AttributeError when trying to connect
        with pytest.raises(AttributeError):
            signal_broker.setup_worker_connections(incomplete_main_window, mock_worker)

    def test_multiple_setup_calls_safe(self, signal_broker, mock_main_window) -> None:
        """Test that multiple setup calls don't cause issues."""
        # Call setup multiple times
        signal_broker.setup_main_window_connections(mock_main_window)
        signal_broker.setup_main_window_connections(mock_main_window)

        # Each signal should have been connected multiple times
        # (This tests that the broker doesn't track/prevent duplicate connections)
        assert mock_main_window.request_previews_update.connect.call_count == 2

    def test_setup_with_partial_main_window(self, signal_broker) -> None:
        """Test setup with a main window missing some components."""
        partial_main_window = Mock()

        # Only add some of the expected attributes
        partial_main_window.request_previews_update = Mock()
        partial_main_window.request_previews_update.connect = Mock()
        partial_main_window._update_previews = Mock()

        # Should raise AttributeError for missing components
        with pytest.raises(AttributeError):
            signal_broker.setup_main_window_connections(partial_main_window)

    def test_signal_broker_inheritance(self, signal_broker) -> None:
        """Test that SignalBroker properly inherits from QObject."""
        assert isinstance(signal_broker, QObject)
        assert hasattr(signal_broker, "moveToThread")  # QObject method
        assert hasattr(signal_broker, "deleteLater")  # QObject method

    def test_logging_during_connections(self, signal_broker, mock_main_window) -> None:
        """Test that appropriate logging occurs during connection setup."""
        with patch("goesvfi.gui_components.signal_broker.LOGGER") as mock_logger:
            signal_broker.setup_main_window_connections(mock_main_window)

            # Should have multiple debug log calls
            assert mock_logger.debug.call_count >= 5

            # Should have at least one info log for processing signal
            mock_logger.info.assert_called()

    def test_logging_during_worker_connections(self, signal_broker, mock_main_window, mock_worker) -> None:
        """Test logging during worker connection setup."""
        with patch("goesvfi.gui_components.signal_broker.LOGGER") as mock_logger:
            signal_broker.setup_worker_connections(mock_main_window, mock_worker)

            # Should have debug log calls
            assert mock_logger.debug.call_count >= 2

    def test_concurrent_connection_setup(self, signal_broker, mock_main_window, mock_worker) -> None:
        """Test that signal broker can handle concurrent setup calls."""
        import threading

        def setup_main_window() -> None:
            signal_broker.setup_main_window_connections(mock_main_window)

        def setup_worker() -> None:
            signal_broker.setup_worker_connections(mock_main_window, mock_worker)

        # Start both setups concurrently
        thread1 = threading.Thread(target=setup_main_window)
        thread2 = threading.Thread(target=setup_worker)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Both should complete successfully
        assert mock_main_window.request_previews_update.connect.called
        assert mock_worker.progress.connect.called
