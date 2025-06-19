#!/usr/bin/env python3
"""Test and demonstrate the UI enhancement features."""

import sys
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from goesvfi.utils.ui_enhancements import (
    AnimatedProgressBar,
    DragDropWidget,
    FadeInNotification,
    HelpButton,
    LoadingSpinner,
    ProgressTracker,
    ShortcutManager,
    TooltipHelper,
    create_status_widget,
)


class TestWindow(QMainWindow):
    """Test window to demonstrate UI enhancements."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("UI Enhancements Demo")
        self.setGeometry(100, 100, 800, 600)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 1. Buttons with tooltips
        btn1 = QPushButton("Button with Tooltip")
        TooltipHelper.add_tooltip(btn1, "fps")
        layout.addWidget(btn1)

        # 2. Help button
        help_btn = HelpButton("encoder", self)
        help_btn.help_requested.connect(lambda topic: print(f"Help requested: {topic}"))
        layout.addWidget(help_btn)

        # 3. Animated progress bar
        self.progress_bar = AnimatedProgressBar()
        layout.addWidget(self.progress_bar)

        # 4. Status widget
        self.status_widget = create_status_widget()
        layout.addWidget(self.status_widget)

        # 5. Loading spinner
        self.spinner = LoadingSpinner(self)
        self.spinner.move(750, 10)

        # 6. Notification
        self.notification = FadeInNotification(self)

        # 7. Progress tracker
        self.progress_tracker = ProgressTracker()
        self.progress_tracker.stats_updated.connect(self.update_stats)

        # 8. Keyboard shortcuts
        self.shortcuts = ShortcutManager(self)
        self.shortcuts.add_shortcut(
            "test",
            "Ctrl+T",
            lambda: self.notification.show_message("Test shortcut triggered!"),
            "Test shortcut",
        )

        # 9. Enable drag and drop
        self.drag_drop = DragDropWidget()
        self.drag_drop.files_dropped.connect(self.handle_dropped_files)
        self.setAcceptDrops(True)
        self.dragEnterEvent = self.drag_drop.dragEnterEvent
        self.dragLeaveEvent = self.drag_drop.dragLeaveEvent
        self.dropEvent = self.drag_drop.dropEvent

        # Control buttons
        start_btn = QPushButton("Start Demo")
        start_btn.clicked.connect(self.start_demo)
        layout.addWidget(start_btn)

        stop_btn = QPushButton("Stop Demo")
        stop_btn.clicked.connect(self.stop_demo)
        layout.addWidget(stop_btn)

        show_shortcuts_btn = QPushButton("Show Shortcuts (F1)")
        show_shortcuts_btn.clicked.connect(self.shortcuts.show_shortcuts)
        layout.addWidget(show_shortcuts_btn)

        # Add F1 shortcut for help
        self.shortcuts.add_shortcut(
            "help", "F1", self.shortcuts.show_shortcuts, "Show keyboard shortcuts"
        )

    def start_demo(self):
        """Start the demo animations."""
        self.spinner.start()
        self.progress_tracker.start(total_items=100)
        self.notification.show_message("Demo started!")

        # Simulate progress
        self.progress_value = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)  # Update every 100ms

    def stop_demo(self):
        """Stop the demo animations."""
        if hasattr(self, "timer"):
            self.timer.stop()

        self.spinner.stop()
        self.progress_tracker.stop()
        self.notification.show_message("Demo stopped!")

        # Reset progress
        self.progress_bar.setValue(0)
        self.status_widget.progress_bar.setValue(0)
        self.status_widget.status_label.setText("Ready")
        self.status_widget.speed_label.setText("")
        self.status_widget.eta_label.setText("")

    def update_progress(self):
        """Update progress simulation."""
        self.progress_value += 1
        if self.progress_value > 100:
            self.stop_demo()
            self.notification.show_message("Demo completed!")
            self.progress_bar.set_state("success")
            return

        # Update progress bar
        self.progress_bar.setValue(self.progress_value)

        # Update tracker (simulate data transfer)
        self.progress_tracker.update_progress(
            items=1, bytes_transferred=1024 * 1024  # 1MB
        )

    def update_stats(self, stats):
        """Update status display with stats."""
        self.status_widget.status_label.setText(f"Processing... {self.progress_value}%")
        self.status_widget.speed_label.setText(f"Speed: {stats['speed_human']}")
        self.status_widget.eta_label.setText(f"ETA: {stats['eta_human']}")
        self.status_widget.progress_bar.setValue(int(stats["progress_percent"]))

    def handle_dropped_files(self, file_paths):
        """Handle dropped files."""
        if file_paths:
            self.notification.show_message(f"Dropped {len(file_paths)} file(s)")
            print(f"Files dropped: {file_paths}")


def main():
    """Run the demo."""
    app = QApplication(sys.argv)

    # Set dark theme
    app.setStyleSheet(
        """
        QWidget {
            background-color: #2a2a2a;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #3a3a3a;
            border: 1px solid #555;
            padding: 5px 15px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
    """
    )

    window = TestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
