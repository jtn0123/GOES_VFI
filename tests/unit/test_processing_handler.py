"""Tests for ProcessingHandler functionality."""

from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.processing_handler import ProcessingHandler


class TestProcessingHandler:
    """Test ProcessingHandler functionality."""

    @pytest.fixture()
    def processing_handler(self):
        """Create ProcessingHandler instance for testing."""
        return ProcessingHandler()

    @pytest.fixture()
    def mock_main_window(self):
        """Create a comprehensive mock main window for testing."""
        main_window = Mock()

        # Processing state
        main_window.is_processing = False
        main_window.debug_mode = False
        main_window.vfi_worker = None

        # Methods
        main_window._set_processing_state = Mock()

        # Signal broker
        main_window.signal_broker = Mock()
        main_window.signal_broker.setup_worker_connections = Mock()

        # View models
        main_window.main_view_model = Mock()
        main_window.main_view_model.processing_vm = Mock()
        main_window.main_view_model.processing_vm.start_processing = Mock()

        # Main tab
        main_window.main_tab = Mock()
        main_window.main_tab._reset_start_button = Mock()

        return main_window

    @pytest.fixture()
    def valid_args(self):
        """Valid processing arguments for testing."""
        return {
            "in_dir": "/test/input",
            "out_file": "/test/output.mp4",
            "fps": 30,
            "multiplier": 2,
            "encoder": "libx264",
            "max_workers": 4,
        }

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    def test_handle_processing_success(
        self, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test successful processing workflow."""
        # Mock worker creation
        mock_worker = Mock()
        mock_worker.start = Mock()
        mock_worker_factory.create_worker.return_value = mock_worker

        processing_handler.handle_processing(mock_main_window, valid_args)

        # Check that processing state was set
        assert mock_main_window.is_processing is True
        mock_main_window._set_processing_state.assert_called_with(True)

        # Check worker creation and setup
        mock_worker_factory.create_worker.assert_called_once_with(valid_args, False)
        mock_main_window.signal_broker.setup_worker_connections.assert_called_once_with(mock_main_window, mock_worker)

        # Check worker was started
        mock_worker.start.assert_called_once()

        # Check view model was notified
        mock_main_window.main_view_model.processing_vm.start_processing.assert_called_once()

        # Check worker was assigned
        assert mock_main_window.vfi_worker is mock_worker

    def test_handle_processing_already_in_progress(self, processing_handler, mock_main_window, valid_args) -> None:
        """Test handling when processing is already in progress."""
        # Set processing flag
        mock_main_window.is_processing = True

        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(mock_main_window, valid_args)

            # Should log warning and return early
            mock_logger.warning.assert_called_once()

            # Should not change processing state
            mock_main_window._set_processing_state.assert_not_called()

    def test_handle_processing_empty_args(self, processing_handler, mock_main_window) -> None:
        """Test handling with empty arguments."""
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(mock_main_window, {})

            # Should log warning and return early
            mock_logger.warning.assert_called_once()
            assert "Empty args dictionary" in str(mock_logger.warning.call_args)

            # Should not change processing state
            mock_main_window._set_processing_state.assert_not_called()

    def test_handle_processing_none_args(self, processing_handler, mock_main_window) -> None:
        """Test handling with None arguments."""
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(mock_main_window, None)

            # Should log warning and return early
            mock_logger.warning.assert_called_once()

            # Should not change processing state
            mock_main_window._set_processing_state.assert_not_called()

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    def test_handle_processing_debug_mode(
        self, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test processing with debug mode enabled."""
        mock_main_window.debug_mode = True
        mock_worker = Mock()
        mock_worker.start = Mock()
        mock_worker_factory.create_worker.return_value = mock_worker

        processing_handler.handle_processing(mock_main_window, valid_args)

        # Check worker created with debug mode
        mock_worker_factory.create_worker.assert_called_once_with(valid_args, True)

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    @patch("goesvfi.gui_components.processing_handler.QMessageBox")
    def test_handle_processing_worker_creation_failure(
        self, mock_qmessage_box, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test handling of worker creation failure."""
        # Mock worker creation failure
        mock_worker_factory.create_worker.side_effect = Exception("Worker creation failed")

        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler.handle_processing(mock_main_window, valid_args)

            # Should log exception
            mock_logger.exception.assert_called_once()

            # Should reset processing state
            assert mock_main_window.is_processing is False
            mock_main_window._set_processing_state.assert_called_with(False)

            # Should show error dialog
            mock_qmessage_box.critical.assert_called_once()

            # Should reset start button
            mock_main_window.main_tab._reset_start_button.assert_called_once()

    def test_terminate_previous_worker_no_worker(self, processing_handler, mock_main_window) -> None:
        """Test terminating when no previous worker exists."""
        mock_main_window.vfi_worker = None

        # Should not raise exception
        processing_handler._terminate_previous_worker(mock_main_window)

    def test_terminate_previous_worker_not_running(self, processing_handler, mock_main_window) -> None:
        """Test terminating when worker exists but not running."""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = False
        mock_main_window.vfi_worker = mock_worker

        processing_handler._terminate_previous_worker(mock_main_window)

        # Should check if running but not terminate
        mock_worker.isRunning.assert_called_once()
        mock_worker.terminate.assert_not_called()

    def test_terminate_previous_worker_running(self, processing_handler, mock_main_window) -> None:
        """Test terminating when worker is running."""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        mock_worker.terminate = Mock()
        mock_worker.wait = Mock()
        mock_main_window.vfi_worker = mock_worker

        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            processing_handler._terminate_previous_worker(mock_main_window)

            # Should log warning
            mock_logger.warning.assert_called_once()

            # Should terminate and wait
            mock_worker.terminate.assert_called_once()
            mock_worker.wait.assert_called_once_with(1000)

    def test_terminate_previous_worker_exception(self, processing_handler, mock_main_window) -> None:
        """Test handling exception during worker termination."""
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        mock_worker.terminate.side_effect = Exception("Termination failed")
        mock_main_window.vfi_worker = mock_worker

        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            # Should not raise exception
            processing_handler._terminate_previous_worker(mock_main_window)

            # Should log exception
            mock_logger.exception.assert_called_once()

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    def test_create_and_start_worker_success(
        self, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test successful worker creation and start."""
        mock_worker = Mock()
        mock_worker.start = Mock()
        mock_worker_factory.create_worker.return_value = mock_worker

        result = processing_handler._create_and_start_worker(mock_main_window, valid_args)

        # Should return True
        assert result is True

        # Should create worker
        mock_worker_factory.create_worker.assert_called_once_with(valid_args, False)

        # Should setup connections
        mock_main_window.signal_broker.setup_worker_connections.assert_called_once_with(mock_main_window, mock_worker)

        # Should start worker
        mock_worker.start.assert_called_once()

        # Should assign worker
        assert mock_main_window.vfi_worker is mock_worker

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    @patch("goesvfi.gui_components.processing_handler.QMessageBox")
    def test_create_and_start_worker_failure(
        self, mock_qmessage_box, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test worker creation failure."""
        mock_worker_factory.create_worker.side_effect = ValueError("Invalid arguments")

        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            result = processing_handler._create_and_start_worker(mock_main_window, valid_args)

            # Should return False
            assert result is False

            # Should log exception
            mock_logger.exception.assert_called_once()

            # Should reset processing state
            assert mock_main_window.is_processing is False
            mock_main_window._set_processing_state.assert_called_with(False)

            # Should show error dialog
            mock_qmessage_box.critical.assert_called_once()
            error_args = mock_qmessage_box.critical.call_args[0]
            assert "Failed to initialize processing pipeline" in error_args[2]

            # Should reset start button
            mock_main_window.main_tab._reset_start_button.assert_called_once()

    @patch("goesvfi.gui_components.processing_handler.WorkerFactory")
    def test_integration_full_workflow(
        self, mock_worker_factory, processing_handler, mock_main_window, valid_args
    ) -> None:
        """Test complete processing workflow integration."""
        # Setup existing worker that's running
        existing_worker = Mock()
        existing_worker.isRunning.return_value = True
        existing_worker.terminate = Mock()
        existing_worker.wait = Mock()
        mock_main_window.vfi_worker = existing_worker

        # Setup new worker
        new_worker = Mock()
        new_worker.start = Mock()
        mock_worker_factory.create_worker.return_value = new_worker

        processing_handler.handle_processing(mock_main_window, valid_args)

        # Should terminate existing worker
        existing_worker.terminate.assert_called_once()
        existing_worker.wait.assert_called_once_with(1000)

        # Should create and start new worker
        mock_worker_factory.create_worker.assert_called_once()
        new_worker.start.assert_called_once()

        # Should setup all state correctly
        assert mock_main_window.is_processing is True
        assert mock_main_window.vfi_worker is new_worker
        mock_main_window._set_processing_state.assert_called_with(True)
        mock_main_window.main_view_model.processing_vm.start_processing.assert_called_once()

    def test_logging_behavior(self, processing_handler, mock_main_window, valid_args) -> None:
        """Test that appropriate logging occurs during processing."""
        with patch("goesvfi.gui_components.processing_handler.LOGGER") as mock_logger:
            with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
                mock_worker = Mock()
                mock_worker.start = Mock()
                mock_worker_factory.create_worker.return_value = mock_worker

                processing_handler.handle_processing(mock_main_window, valid_args)

                # Should log start of processing
                assert any("Starting video interpolation" in str(call) for call in mock_logger.info.call_args_list)

                # Should log debug information
                mock_logger.debug.assert_called_once()

                # Should log worker start
                assert any("VfiWorker thread started" in str(call) for call in mock_logger.info.call_args_list)

    def test_error_dialog_content(self, processing_handler, mock_main_window, valid_args) -> None:
        """Test error dialog shows proper content."""
        with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox") as mock_qmessage_box:
                error_msg = "Specific error message"
                mock_worker_factory.create_worker.side_effect = RuntimeError(error_msg)

                processing_handler.handle_processing(mock_main_window, valid_args)

                # Check error dialog content
                call_args = mock_qmessage_box.critical.call_args[0]
                assert call_args[0] is mock_main_window  # parent
                assert call_args[1] == "Error"  # title
                assert error_msg in call_args[2]  # message contains specific error

    def test_state_consistency_on_error(self, processing_handler, mock_main_window, valid_args) -> None:
        """Test that state remains consistent when errors occur."""

        with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
            with patch("goesvfi.gui_components.processing_handler.QMessageBox"):
                mock_worker_factory.create_worker.side_effect = Exception("Test error")

                processing_handler.handle_processing(mock_main_window, valid_args)

                # Processing state should be reset to False
                assert mock_main_window.is_processing is False

                # UI state should be properly reset
                mock_main_window._set_processing_state.assert_called_with(False)
                mock_main_window.main_tab._reset_start_button.assert_called_once()

    def test_worker_assignment_timing(self, processing_handler, mock_main_window, valid_args) -> None:
        """Test that worker is assigned at the correct time."""
        with patch("goesvfi.gui_components.processing_handler.WorkerFactory") as mock_worker_factory:
            mock_worker = Mock()
            mock_worker.start = Mock()
            mock_worker_factory.create_worker.return_value = mock_worker

            # Worker should not be assigned yet
            initial_worker = mock_main_window.vfi_worker

            processing_handler.handle_processing(mock_main_window, valid_args)

            # Worker should now be assigned
            assert mock_main_window.vfi_worker is mock_worker
            assert mock_main_window.vfi_worker is not initial_worker
