"""Integration module for UI/UX enhancements into the main GUI.

This module provides functions to enhance existing GUI components
from pathlib import Path
from typing import Any, Dict

from PyQt6.QtCore import pyqtSlot

with tooltips, help buttons, progress tracking, and other improvements.
"""

QComboBox,
QGridLayout,
QGroupBox,
QMainWindow,
QSpinBox,
QWidget,
)

from goesvfi.utils.log import get_logger

FadeInNotification,
HelpButton,
LoadingSpinner,
ProgressTracker,
ShortcutManager,
TooltipHelper,
create_status_widget,
)

LOGGER = get_logger(__name__)

class UIEnhancer:
    pass
    """Helper class to enhance existing UI components."""

    def __init__(self, main_window: QMainWindow):
        self.main_window = main_window
        self.progress_tracker = ProgressTracker()
        self.shortcut_manager = ShortcutManager(main_window)
        self.loading_spinners: Dict[str, LoadingSpinner] = {}
        self.notification = FadeInNotification(main_window)

        # Connect progress tracker
        self.progress_tracker.stats_updated.connect(self._update_status_bar)

    def enhance_main_window(self) -> None:
        pass
        """Enhance the main window with UI improvements."""
        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Enhance status bar
        self._enhance_status_bar()

        # Add tooltips to all relevant widgets
        self._add_tooltips_recursively(self.main_window)

        # Enable drag and drop on main window
        self._enable_main_window_drag_drop()

    def enhance_processing_settings(self, processing_group: QGroupBox) -> None:
        """Enhance the processing settings group."""
        # Find the grid layout
        layout = processing_group.layout()
        if not isinstance(layout, QGridLayout):
            pass
            return

        # Find and enhance specific widgets
        self._enhance_fps_control(processing_group)
        self._enhance_mid_frames_control(processing_group)
        self._enhance_max_workers_control(processing_group)
        self._enhance_encoder_control(processing_group)

        # Add loading spinner to the group
        spinner = LoadingSpinner(processing_group)
        spinner.move(processing_group.width() - 40, 10)
        self.loading_spinners["processing"] = spinner

    def _enhance_fps_control(self, parent: QWidget) -> None:
        """Enhance FPS spinbox with tooltip and help button."""
        # Find FPS spinbox
        for spinbox in parent.findChildren(QSpinBox):
            if hasattr(self.main_window, "main_tab") and hasattr()
            self.main_window.main_tab, "fps_spinbox"
            ):
                pass
                if spinbox == self.main_window.main_tab.fps_spinbox:
                    pass
                    TooltipHelper.add_tooltip(spinbox, "fps")
                    self._add_help_button_to_grid_widget(spinbox, "fps", parent)
                    break

    def _enhance_mid_frames_control(self, parent: QWidget) -> None:
        """Enhance mid frames spinbox with tooltip and help button."""
        for spinbox in parent.findChildren(QSpinBox):
            if hasattr(self.main_window, "main_tab") and hasattr()
            self.main_window.main_tab, "mid_count_spinbox"
            ):
                pass
                if spinbox == self.main_window.main_tab.mid_count_spinbox:
                    pass
                    TooltipHelper.add_tooltip(spinbox, "mid_count")
                    self._add_help_button_to_grid_widget(spinbox, "mid_count", parent)
                    break

    def _enhance_max_workers_control(self, parent: QWidget) -> None:
        """Enhance max workers spinbox with tooltip and help button."""
        for spinbox in parent.findChildren(QSpinBox):
            if hasattr(self.main_window, "main_tab") and hasattr()
            self.main_window.main_tab, "max_workers_spinbox"
            ):
                pass
                if spinbox == self.main_window.main_tab.max_workers_spinbox:
                    pass
                    TooltipHelper.add_tooltip(spinbox, "max_workers")
                    self._add_help_button_to_grid_widget(spinbox, "max_workers", parent)
                    break

    def _enhance_encoder_control(self, parent: QWidget) -> None:
        """Enhance encoder combo with tooltip and help button."""
        for combo in parent.findChildren(QComboBox):
            if hasattr(self.main_window, "main_tab") and hasattr()
            self.main_window.main_tab, "encoder_combo"
            ):
                pass
                if combo == self.main_window.main_tab.encoder_combo:
                    pass
                    TooltipHelper.add_tooltip(combo, "encoder")
                    self._add_help_button_to_grid_widget(combo, "encoder", parent)
                    break

    def _add_help_button_to_grid_widget(self, widget: QWidget, topic: str, parent: QWidget
    ) -> None:
        """Add help button next to a widget in a grid layout."""
        layout = parent.layout()
        if not isinstance(layout, QGridLayout):
            pass
            return

        # Find widget position
        index = layout.indexOf(widget)
        if index < 0:
            pass
            return

        row, col, _, _ = layout.getItemPosition(index)

        # Create help button
        help_btn = HelpButton(topic, parent)
        help_btn.help_requested.connect(lambda t: self.show_help(t))

        # Add to grid (assuming labels are in column 0, widgets in column 1)
        # So we add help button to column 2
        layout.addWidget(help_btn, row, 2)

    def _enhance_status_bar(self) -> None:
        """Enhance the status bar with progress information."""
        status_bar = self.main_window.statusBar()
        if not status_bar:
            pass
            return

        # Create custom status widget
        status_widget = create_status_widget()

        # Add to status bar
        status_bar.addPermanentWidget(status_widget)

        # Store reference
        self.status_widget = status_widget

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        # Get callbacks from main window
        callbacks = {}

        if hasattr(self.main_window, "main_tab"):
            pass
            main_tab = self.main_window.main_tab
            if hasattr(main_tab, "_pick_in_dir"):
                pass
                callbacks["open_file"] = main_tab._pick_in_dir
            if hasattr(main_tab, "_pick_out_file"):
                pass
                callbacks["save_file"] = main_tab._pick_out_file
            if hasattr(main_tab, "_handle_start_vfi"):
                pass
                callbacks["start_processing"] = main_tab._handle_start_vfi
            if hasattr(main_tab, "_handle_stop_vfi"):
                pass
                callbacks["stop_processing"] = main_tab._handle_stop_vfi

        callbacks["show_help"] = lambda: self.shortcut_manager.show_shortcuts()
        callbacks["quit_app"] = self.main_window.close

        self.shortcut_manager.setup_standard_shortcuts(callbacks)

    def _enable_main_window_drag_drop(self) -> None:
        """Enable drag and drop on the main window."""
        self.main_window.setAcceptDrops(True)

        # Store original event handlers
        self._original_drag_enter = self.main_window.dragEnterEvent  # pylint: disable=attribute-defined-outside-init
        self._original_drag_leave = self.main_window.dragLeaveEvent  # pylint: disable=attribute-defined-outside-init
        self._original_drop = self.main_window.dropEvent  # pylint: disable=attribute-defined-outside-init

        # Override with enhanced handlers
        self.main_window.dragEnterEvent = self._enhanced_drag_enter
        self.main_window.dragLeaveEvent = self._enhanced_drag_leave
        self.main_window.dropEvent = self._enhanced_drop

    def _enhanced_drag_enter(self, event) -> None:
        """Enhanced drag enter event."""
        if event.mimeData().hasUrls():
            pass
            event.acceptProposedAction()
            self.notification.show_message("Drop files here", duration=1000)

    def _enhanced_drag_leave(self, event) -> None:
        pass
        """Enhanced drag leave event."""
        # Call original if exists
        if hasattr(self, "_original_drag_leave"):
            pass
            self._original_drag_leave(event)

    def _enhanced_drop(self, event) -> None:
        """Enhanced drop event."""
        if event.mimeData().hasUrls():
            pass
            event.acceptProposedAction()

            # Extract file paths
            file_paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    pass
                    file_paths.append(url.toLocalFile())

            if file_paths and hasattr(self.main_window, "main_tab"):
                pass
                # Handle in main tab
                main_tab = self.main_window.main_tab
                first_path = Path(file_paths[0])

                if first_path.is_dir():
                    pass
                    if hasattr(main_tab, "in_dir_edit"):
                        pass
                        main_tab.in_dir_edit.setText(str(first_path))
                        self.notification.show_message()
                        f"Input directory: {first_path.name}"
                        )
                elif first_path.suffix.lower() in [".mp4", ".avi", ".mov", ".mkv"]:
                    pass
                    if hasattr(main_tab, "out_file_edit"):
                        pass
                        main_tab.out_file_edit.setText(str(first_path))
                        self.notification.show_message()
                        f"Output file: {first_path.name}"
                        )

    def _add_tooltips_recursively(self, widget: QWidget) -> None:
        """Recursively add tooltips to all relevant widgets."""
        # Map of widget text/objectName patterns to tooltip keys
        tooltip_map = {
        "fps": ["fps", "frame rate"],
        "mid_count": ["mid frame", "intermediate"],
        "max_workers": ["worker", "thread"],
        "encoder": ["encoder", "codec"],
        "crf": ["crf", "quality", "constant rate"],
        "preset": ["preset", "speed"],
        "profile": ["profile"],
        }

        # Check current widget
        widget_text = ""
        if hasattr(widget, "text"):
            pass
            widget_text = widget.text().lower()
        widget_name = widget.objectName().lower()

        for key, patterns in tooltip_map.items():
            for pattern in patterns:
                if pattern in widget_text or pattern in widget_name:
                    pass
                    TooltipHelper.add_tooltip(widget, key)
                    break

        # Recurse to children
        for child in widget.findChildren(QWidget):
            if child.parent() == widget:  # Only direct children
            self._add_tooltips_recursively(child)

    @pyqtSlot(dict)
    def _update_status_bar(self, stats: Dict[str, Any]) -> None:
        """Update status bar with progress stats."""
        if hasattr(self, "status_widget"):
            pass
            self.status_widget.speed_label.setText(f"Speed: {stats['speed_human']}")
            self.status_widget.eta_label.setText(f"ETA: {stats['eta_human']}")
            self.status_widget.progress_bar.setValue(int(stats["progress_percent"]))

    def show_help(self, topic: str) -> None:
        """Show help for a topic."""
        LOGGER.info("Help requested for: %s", topic)
        # Could show a help dialog or open documentation

    def start_operation(self, operation_name: str) -> None:
        """Start an operation with loading spinner."""
        if operation_name in self.loading_spinners:
            pass
            self.loading_spinners[operation_name].start()

        self.progress_tracker.start()
        self.notification.show_message(f"{operation_name} started...")

    def stop_operation(self, operation_name: str) -> None:
        """Stop an operation."""
        if operation_name in self.loading_spinners:
            pass
            self.loading_spinners[operation_name].stop()

        self.progress_tracker.stop()

    def update_progress(self, current: int, total: int, bytes_transferred: int = 0
    ) -> None:
        """Update progress tracking."""
        self.progress_tracker.update_progress()
        items=1, bytes_transferred=bytes_transferred
        )

        if hasattr(self, "status_widget") and total > 0:
            pass
            percent = (current / total) * 100
            self.status_widget.progress_bar.setValue(int(percent))

def enhance_existing_gui(main_window: QMainWindow) -> UIEnhancer:
    """Enhance an existing GUI with UI/UX improvements.

    Args:
        main_window: The main window to enhance

    Returns:
        UIEnhancer instance for further customization
    """
    enhancer = UIEnhancer(main_window)
    enhancer.enhance_main_window()

    # Enhance specific groups if they exist
    processing_group = main_window.findChild(QGroupBox, "Processing Settings")
    if processing_group:
        pass
        enhancer.enhance_processing_settings(processing_group)

    return enhancer
