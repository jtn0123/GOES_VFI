"""PyQt6 GUI entry point for GOES‑VFI.

Launching this module starts the application's main window with tabs for data
integrity checks, imagery previews, and video generation.  Run
``python -m goesvfi.gui`` to open the interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QStatusBar, QTabWidget, QVBoxLayout, QWidget

from goesvfi.gui_components import (
    InitializationManager,
    ProcessingHandler,
    SettingsPersistence,
    ThemeManager,
)
from goesvfi.utils import log
from goesvfi.utils.gui_helpers import ClickableLabel
from goesvfi.utils.settings.gui_settings_manager import GUISettingsManager

LOGGER = log.get_logger(__name__)


# ────────────────────────────── Main Window ────────────────────────────────
class MainWindow(QWidget):
    request_previews_update = pyqtSignal()  # Signal to trigger preview update

    # Type annotations for attributes created by InitializationManager
    main_tab: Any
    main_view_model: Any
    state_manager: Any
    file_picker_manager: Any
    crop_handler: Any
    zoom_manager: Any
    model_selector_manager: Any
    tab_widget: QTabWidget
    signal_broker: Any
    ui_setup_manager: Any
    rife_ui_manager: Any
    ffmpeg_settings_tab: Any
    in_dir: Optional[Path]
    current_crop_rect: Optional[Any]
    processing_callbacks: Any

    def __init__(self, debug_mode: bool = False) -> None:
        # Removed log level setting here, it's handled in main()
        LOGGER.debug("Entering MainWindow.__init__... debug_mode=%s", debug_mode)
        super().__init__()
        self.debug_mode = debug_mode
        self.setWindowTitle(self.tr("GOES-VFI"))
        self.setGeometry(100, 100, 800, 600)  # x, y, w, h

        # Initialize components using initialization manager
        self.initialization_manager = InitializationManager()
        self._initialize_settings()
        self.initialization_manager.initialize_models(self)
        self.initialization_manager.initialize_processors(self)
        self.initialization_manager.initialize_state(self)

        # Create processing handler
        self.processing_handler = ProcessingHandler()

        self._create_ui()

        LOGGER.info("MainWindow initialized.")

    def _initialize_settings(self) -> None:
        """Initialize QSettings for the application."""
        # Get the application-wide organization and application names
        app = QApplication.instance()
        org_name = app.organizationName() if app is not None else ""
        app_name = app.applicationName() if app is not None else ""

        if not org_name or not app_name:
            # Default fallback values if not set at the application level
            org_name = "GOES_VFI"
            app_name = "GOES_VFI_App"
            LOGGER.warning("Application organization/name not set! Using defaults: %s/%s")

        # Initialize QSettings with application-wide settings to ensure consistency
        self.settings = QSettings(org_name, app_name)
        self.settings_loaded = False  # Flag to avoid duplicate loading
        # Disable fallbacks to ensure we only use our specified settings
        self.settings.setFallbacksEnabled(False)

        # Log where settings will be stored
        LOGGER.debug("Settings will be stored at: %s", self.settings.fileName())

        # Create settings manager for simplified save/load
        self.settings_manager = GUISettingsManager(self.settings)
        # Create settings persistence handler
        self.settings_persistence = SettingsPersistence(self.settings)

    def _create_ui(self) -> None:
        """Create the user interface."""
        main_layout = QVBoxLayout(self)

        # Set up tab widget
        self._setup_tab_widget()

        # Create all tabs
        self._create_all_tabs()

        # Add tab widget to layout
        main_layout.addWidget(self.tab_widget)

        # Create status bar
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

        # Set up aliases for compatibility
        self.model_combo = self.main_tab.rife_model_combo
        self.sanchez_res_km_combo = self.main_tab.sanchez_res_combo

        # Apply dark theme
        self.theme_manager = ThemeManager()
        self.theme_manager.apply_dark_theme(self)

        # Load settings after main layout is constructed
        self.loadSettings()

        # Set up all signal connections through SignalBroker
        self.signal_broker.setup_main_window_connections(self)

        # Initial preview update after a short delay
        QTimer.singleShot(100, self.request_previews_update.emit)

        LOGGER.info("MainWindow initialized.")

    def _setup_tab_widget(self) -> None:
        """Configure the tab widget appearance and behavior."""
        # Create tab widget
        self.tab_widget = QTabWidget(self)

        # Create UI setup manager
        from goesvfi.gui_components.ui_setup_manager import UISetupManager

        self.ui_setup_manager = UISetupManager()

        # Create signal broker
        from goesvfi.gui_components.signal_broker import SignalBroker

        self.signal_broker = SignalBroker()

        self.ui_setup_manager.setup_tab_widget(self)

    def _create_all_tabs(self) -> None:
        """Create and configure all application tabs."""
        self.ui_setup_manager.create_all_tabs(self)

    def _create_integrity_check_tab(self) -> None:
        """Create and configure the integrity check tab."""
        self.ui_setup_manager.create_integrity_check_tab(self)

    def _post_init_setup(self) -> None:
        # LOGGER.debug("Entering _post_init_setup...")  # Removed log
        """Perform UI setup and signal connections after initialization.

        This method should be called after the MainWindow is added to qtbot in tests,
        to ensure proper Qt object lifetime management.
        """
        # Set up all signal connections through SignalBroker
        self.signal_broker.setup_main_window_connections(self)

        # Populate initial data
        self._populate_models()

        # Load settings
        self.loadSettings()

        # Update initial UI state
        self._update_rife_ui_elements()
        # self._update_ffmpeg_controls_state(self.encoder_combo.currentText())
        # Removed - FFmpeg groups moved to own tab
        self._update_start_button_state()
        self._update_crop_buttons_state()
        self._update_rife_ui_elements()  # Use the new method
        # Quality controls state is now handled in the FFmpeg settings tab
        # self._update_quality_controls_state(self.current_encoder)  # Method moved to FFmpeg tab
        # self._update_ffmpeg_controls_state(self.current_encoder == "FFmpeg",
        #                                    update_group=False)
        # Removed - FFmpeg groups moved to own tab

        # Set up preview update (MOVED TO __init__)

        # Set initial status
        self.status_bar.showMessage(self.main_view_model.status)

        # LOGGER.debug("Exiting _post_init_setup...")  # Removed log
        LOGGER.info("MainWindow post-initialization setup complete.")

    # --- State Setters for Child Tabs ---
    def _save_input_directory(self, path: Path) -> bool:
        """Save input directory to settings persistently."""
        return self.settings_persistence.save_input_directory(path)

    def set_in_dir(self, path: Path | None) -> None:
        """Set the input directory state, save settings, and clear Sanchez cache."""
        self.state_manager.set_input_directory(path)

    def _save_crop_rect(self, rect: tuple[int, int, int, int]) -> bool:
        """Save crop rectangle to settings persistently."""
        return self.settings_persistence.save_crop_rect(rect)

    def set_crop_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        """Set the current crop rectangle state."""
        self.state_manager.set_crop_rect(rect)

    # ------------------------------------
    def _set_in_dir_from_sorter(self, directory: Path) -> None:
        """Sets the input directory from a sorter tab."""
        self.file_picker_manager.set_input_dir_from_sorter(self, directory)

    def _pick_in_dir(self) -> None:
        """Open a directory dialog to select the input image folder."""
        self.file_picker_manager.pick_input_directory(self)

    def _pick_out_file(self) -> None:
        """Open a file dialog to select the output MP4 file path."""
        self.file_picker_manager.pick_output_file(self)

    def _on_crop_clicked(self) -> None:
        """Open the crop dialog with the first image."""
        self.crop_handler.on_crop_clicked(self)

    def _get_sorted_image_files(self) -> list[Path]:
        """Get sorted list of image files from input directory."""
        return cast(List[Path], self.crop_handler.get_sorted_image_files(self))

    def _prepare_image_for_crop_dialog(self, image_path: Path) -> Optional[QPixmap]:
        """Prepare an image for the crop dialog, applying Sanchez if enabled."""
        return cast(
            Optional[QPixmap],
            self.crop_handler.prepare_image_for_crop_dialog(self, image_path),
        )

    def _get_processed_preview_pixmap(self) -> Optional[QPixmap]:
        """Get the processed preview pixmap from the first frame label."""
        return cast(Optional[QPixmap], self.crop_handler.get_processed_preview_pixmap(self))

    def _show_crop_dialog(self, pixmap: QPixmap) -> None:
        """Show the crop selection dialog."""
        self.crop_handler.show_crop_dialog(self, pixmap)

    def _on_clear_crop_clicked(self) -> None:
        """Clear the current crop rectangle and update previews."""
        self.crop_handler.on_clear_crop_clicked(self)

    def _show_zoom(self, label: ClickableLabel) -> None:
        """Show a zoomed view of the processed image associated with the clicked label."""
        self.zoom_manager.show_zoom(label, self)

    def _connect_model_combo(self) -> None:
        """Connect the model combo box signal."""
        # Disabled - MainTab already handles model selection in _on_model_selected
        # self.model_selector_manager.connect_model_combo(self)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab changes and update the ViewModel."""
        LOGGER.debug("Tab changed to index: %s", index)
        self.main_view_model.active_tab_index = index  # <-- Update ViewModel state
        # Add any other logic needed when a tab changes, e.g., triggering updates
        if self.tab_widget.widget(index) == self.main_tab:
            self.request_previews_update.emit()

    def loadSettings(self) -> None:
        """Load settings from QSettings using the refactored settings manager."""
        if self.settings_loaded:
            LOGGER.debug("Settings already loaded, skipping...")
            return

        LOGGER.info("Loading application settings...")
        self.settings_manager.load_all_settings(self)
        self.settings_loaded = True  # pylint: disable=attribute-defined-outside-init
        LOGGER.info("All settings loaded")

    def saveSettings(self) -> None:
        """Save settings to QSettings using the refactored settings manager."""
        LOGGER.info("Saving application settings...")
        success = self.settings_manager.save_all_settings(self)
        if success:
            LOGGER.info("All settings saved successfully")
        else:
            LOGGER.warning("Some settings may not have been saved")

    def _validate_thread_spec(self, text: str) -> None:
        """Validate the RIFE thread specification format."""
        self.model_selector_manager.validate_thread_spec(self, text)

    def _populate_models(self) -> None:
        """Populate the RIFE model combo box."""
        self.model_selector_manager.populate_models(self)

    def _toggle_sanchez_res_enabled(self, state: Qt.CheckState) -> None:
        """Enables or disables the Sanchez resolution combo box based on the checkbox state."""
        self.model_selector_manager.toggle_sanchez_res_enabled(self, state)

    @property
    def current_encoder(self) -> str:
        """Get the current encoder from the main tab."""
        return self.main_tab.current_encoder if hasattr(self.main_tab, "current_encoder") else "RIFE"

    @property
    def current_model_key(self) -> str:
        """Get the current model key from the main tab."""
        return self.main_tab.current_model_key if hasattr(self.main_tab, "current_model_key") else ""

    def _update_rife_ui_elements(self) -> None:
        """Updates the visibility and state of RIFE-specific UI elements."""
        self.rife_ui_manager.update_rife_ui_elements(
            self.main_tab,
            self.current_encoder,
            self.current_model_key,
            self.ffmpeg_settings_tab,
        )

    def _on_model_changed(self, model_key: str) -> None:
        """Handle RIFE model selection change."""
        self.model_selector_manager.on_model_changed(self, model_key)

    def _update_previews(self) -> None:
        """Update preview images using the PreviewManager."""
        LOGGER.debug("_update_previews called")

        if not self.in_dir:
            LOGGER.debug("No input directory set, skipping preview update")
            return

        # Get preview labels from main tab
        preview_labels = []
        if hasattr(self.main_tab, "first_frame_label"):
            preview_labels.append(self.main_tab.first_frame_label)
        if hasattr(self.main_tab, "last_frame_label"):
            preview_labels.append(self.main_tab.last_frame_label)

        if not preview_labels:
            LOGGER.warning("No preview labels found in main_tab")
            return

        # Load preview images using PreviewManager
        try:
            # Get sanchez settings from main tab
            apply_sanchez = False
            sanchez_resolution = None
            if hasattr(self.main_tab, "sanchez_checkbox") and self.main_tab.sanchez_checkbox.isChecked():
                apply_sanchez = True
                if hasattr(self.main_tab, "sanchez_res_combo"):
                    sanchez_resolution = int(self.main_tab.sanchez_res_combo.currentText())

            LOGGER.debug(
                "Loading preview images from %s, apply_sanchez=%s",
                self.in_dir,
                apply_sanchez,
            )

            # Disconnect any existing connections first
            try:
                self.main_view_model.preview_manager.preview_updated.disconnect()
            except TypeError:
                pass  # No connections exist
            try:
                self.main_view_model.preview_manager.preview_error.disconnect()
            except TypeError:
                pass  # No connections exist

            # Connect signals before loading
            self.main_view_model.preview_manager.preview_updated.connect(self._on_preview_images_loaded)
            self.main_view_model.preview_manager.preview_error.connect(self._on_preview_error)

            # Load previews through view model
            success = self.main_view_model.preview_manager.load_preview_images(
                self.in_dir,
                crop_rect=self.current_crop_rect,
                apply_sanchez=apply_sanchez,
                sanchez_resolution=sanchez_resolution,
            )

            if not success:
                LOGGER.error("Failed to load preview images")

        except Exception as e:
            LOGGER.exception("Error updating previews: %s", e)

    def _handle_processing(self, args: Dict[str, Any]) -> None:
        """Handle the processing_started signal from MainTab."""
        self.processing_handler.handle_processing(self, args)

    def _on_processing_progress(self, current: int, total: int, eta: float) -> None:
        """Handle progress updates from the VFI worker."""
        self.processing_callbacks.on_processing_progress(self, current, total, eta)

    def _on_processing_finished(self, output_path: str) -> None:
        """Handle successful completion of VFI processing."""
        self.processing_callbacks.on_processing_finished(self, output_path)

    def _on_processing_error(self, error_msg: str) -> None:
        """Handle errors during VFI processing."""
        self.processing_callbacks.on_processing_error(self, error_msg)

    def _set_processing_state(self, is_processing: bool) -> None:
        """Update UI elements to reflect processing state."""
        self.processing_callbacks.set_processing_state(self, is_processing)

    def _update_start_button_state(self) -> None:
        """Update the start button enabled state based on current inputs."""
        self.processing_callbacks.update_start_button_state(self)

    def _on_preview_images_loaded(self, first_pixmap: QPixmap, middle_pixmap: QPixmap, last_pixmap: QPixmap) -> None:
        """Handle loaded preview images from PreviewManager.

        Args:
            first_pixmap: The first frame pixmap
            middle_pixmap: The middle frame pixmap
            last_pixmap: The last frame pixmap
        """
        LOGGER.debug(
            "_on_preview_images_loaded called with pixmaps: first=%s, middle=%s, last=%s",
            not first_pixmap.isNull(),
            not middle_pixmap.isNull(),
            not last_pixmap.isNull(),
        )

        try:
            # Update first frame label
            if hasattr(self.main_tab, "first_frame_label") and not first_pixmap.isNull():
                # Scale pixmap to fit label while maintaining aspect ratio
                scaled_first_pixmap = self.main_view_model.preview_manager.scale_preview_pixmap(
                    first_pixmap, self.main_tab.first_frame_label.size()
                )
                self.main_tab.first_frame_label.setPixmap(scaled_first_pixmap)

                # Set file_path attribute for display
                if self.in_dir and self.in_dir.exists():
                    image_files = sorted(
                        [
                            f
                            for f in self.in_dir.iterdir()
                            if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                        ]
                    )
                    if image_files:
                        self.main_tab.first_frame_label.file_path = str(image_files[0])
                # Store the full resolution image data for preview
                first_frame_data, _, _ = self.main_view_model.preview_manager.get_current_frame_data()
                if first_frame_data and first_frame_data.image_data is not None:
                    # Convert numpy array to QImage using PreviewManager's method
                    full_res_pixmap = self.main_view_model.preview_manager._numpy_to_qpixmap(
                        first_frame_data.image_data
                    )
                    if not full_res_pixmap.isNull():
                        self.main_tab.first_frame_label.processed_image = full_res_pixmap.toImage()
                        LOGGER.debug(
                            "Set processed_image on first_frame_label: %s",
                            self.main_tab.first_frame_label.processed_image,
                        )
                else:
                    LOGGER.warning("No first_frame_data available from preview manager")

            # Update middle frame label
            if hasattr(self.main_tab, "middle_frame_label") and not middle_pixmap.isNull():
                # Scale pixmap to fit label while maintaining aspect ratio
                scaled_middle_pixmap = self.main_view_model.preview_manager.scale_preview_pixmap(
                    middle_pixmap, self.main_tab.middle_frame_label.size()
                )
                self.main_tab.middle_frame_label.setPixmap(scaled_middle_pixmap)

                # Set file_path attribute for display
                if self.in_dir and self.in_dir.exists():
                    image_files = sorted(
                        [
                            f
                            for f in self.in_dir.iterdir()
                            if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                        ]
                    )
                    if len(image_files) >= 3:
                        middle_index = len(image_files) // 2
                        self.main_tab.middle_frame_label.file_path = str(image_files[middle_index])
                # Store the full resolution image data for preview
                _, middle_frame_data, _ = self.main_view_model.preview_manager.get_current_frame_data()
                if middle_frame_data and middle_frame_data.image_data is not None:
                    # Convert numpy array to QImage using PreviewManager's method
                    full_res_pixmap = self.main_view_model.preview_manager._numpy_to_qpixmap(
                        middle_frame_data.image_data
                    )
                    if not full_res_pixmap.isNull():
                        self.main_tab.middle_frame_label.processed_image = full_res_pixmap.toImage()

            # Update last frame label
            if hasattr(self.main_tab, "last_frame_label") and not last_pixmap.isNull():
                # Scale pixmap to fit label while maintaining aspect ratio
                scaled_last_pixmap = self.main_view_model.preview_manager.scale_preview_pixmap(
                    last_pixmap, self.main_tab.last_frame_label.size()
                )
                self.main_tab.last_frame_label.setPixmap(scaled_last_pixmap)

                # Set file_path attribute for display
                if self.in_dir and self.in_dir.exists():
                    image_files = sorted(
                        [
                            f
                            for f in self.in_dir.iterdir()
                            if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
                        ]
                    )
                    if image_files:
                        self.main_tab.last_frame_label.file_path = str(image_files[-1])
                # Store the full resolution image data for preview
                _, _, last_frame_data = self.main_view_model.preview_manager.get_current_frame_data()
                if last_frame_data and last_frame_data.image_data is not None:
                    # Convert numpy array to QImage using PreviewManager's method
                    full_res_pixmap = self.main_view_model.preview_manager._numpy_to_qpixmap(last_frame_data.image_data)
                    if not full_res_pixmap.isNull():
                        self.main_tab.last_frame_label.processed_image = full_res_pixmap.toImage()

            LOGGER.debug("Preview images updated successfully")

        except Exception as e:
            LOGGER.exception("Error updating preview labels: %s", e)

    def _on_preview_error(self, error_message: str) -> None:
        """Handle preview loading errors.

        Args:
            error_message: The error message from PreviewManager
        """
        LOGGER.error("Preview loading error: %s", error_message)
        # Update status bar to show error
        self.status_bar.showMessage(f"Preview error: {error_message}", 5000)

    def _update_crop_buttons_state(self) -> None:
        """Update crop button states based on current state."""
        self.processing_callbacks.update_crop_buttons_state(self)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Handle window close event."""
        LOGGER.info("MainWindow close event triggered")

        # Save settings before closing
        self.saveSettings()

        # Clean up resources
        if hasattr(self, "_sanchez_gui_temp_dir") and self._sanchez_gui_temp_dir.exists():
            try:
                import shutil

                shutil.rmtree(self._sanchez_gui_temp_dir)
                LOGGER.debug("Cleaned up temporary Sanchez directory")
            except Exception as e:
                LOGGER.warning("Failed to clean up temp directory: %s", e)

        # Terminate any running worker
        if hasattr(self, "vfi_worker") and self.vfi_worker and self.vfi_worker.isRunning():
            LOGGER.info("Terminating VFI worker thread")
            self.vfi_worker.terminate()
            self.vfi_worker.wait(1000)

        # Accept the close event
        event.accept()
