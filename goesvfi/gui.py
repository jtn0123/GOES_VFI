"""PyQt6 GUI entry point for GOES‑VFI.

Launching this module starts the application's main window with tabs for data
integrity checks, imagery previews, and video generation.  Run
``python -m goesvfi.gui`` to open the interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QSettings, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QStatusBar, QTabWidget, QVBoxLayout, QWidget

from goesvfi.gui_components import (
    InitializationManager,
    ProcessingHandler,
    SettingsPersistence,
    ThemeManager,
)
from goesvfi.gui_components.resource_manager import get_resource_tracker
from goesvfi.gui_components.update_manager import get_update_manager, register_update, request_update
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
    in_dir: Path | None
    current_crop_rect: Any | None
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

        # Apply qt-material theme
        self.theme_manager = ThemeManager()
        app = QApplication.instance()
        if app:
            self.theme_manager.apply_theme(cast("QApplication", app))
        else:
            LOGGER.error("No QApplication instance found for theme application")

        # Load settings after main layout is constructed
        self.loadSettings()

        # Set up all signal connections through SignalBroker
        self.signal_broker.setup_main_window_connections(self)

        # Connect settings tab signals if it exists
        if hasattr(self, "settings_tab"):
            self._connect_settings_tab()

        # Initialize UpdateManager integration
        self._setup_main_window_update_manager()

        # Initial preview update after a short delay (now through UpdateManager)
        QTimer.singleShot(100, lambda: request_update("main_window_preview"))

        LOGGER.info("MainWindow initialized.")

    def _setup_main_window_update_manager(self) -> None:
        """Set up UpdateManager integration for main window updates."""
        # Register main window update operations
        register_update("main_window_preview", self._emit_preview_update, priority=3)
        register_update("main_window_status", self._update_status_display, priority=2)

        # Initialize the global UpdateManager
        update_manager = get_update_manager()
        LOGGER.info("MainWindow integrated with UpdateManager (batching: %sms)", update_manager.batch_delay_ms)

    def _emit_preview_update(self) -> None:
        """Emit preview update signal (called by UpdateManager)."""
        self.request_previews_update.emit()

    def _update_status_display(self) -> None:
        """Update status display elements (called by UpdateManager)."""
        # This can be expanded to update various status elements in batches

    def request_main_window_update(self, update_type: str = "preview") -> None:
        """Request a main window update through UpdateManager.

        Args:
            update_type: Type of update (preview, status)
        """
        update_id = f"main_window_{update_type}"
        request_update(update_id)

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
        return cast("list[Path]", self.crop_handler.get_sorted_image_files(self))

    def _prepare_image_for_crop_dialog(self, image_path: Path) -> QPixmap | None:
        """Prepare an image for the crop dialog, applying Sanchez if enabled."""
        return cast(
            "QPixmap | None",
            self.crop_handler.prepare_image_for_crop_dialog(self, image_path),
        )

    def _get_processed_preview_pixmap(self) -> QPixmap | None:
        """Get the processed preview pixmap from the first frame label."""
        return cast("QPixmap | None", self.crop_handler.get_processed_preview_pixmap(self))

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

        if not self.in_dir or not self.in_dir.exists():
            LOGGER.debug("No valid input directory set, skipping preview update")
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
            sanchez_checkbox = getattr(self.main_tab, "sanchez_false_colour_checkbox", None)
            if sanchez_checkbox and sanchez_checkbox.isChecked():
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

            # Load previews through view model using memory-efficient thumbnails
            success = self.main_view_model.preview_manager.load_preview_thumbnails(
                self.in_dir,
                crop_rect=self.current_crop_rect,
                apply_sanchez=apply_sanchez,
                sanchez_resolution=sanchez_resolution,
            )

            if not success:
                LOGGER.error("Failed to load preview images")

        except Exception:
            LOGGER.exception("Error updating previews")

    def _handle_processing(self, args: dict[str, Any]) -> None:
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
            # Get image files once for all frames
            image_files = self._get_image_files_from_input_dir()
            frame_data = self.main_view_model.preview_manager.get_current_frame_data()

            # Update each frame label
            self._update_frame_label("first_frame_label", first_pixmap, image_files, frame_data[0], 0)
            self._update_frame_label(
                "middle_frame_label",
                middle_pixmap,
                image_files,
                frame_data[1],
                len(image_files) // 2 if image_files else 0,
            )
            self._update_frame_label("last_frame_label", last_pixmap, image_files, frame_data[2], -1)

            LOGGER.debug("Preview images updated successfully")

        except Exception:
            LOGGER.exception("Error updating preview labels")

    def _get_image_files_from_input_dir(self) -> list[Path]:
        """Get sorted list of image files from input directory."""
        if not (self.in_dir and self.in_dir.exists()):
            return []

        return sorted([
            f for f in self.in_dir.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        ])

    def _update_frame_label(
        self, label_name: str, pixmap: QPixmap, image_files: list[Path], frame_data: Any, file_index: int
    ) -> None:
        """Update a single frame label with pixmap and metadata."""
        if not (hasattr(self.main_tab, label_name) and not pixmap.isNull()):
            return

        label = getattr(self.main_tab, label_name)

        # Scale and set pixmap
        target_size = self._get_target_size_for_label(label)
        scaled_pixmap = self.main_view_model.preview_manager.scale_preview_pixmap(pixmap, target_size)
        label.setPixmap(scaled_pixmap)

        # Set file path
        if image_files:
            if file_index == -1:  # Last file
                label.file_path = str(image_files[-1])
            elif file_index < len(image_files):
                label.file_path = str(image_files[file_index])

        # Set processed image data
        if frame_data and frame_data.image_data is not None:
            full_res_pixmap = self.main_view_model.preview_manager.numpy_to_qpixmap(frame_data.image_data)
            if not full_res_pixmap.isNull():
                label.processed_image = full_res_pixmap.toImage()
                if label_name == "first_frame_label":
                    LOGGER.debug("Set processed_image on first_frame_label: %s", label.processed_image)
        elif label_name == "first_frame_label":
            LOGGER.warning("No first_frame_data available from preview manager")

    def _get_target_size_for_label(self, label: QWidget) -> QSize:
        """Get appropriate target size for scaling a label's pixmap."""
        target_size = QSize(200, 200)  # Minimum preview size
        current_size = label.size()
        if current_size.width() > 200 and current_size.height() > 200:
            target_size = current_size
        return target_size

    def _on_preview_error(self, error_message: str) -> None:
        """Handle preview loading errors.

        Args:
            error_message: The error message from PreviewManager
        """
        # Only show error messages if we have a valid input directory
        # This prevents showing errors during startup when no directory is selected
        if self.in_dir and self.in_dir.exists():
            LOGGER.error("Preview loading error: %s", error_message)
            # Update status bar to show error
            self.status_bar.showMessage(f"Preview error: {error_message}", 5000)
        else:
            LOGGER.debug("Suppressing preview error (no valid directory): %s", error_message)

    def _update_crop_buttons_state(self) -> None:
        """Update crop button states based on current state."""
        self.processing_callbacks.update_crop_buttons_state(self)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handle window close event."""
        LOGGER.info("MainWindow close event triggered")

        # Save settings before closing
        self.saveSettings()

        # Clean up all tracked resources through resource manager
        resource_tracker = get_resource_tracker()
        stats = resource_tracker.get_stats()
        LOGGER.info("Cleaning up resources: %s", stats)

        resource_tracker.cleanup_all()

        # Legacy cleanup for any untracked resources
        if hasattr(self, "_sanchez_gui_temp_dir") and self._sanchez_gui_temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self._sanchez_gui_temp_dir)
                LOGGER.debug("Cleaned up temporary Sanchez directory")
            except Exception as e:
                LOGGER.warning("Failed to clean up temp directory: %s", e)

        # Terminate any running worker (now also handled by resource tracker)
        if hasattr(self, "vfi_worker") and self.vfi_worker and self.vfi_worker.isRunning():
            LOGGER.info("Terminating VFI worker thread")
            self.vfi_worker.terminate()
            self.vfi_worker.wait(1000)

        # Accept the close event
        if event:
            event.accept()

    def _connect_settings_tab(self) -> None:
        """Connect settings tab signals to handlers."""
        if hasattr(self, "settings_tab"):
            # Connect theme change signal
            self.settings_tab.themeChanged.connect(self._on_settings_theme_changed)
            # Connect general settings change signal
            self.settings_tab.settingsChanged.connect(self._on_settings_changed)

    def _on_settings_theme_changed(self, theme_name: str) -> None:
        """Handle theme change from settings tab."""
        try:
            app = QApplication.instance()
            if app:
                self.theme_manager.change_theme(cast("QApplication", app), theme_name)
                LOGGER.info("Theme changed to: %s", theme_name)
            else:
                LOGGER.error("No QApplication instance found for theme change")
        except Exception:
            LOGGER.exception("Failed to change theme")

    def _on_settings_changed(self) -> None:
        """Handle general settings changes."""
        try:
            if hasattr(self, "settings_tab"):
                current_settings = self.settings_tab.get_current_settings()
                LOGGER.debug("Settings changed: %s", current_settings)
                # Save settings if auto-save is enabled
                if current_settings.get("app", {}).get("auto_save", True):
                    self.saveSettings()
        except Exception:
            LOGGER.exception("Failed to handle settings change")
