"""Tests for GUI components in the gui_components package."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QObject, QSettings, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QWidget

from goesvfi.gui_components import (
    CropHandler,
    FilePickerManager,
    ModelSelectorManager,
    ProcessingCallbacks,
    SettingsPersistence,
    SignalBroker,
    StateManager,
    ThemeManager,
)


class MockMainWindow(QObject):
    """Mock MainWindow for testing components."""

    request_previews_update = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.in_dir = None
        self.out_file_path = None
        self.current_crop_rect = None
        self.is_processing = False
        self.settings = MagicMock(spec=QSettings)
        self.main_tab = MagicMock()
        self.tab_widget = MagicMock()
        self.status_bar = MagicMock()
        self.main_view_model = MagicMock()
        self.sanchez_preview_cache = {}


class TestSignalBroker:
    """Test SignalBroker component."""

    def test_setup_main_window_connections(self) -> None:
        """Test that SignalBroker connects all required signals."""
        broker = SignalBroker()
        main_window = MockMainWindow()

        # Mock methods
        main_window._update_previews = MagicMock()
        main_window._on_tab_changed = MagicMock()
        main_window._handle_processing = MagicMock()

        # Set up connections
        broker.setup_main_window_connections(main_window)

        # Test preview update signal
        main_window.request_previews_update.emit()
        main_window._update_previews.assert_called_once()

        # Test tab change signal
        main_window.tab_widget.currentChanged.connect.assert_called()

        # Test processing signal
        main_window.main_tab.processing_started.connect.assert_called()


class TestStateManager:
    """Test StateManager component."""

    def test_set_input_directory(self) -> None:
        """Test setting input directory updates state correctly."""
        main_window = MockMainWindow()
        main_window._save_input_directory = MagicMock(return_value=True)

        state_manager = StateManager(main_window)
        test_path = Path("/test/input")

        # Set input directory
        state_manager.set_input_directory(test_path)

        # Verify state updated
        assert main_window.in_dir == test_path
        assert len(main_window.sanchez_preview_cache) == 0  # Cache cleared
        main_window.request_previews_update.emit.assert_called_once()
        main_window._save_input_directory.assert_called_once_with(test_path)

    def test_set_crop_rect(self) -> None:
        """Test setting crop rectangle."""
        main_window = MockMainWindow()
        main_window._save_crop_rect = MagicMock(return_value=True)

        state_manager = StateManager(main_window)
        test_rect = (10, 20, 100, 50)

        # Set crop rect
        state_manager.set_crop_rect(test_rect)

        # Verify state updated
        assert main_window.current_crop_rect == test_rect
        main_window.request_previews_update.emit.assert_called_once()
        main_window._save_crop_rect.assert_called_once_with(test_rect)

    def test_clear_input_directory(self) -> None:
        """Test clearing input directory."""
        main_window = MockMainWindow()
        main_window.in_dir = Path("/test/input")

        state_manager = StateManager(main_window)
        state_manager.set_input_directory(None)

        assert main_window.in_dir is None
        assert len(main_window.sanchez_preview_cache) == 0


class TestProcessingCallbacks:
    """Test ProcessingCallbacks component."""

    def test_on_processing_progress(self) -> None:
        """Test progress callback updates UI correctly."""
        main_window = MockMainWindow()
        main_window.main_tab.progress_bar = MagicMock()

        callbacks = ProcessingCallbacks()
        callbacks.on_processing_progress(main_window, 50, 100, 25.0)

        # Verify progress bar updated
        main_window.main_tab.progress_bar.setValue.assert_called_once_with(50)

        # Verify status message
        status_calls = main_window.status_bar.showMessage.call_args_list
        assert any("50%" in str(call) for call in status_calls)

    def test_on_processing_finished(self) -> None:
        """Test processing finished callback."""
        main_window = MockMainWindow()
        main_window.is_processing = True

        callbacks = ProcessingCallbacks()

        with patch("goesvfi.gui_components.processing_callbacks.QMessageBox.information") as mock_info:
            callbacks.on_processing_finished(main_window, "/test/output.mp4")

        # Verify state updated
        assert not main_window.is_processing
        mock_info.assert_called_once()

        # Verify status message
        status_calls = main_window.status_bar.showMessage.call_args_list
        assert any("completed" in str(call).lower() for call in status_calls)

    def test_on_processing_error(self) -> None:
        """Test processing error callback."""
        main_window = MockMainWindow()
        main_window.is_processing = True

        callbacks = ProcessingCallbacks()

        with patch("goesvfi.gui_components.processing_callbacks.QMessageBox.critical") as mock_error:
            callbacks.on_processing_error(main_window, "Test error")

        # Verify error shown
        mock_error.assert_called_once()
        assert "Test error" in str(mock_error.call_args)

        # Verify state updated
        assert not main_window.is_processing

    def test_set_processing_state(self) -> None:
        """Test setting processing state updates UI."""
        main_window = MockMainWindow()
        main_window.main_tab.in_dir_button = MagicMock()
        main_window.main_tab.out_file_button = MagicMock()
        main_window.main_tab.encoder_combo = MagicMock()
        main_window.main_tab.start_button = MagicMock()
        main_window.tab_widget.count.return_value = 5

        callbacks = ProcessingCallbacks()

        # Enable processing
        callbacks.set_processing_state(main_window, True)

        # Verify UI disabled
        assert not main_window.main_tab.in_dir_button.setEnabled.call_args[0][0]
        assert not main_window.main_tab.out_file_button.setEnabled.call_args[0][0]
        assert main_window.main_tab.start_button.setText.call_args[0][0] == "Stop Processing"

        # Verify other tabs disabled
        for i in range(1, 5):
            main_window.tab_widget.setTabEnabled.assert_any_call(i, False)

        # Disable processing
        callbacks.set_processing_state(main_window, False)

        # Verify UI re-enabled
        assert main_window.main_tab.in_dir_button.setEnabled.call_args_list[-1][0][0]
        assert main_window.main_tab.start_button.setText.call_args_list[-1][0][0] == "Start Processing"


class TestSettingsPersistence:
    """Test SettingsPersistence component."""

    def test_save_input_directory(self) -> None:
        """Test saving input directory to settings."""
        settings = MagicMock(spec=QSettings)
        persistence = SettingsPersistence(settings)

        test_path = Path("/test/input")
        result = persistence.save_input_directory(test_path)

        settings.setValue.assert_called_once_with("paths/inputDirectory", str(test_path))
        settings.sync.assert_called_once()
        assert result is True

    def test_save_crop_rect(self) -> None:
        """Test saving crop rectangle to settings."""
        settings = MagicMock(spec=QSettings)
        persistence = SettingsPersistence(settings)

        test_rect = (10, 20, 100, 50)
        result = persistence.save_crop_rect(test_rect)

        settings.setValue.assert_called_once_with("preview/cropRectangle", "10,20,100,50")
        settings.sync.assert_called_once()
        assert result is True

    def test_verify_settings_consistency(self) -> None:
        """Test settings consistency verification."""
        settings = MagicMock(spec=QSettings)
        settings.organizationName.return_value = "TestOrg"
        settings.applicationName.return_value = "TestApp"

        # Mock QApplication
        with patch("goesvfi.gui_components.settings_persistence.QApplication") as mock_app:
            mock_instance = MagicMock()
            mock_instance.organizationName.return_value = "TestOrg"
            mock_instance.applicationName.return_value = "TestApp"
            mock_app.instance.return_value = mock_instance

            persistence = SettingsPersistence(settings)
            persistence._ensure_settings_consistency()

            # Should not create new settings when consistent
            settings.setValue.assert_not_called()


class TestCropHandler:
    """Test CropHandler component."""

    def test_on_crop_clicked_no_input(self) -> None:
        """Test crop click with no input directory."""
        main_window = MockMainWindow()
        main_window.in_dir = None

        handler = CropHandler()

        with patch("goesvfi.gui_components.crop_handler.QMessageBox.warning") as mock_warning:
            handler.on_crop_clicked(main_window)

        mock_warning.assert_called_once()
        assert "select an input directory" in str(mock_warning.call_args).lower()

    def test_get_sorted_image_files(self) -> None:
        """Test getting sorted image files."""
        main_window = MockMainWindow()

        # Create mock directory with image files
        with patch("pathlib.Path.iterdir") as mock_iterdir:
            mock_files = [
                MagicMock(name="image1.png", suffix=".png"),
                MagicMock(name="image2.jpg", suffix=".jpg"),
                MagicMock(name="text.txt", suffix=".txt"),  # Should be filtered out
                MagicMock(name="image3.jpeg", suffix=".jpeg"),
            ]
            for i, f in enumerate(mock_files[:3]):
                f.name = ["image1.png", "image2.jpg", "text.txt"][i]
                f.is_file.return_value = True
            mock_files[2].suffix = ".txt"  # Non-image file
            mock_files[3].name = "image3.jpeg"
            mock_files[3].is_file.return_value = True

            mock_iterdir.return_value = mock_files
            main_window.in_dir = Path("/test/input")

            handler = CropHandler()
            result = handler.get_sorted_image_files(main_window)

            # Should only return image files, sorted
            assert len(result) == 3
            assert all(f.suffix.lower() in {".png", ".jpg", ".jpeg"} for f in result)

    def test_on_clear_crop_clicked(self) -> None:
        """Test clearing crop."""
        main_window = MockMainWindow()
        main_window.current_crop_rect = (10, 20, 100, 50)
        main_window.set_crop_rect = MagicMock()

        handler = CropHandler()
        handler.on_clear_crop_clicked(main_window)

        main_window.set_crop_rect.assert_called_once_with(None)


class TestFilePickerManager:
    """Test FilePickerManager component."""

    def test_pick_input_directory(self) -> None:
        """Test input directory picker."""
        main_window = MockMainWindow()
        main_window.set_in_dir = MagicMock()

        manager = FilePickerManager()

        with patch("goesvfi.gui_components.file_picker_manager.QFileDialog.getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = "/test/selected/dir"

            manager.pick_input_directory(main_window)

            main_window.set_in_dir.assert_called_once_with(Path("/test/selected/dir"))

    def test_pick_output_file(self) -> None:
        """Test output file picker."""
        main_window = MockMainWindow()

        manager = FilePickerManager()

        with patch("goesvfi.gui_components.file_picker_manager.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = ("/test/output.mp4", "Video Files (*.mp4)")

            manager.pick_output_file(main_window)

            assert main_window.out_file_path == Path("/test/output.mp4")
            main_window.main_tab.out_file_edit.setText.assert_called_once_with("/test/output.mp4")


class TestModelSelectorManager:
    """Test ModelSelectorManager component."""

    def test_populate_models(self) -> None:
        """Test populating RIFE models."""
        main_window = MockMainWindow()
        main_window.model_combo = MagicMock(spec=QComboBox)
        main_window.available_models = {
            "rife-v4.6": {"description": "RIFE v4.6"},
            "rife-v4.13": {"description": "RIFE v4.13"},
        }

        manager = ModelSelectorManager()
        manager.populate_models(main_window)

        # Verify models added
        assert main_window.model_combo.addItem.call_count == 2

        # Verify current model set
        assert hasattr(main_window, "current_model_key")

    def test_on_model_changed(self) -> None:
        """Test model change handler."""
        main_window = MockMainWindow()
        main_window._update_rife_ui_elements = MagicMock()

        manager = ModelSelectorManager()
        manager.on_model_changed(main_window, "rife-v4.13")

        assert main_window.current_model_key == "rife-v4.13"
        main_window._update_rife_ui_elements.assert_called_once()


class TestThemeManager:
    """Test ThemeManager component."""

    def test_apply_dark_theme(self) -> None:
        """Test applying dark theme."""
        widget = QWidget()
        manager = ThemeManager()

        # Apply theme
        manager.apply_dark_theme(widget)

        # Verify stylesheet applied
        stylesheet = widget.styleSheet()
        assert len(stylesheet) > 0
        assert "background-color" in stylesheet
        assert "color" in stylesheet
