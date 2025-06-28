# goesvfi/gui_tabs/main_tab_enhanced.py
"""Enhanced main tab with UI/UX improvements."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from goesvfi.gui_tabs.main_tab import MainTab
from goesvfi.utils import log

try:
    from goesvfi.utils.ui_enhancements import (
        DragDropWidget,
        FadeInNotification,
        HelpButton,
        LoadingSpinner,
        ProgressTracker,
        ShortcutManager,
        TooltipHelper,
        create_status_widget,
    )
except ImportError:
    # Provide dummy implementations if module is missing
    DragDropWidget = None  # type: ignore
    FadeInNotification = None  # type: ignore
    HelpButton = None  # type: ignore
    LoadingSpinner = None  # type: ignore
    ProgressTracker = None  # type: ignore
    ShortcutManager = None  # type: ignore
    TooltipHelper = None  # type: ignore
    create_status_widget = None  # type: ignore

LOGGER = log.get_logger(__name__)


class EnhancedMainTab(MainTab):
    """Enhanced main tab with improved UI/UX features."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Initialize UI enhancement components
        self._progress_tracker = ProgressTracker()
        self._progress_tracker.stats_updated.connect(self._update_progress_stats)

        self._shortcut_manager = ShortcutManager(self)
        self._notification = FadeInNotification(self)

        # Add UI enhancements after parent initialization
        self._enhance_ui()

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        # Enable drag and drop on the main widget
        self._enable_drag_drop()

    def _enhance_ui(self) -> None:
        """Add UI enhancements to existing widgets."""
        # Add tooltips to processing settings
        if hasattr(self, "fps_spinbox"):
            TooltipHelper.add_tooltip(self.fps_spinbox, "fps")
            self._add_help_button_to_widget(self.fps_spinbox, "fps")

        if hasattr(self, "mid_count_spinbox"):
            TooltipHelper.add_tooltip(self.mid_count_spinbox, "mid_count")
            self._add_help_button_to_widget(self.mid_count_spinbox, "mid_count")

        if hasattr(self, "max_workers_spinbox"):
            TooltipHelper.add_tooltip(self.max_workers_spinbox, "max_workers")
            self._add_help_button_to_widget(self.max_workers_spinbox, "max_workers")

        if hasattr(self, "encoder_combo"):
            TooltipHelper.add_tooltip(self.encoder_combo, "encoder")
            self._add_help_button_to_widget(self.encoder_combo, "encoder")

        # Add tooltips to file path widgets
        if hasattr(self, "in_dir_edit"):
            TooltipHelper.add_tooltip(self.in_dir_edit, "input_path")

        if hasattr(self, "out_file_edit"):
            TooltipHelper.add_tooltip(self.out_file_edit, "output_path")

        # Add tooltips to crop controls
        if hasattr(self, "crop_button"):
            TooltipHelper.add_tooltip(self.crop_button, "crop_enable")

        if hasattr(self, "clear_crop_button"):
            TooltipHelper.add_tooltip(self.clear_crop_button, "crop_preview")

        # Create and add status widget
        self._create_status_widget()

        # Add loading spinner (initially hidden)
        self._loading_spinner = LoadingSpinner(self)
        self._loading_spinner.move(10, 10)

    def _add_help_button_to_widget(self, widget: QWidget, topic: str) -> None:
        """Add a help button next to a widget."""
        # Find the widget's parent layout
        parent_widget = widget.parentWidget()
        if not parent_widget:
            return

        # Try to find the widget in a grid layout
        layout = parent_widget.layout()
        if not layout:
            return

        if isinstance(layout, QGridLayout):
            # Find widget position in grid
            index = layout.indexOf(widget)
            if index >= 0:
                position = layout.getItemPosition(index)
                if position and len(position) >= 2:
                    row, col = position[0], position[1]
                    if row is not None and col is not None:
                        # Create help button
                        help_btn = HelpButton(topic, parent_widget)
                        help_btn.help_requested.connect(self._show_help)

                        # Add help button to the right of the widget
                        layout.addWidget(help_btn, row, col + 1)

    def _create_status_widget(self) -> None:
        """Create and add the status widget to the bottom of the tab."""
        # Find the main layout
        main_layout = self.layout()
        if not main_layout:
            return

        # Create status widget
        self._status_widget = create_status_widget(self)

        # Add to bottom of layout
        if isinstance(main_layout, QVBoxLayout):
            main_layout.addWidget(self._status_widget)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        callbacks = {
            "open_file": self._pick_in_dir,
            "save_file": self._pick_out_file,
            "start_processing": self._handle_start_vfi,
            "stop_processing": self._handle_stop_vfi,
            "toggle_preview": self._toggle_preview,
            "show_help": self._show_all_help,
        }

        self._shortcut_manager.setup_standard_shortcuts(callbacks)

    def _enable_drag_drop(self) -> None:
        """Enable drag and drop support."""
        # Make the entire tab accept drops
        self.setAcceptDrops(True)

        # Create drag drop handler
        self._drag_handler = DragDropWidget()
        self._drag_handler.files_dropped.connect(self._handle_dropped_files)

        # Store original drag/drop events
        self._original_dragEnterEvent = self.dragEnterEvent
        self._original_dragLeaveEvent = self.dragLeaveEvent
        self._original_dropEvent = self.dropEvent

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        """Handle drag enter event."""
        if self._drag_handler:
            self._drag_handler.dragEnterEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent | None) -> None:
        """Handle drag leave event."""
        if self._drag_handler:
            self._drag_handler.dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent | None) -> None:
        """Handle drop event."""
        if self._drag_handler:
            self._drag_handler.dropEvent(event)

    @pyqtSlot(list)
    def _handle_dropped_files(self, file_paths: list[str]) -> None:
        """Handle dropped files."""
        if not file_paths:
            return

        # Check if it's a directory or video files
        first_path = Path(file_paths[0])

        if first_path.is_dir():
            # Set as input directory
            self.in_dir_edit.setText(str(first_path))
            self._notification.show_message(f"Input directory set to: {first_path.name}")
        elif first_path.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
            # Set as output file
            self.out_file_edit.setText(str(first_path))
            self._notification.show_message(f"Output file set to: {first_path.name}")
        else:
            # Try to find image sequence
            image_extensions = [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
            if first_path.suffix.lower() in image_extensions:
                # Set parent directory as input
                self.in_dir_edit.setText(str(first_path.parent))
                self._notification.show_message(f"Input directory set to: {first_path.parent.name}")

    @pyqtSlot(dict)
    def _update_progress_stats(self, stats: dict[str, Any]) -> None:
        """Update progress statistics in the UI."""
        if hasattr(self, "_status_widget"):
            self._status_widget.status_label.setText("Processing...")
            self._status_widget.speed_label.setText(f"Speed: {stats['speed_human']}")
            self._status_widget.eta_label.setText(f"ETA: {stats['eta_human']}")
            self._status_widget.progress_bar.setValue(int(stats["progress_percent"]))

    def _show_help(self, topic: str) -> None:
        """Show help for a specific topic."""
        LOGGER.debug("Help requested for topic: %s", topic)

    def _show_all_help(self) -> None:
        """Show all keyboard shortcuts."""
        self._shortcut_manager.show_shortcuts()

    def _toggle_preview(self) -> None:
        """Toggle preview visibility."""
        # Implementation depends on your preview system
        LOGGER.debug("Toggle preview requested")

    def _handle_start_vfi(self) -> None:
        """Override to add progress tracking."""
        # Show loading spinner
        if hasattr(self, "_loading_spinner"):
            self._loading_spinner.start()

        # Start progress tracking
        self._progress_tracker.start()

        # Parent class doesn't have _handle_start_vfi method
        # This is an enhancement-specific method

        # Show notification
        self._notification.show_message("Processing started...")

    def _handle_stop_vfi(self) -> None:
        """Override to stop progress tracking."""
        # Hide loading spinner
        if hasattr(self, "_loading_spinner"):
            self._loading_spinner.stop()

        # Reset progress tracking
        self._progress_tracker.set_progress(0)
        self._progress_tracker.set_status("Stopped")

        # Parent class doesn't have _handle_stop_vfi method
        # This is an enhancement-specific method

        # Show notification
        self._notification.show_message("Processing stopped")

        # Update status
        if hasattr(self, "_status_widget"):
            self._status_widget.status_label.setText("Ready")
            self._status_widget.speed_label.setText("")
            self._status_widget.eta_label.setText("")
            self._status_widget.progress_bar.setValue(0)

    def update_progress(self, current: int, total: int) -> None:
        """Update progress information."""
        if hasattr(self, "_progress_tracker"):
            self._progress_tracker.update_progress(items=1)

        if hasattr(self, "_status_widget") and total > 0:
            percent = (current / total) * 100
            self._status_widget.progress_bar.setValue(int(percent))

    def update_transfer_stats(self, bytes_transferred: int) -> None:
        """Update transfer statistics."""
        if hasattr(self, "_progress_tracker"):
            self._progress_tracker.update_progress(bytes_transferred=bytes_transferred)
