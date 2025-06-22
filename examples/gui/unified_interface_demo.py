#!/usr/bin/env python3
"""
Test script for unified interface with shared components

This script demonstrates the new unified interface components, including:
1. Shared preview panel with bookmarking and caching
2. Sidebar settings panel with collapsible sections
3. Cross-tab interactions and data sharing
"""

import io
import logging
import sys
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create stub implementations for missing components
from PyQt6.QtCore import QDate, QTime, pyqtSignal
from PyQt6.QtWidgets import QDateEdit, QTimeEdit

# Import our shared components
from goesvfi.integrity_check.shared_components import PreviewMetadata


class SharedPreviewPanel(QWidget):
    """Stub implementation of SharedPreviewPanel."""

    previewSelected = pyqtSignal(str, object)  # key, metadata
    previewBookmarked = pyqtSignal(str, bool)  # key, is_bookmarked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._previews = {}

        layout = QVBoxLayout(self)
        self.preview_label = QLabel("Preview Panel")
        layout.addWidget(self.preview_label)

    def addPreview(self, key, pixmap, metadata):
        """Add a preview."""
        self._previews[key] = {"pixmap": pixmap, "metadata": metadata}

    def getPreview(self, key):
        """Get preview data."""
        return self._previews.get(key)


class SidebarSettingsPanel(QWidget):
    """Stub implementation of SidebarSettingsPanel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sections = {}

        layout = QVBoxLayout(self)

        # Add date/time controls for testing
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime.currentTime())

        layout.addWidget(self.date_edit)
        layout.addWidget(self.time_edit)

    def show_section(self, section_name, visible):
        """Show or hide a section."""
        self._sections[section_name] = visible

    def set_date_time(self, date_time):
        """Set the date and time."""
        self.date_edit.setDate(date_time.date())
        self.time_edit.setTime(date_time.time())


# Helper function to create sample images
def create_sample_image(channel=13, size=(600, 400), enhance=False):
    """Create a sample image for testing."""
    img = Image.new("RGB", size, color=(40, 40, 40))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(size[1]):
        color_value = int(200 * (y / size[1]))
        if channel <= 6:  # Visible
            draw.line(
                [(0, y), (size[0], y)],
                fill=(
                    150 + color_value // 2,
                    150 + color_value // 2,
                    220 - color_value,
                ),
            )
        elif channel <= 10:  # Water vapor
            draw.line([(0, y), (size[0], y)], fill=(20, 20, 120 + color_value))
        else:  # IR
            if enhance:
                # Enhanced IR (colorized)
                if y < size[1] / 3:
                    draw.line([(0, y), (size[0], y)], fill=(220, 100 - color_value // 2, 0))
                else:
                    draw.line(
                        [(0, y), (size[0], y)],
                        fill=(0, 100 + color_value // 2, 200 - color_value // 2),
                    )
            else:
                # Standard IR (grayscale)
                c = 40 + color_value
                draw.line([(0, y), (size[0], y)], fill=(c, c, c))

    # Add header
    draw.rectangle([(0, 0), (size[0], 30)], fill=(25, 52, 152))

    # Add channel info
    channel_name = f"Band {channel}"
    if channel == 13:
        channel_name = "Clean IR (Band 13)"
    elif channel == 8:
        channel_name = "Water Vapor (Band 8)"
    elif channel == 100:
        channel_name = "True Color RGB"

    # Create fonts - fallback to default if Arial not available
    try:
        font = ImageFont.truetype("Arial", 18)
        small_font = ImageFont.truetype("Arial", 12)
    except IOError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Add title text
    draw.text((20, 7), f"GOES-16 {channel_name}", fill=(255, 255, 255), font=font)

    # Add timestamp at bottom
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle([(0, size[1] - 25), (size[0], size[1])], fill=(25, 52, 152))
    draw.text((10, size[1] - 20), timestamp, fill=(255, 255, 255), font=small_font)

    # Add "features" (circles simulating clouds/weather)
    import random

    random.seed(channel)  # Make it reproducible but different per channel

    # Calculate center (not directly used but useful for context)
    # size[0] // 2, size[1] // 2 would be the center coordinates

    for i in range(10):
        x = random.randint(50, size[0] - 50)
        y = random.randint(50, size[1] - 80)
        radius = random.randint(10, 40)

        if enhance and channel > 10:
            # IR enhanced - cool/warm colors
            temp = random.random()
            if temp < 0.3:
                color = (255, 50, 0, 180)  # Cold
            elif temp < 0.6:
                color = (255, 180, 0, 180)  # Medium
            else:
                color = (0, 180, 255, 180)  # Warm
        elif channel <= 6:
            # Visible - white clouds
            color = (255, 255, 255, 150)
        elif channel <= 10:
            # Water vapor - blue shades
            color = (100, 100, 200 + random.randint(0, 55), 180)
        else:
            # IR standard - grayscale
            gray = 200 + random.randint(0, 55)
            color = (gray, gray, gray, 150)

        draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], fill=color)

    return img


class TestWindow(QMainWindow):
    """Test window for demonstrating unified interface components."""

    def __init__(self):
        super().__init__()

        # Set window properties
        self.setWindowTitle("Unified Interface Demo")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create header
        header = QWidget()
        header.setMaximumHeight(60)
        header.setStyleSheet("background-color: #2c3e50;")
        header_layout = QHBoxLayout(header)

        title = QLabel("GOES Imagery Unified Interface Demo")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        # Add header to main layout
        layout.addWidget(header)

        # Create content area with splitter
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create left side (simulated tab content)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Create tab switcher
        tab_switcher = QWidget()
        tab_switcher.setMaximumHeight(40)
        switcher_layout = QHBoxLayout(tab_switcher)
        switcher_layout.setContentsMargins(5, 0, 5, 0)

        # Tab buttons
        self.tab1_btn = QPushButton("File Integrity")
        self.tab2_btn = QPushButton("GOES Imagery")

        # Style buttons like tabs
        button_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #b0b0b0;
                border: none;
                padding: 5px 10px;
                border-bottom: 2px solid transparent;
            }
            QPushButton:checked, QPushButton:pressed {
                color: white;
                background-color: #444444;
                border-bottom: 2px solid #3498db;
            }
        """
        self.tab1_btn.setStyleSheet(button_style)
        self.tab2_btn.setStyleSheet(button_style)
        self.tab1_btn.setCheckable(True)
        self.tab2_btn.setCheckable(True)
        self.tab1_btn.setChecked(True)

        # Add buttons to layout
        switcher_layout.addWidget(self.tab1_btn)
        switcher_layout.addWidget(self.tab2_btn)
        switcher_layout.addStretch()

        # Tab content
        self.tab_stack = QStackedWidget()

        # Tab 1 content (File Integrity simulation)
        tab1_content = QWidget()
        tab1_layout = QVBoxLayout(tab1_content)

        integrity_group = QGroupBox("File Integrity Actions")
        integrity_layout = QVBoxLayout(integrity_group)

        # Add some buttons to simulate actions
        scan_btn = QPushButton("Scan Directory")
        scan_btn.clicked.connect(lambda: self.add_sample_preview(13, "Integrity Scan"))

        verify_btn = QPushButton("Verify Files")
        verify_btn.clicked.connect(lambda: self.add_sample_preview(8, "File Verification"))

        reconcile_btn = QPushButton("Reconcile Files")
        reconcile_btn.clicked.connect(lambda: self.add_sample_preview(14, "File Reconciliation"))

        # Add to layout
        integrity_layout.addWidget(scan_btn)
        integrity_layout.addWidget(verify_btn)
        integrity_layout.addWidget(reconcile_btn)
        integrity_layout.addStretch()

        tab1_layout.addWidget(integrity_group)
        tab1_layout.addStretch()

        # Tab 2 content (GOES Imagery simulation)
        tab2_content = QWidget()
        tab2_layout = QVBoxLayout(tab2_content)

        imagery_group = QGroupBox("GOES Imagery Actions")
        imagery_layout = QVBoxLayout(imagery_group)

        # Add imagery action buttons
        preview_btn = QPushButton("Preview IR")
        preview_btn.clicked.connect(lambda: self.add_sample_preview(13, "IR Preview", enhanced=True))

        wv_btn = QPushButton("Preview Water Vapor")
        wv_btn.clicked.connect(lambda: self.add_sample_preview(8, "Water Vapor", enhanced=True))

        true_color_btn = QPushButton("Preview True Color")
        true_color_btn.clicked.connect(lambda: self.add_sample_preview(100, "True Color"))

        # Add to layout
        imagery_layout.addWidget(preview_btn)
        imagery_layout.addWidget(wv_btn)
        imagery_layout.addWidget(true_color_btn)
        imagery_layout.addStretch()

        # Add cross-tab action buttons
        cross_tab_group = QGroupBox("Cross-Tab Actions")
        cross_layout = QVBoxLayout(cross_tab_group)

        verify_imagery_btn = QPushButton("Verify This Imagery")
        verify_imagery_btn.setStyleSheet("background-color: #2980b9; color: white;")

        process_verified_btn = QPushButton("Process Verified Files")
        process_verified_btn.setStyleSheet("background-color: #27ae60; color: white;")

        cross_layout.addWidget(verify_imagery_btn)
        cross_layout.addWidget(process_verified_btn)

        # Add to main layout
        tab2_layout.addWidget(imagery_group)
        tab2_layout.addWidget(cross_tab_group)
        tab2_layout.addStretch()

        # Add content to stacked widget
        self.tab_stack.addWidget(tab1_content)
        self.tab_stack.addWidget(tab2_content)

        # Connect tab buttons
        self.tab1_btn.clicked.connect(lambda: self.switch_tab(0))
        self.tab2_btn.clicked.connect(lambda: self.switch_tab(1))

        # Add components to left layout
        left_layout.addWidget(tab_switcher)
        left_layout.addWidget(self.tab_stack)

        # Create shared preview panel (center)
        self.preview_panel = SharedPreviewPanel()

        # Create settings sidebar (right)
        self.settings_panel = SidebarSettingsPanel()

        # Add widgets to splitter
        self.content_splitter.addWidget(left_widget)
        self.content_splitter.addWidget(self.preview_panel)
        self.content_splitter.addWidget(self.settings_panel)

        # Set initial sizes (main:preview:settings)
        self.content_splitter.setSizes([300, 400, 300])

        # Add splitter to main layout
        layout.addWidget(self.content_splitter, 1)  # 1 = stretch factor

        # Create status bar
        self.statusBar().showMessage("Ready")

        # Connect signals
        self.preview_panel.previewSelected.connect(self.on_preview_selected)
        self.preview_panel.previewBookmarked.connect(self.on_preview_bookmarked)

        # Connect settings signals
        self.settings_panel.date_edit.dateChanged.connect(self.on_date_changed)
        self.settings_panel.time_edit.timeChanged.connect(self.on_time_changed)

        # Show some sample previews to demonstrate functionality
        QTimer.singleShot(500, self.add_initial_samples)

    def switch_tab(self, index):
        """Switch to the specified tab."""
        self.tab_stack.setCurrentIndex(index)
        self.tab1_btn.setChecked(index == 0)
        self.tab2_btn.setChecked(index == 1)

        # Update settings context based on active tab
        if index == 0:  # File Integrity
            self.settings_panel.show_section("visualization", False)
            self.settings_panel.show_section("advanced", False)
        else:  # GOES Imagery
            self.settings_panel.show_section("visualization", True)
            self.settings_panel.show_section("advanced", True)

        self.statusBar().showMessage(f"Switched to {'File Integrity' if index == 0 else 'GOES Imagery'} tab")

    def add_sample_preview(self, channel, source, enhanced=False):
        """Add a sample preview to the shared preview panel."""
        # Create sample image
        img = create_sample_image(channel, enhance=enhanced)

        # Convert to QPixmap
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        qimg = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimg)

        # Create metadata
        from goesvfi.integrity_check.goes_imagery import ProductType

        metadata = PreviewMetadata(
            channel=channel,
            product_type=ProductType.FULL_DISK,  # Default to full disk
            date_time=datetime.now(),
            source=source,
        )

        # Add to preview panel
        key = metadata.get_key()
        self.preview_panel.addPreview(key, pixmap, metadata)

        self.statusBar().showMessage(f"Added preview: {metadata.get_display_name()}")

    def add_initial_samples(self):
        """Add some initial sample previews to demonstrate functionality."""
        # Add a few different types of previews
        self.add_sample_preview(13, "Initial Sample")
        QTimer.singleShot(
            100,
            lambda: self.add_sample_preview(8, "Water Vapor Example", enhanced=True),
        )
        QTimer.singleShot(200, lambda: self.add_sample_preview(100, "True Color Example"))

    def on_preview_selected(self, key, metadata):
        """Handle preview selection in the preview panel."""
        # Update status
        self.statusBar().showMessage(f"Selected preview: {metadata.get_display_name()}")

        # Update settings to match metadata
        self.settings_panel.set_date_time(metadata.date_time)

        # Could update other settings based on metadata

    def on_preview_bookmarked(self, key, is_bookmarked):
        """Handle preview bookmark status change."""
        # Get preview data
        preview_data = self.preview_panel.getPreview(key)
        if not preview_data:
            return

        metadata = preview_data["metadata"]
        status = "Bookmarked" if is_bookmarked else "Unbookmarked"

        self.statusBar().showMessage(f"{status} preview: {metadata.get_display_name()}")

    def on_date_changed(self, new_date):
        """Handle date change in settings panel."""
        self.statusBar().showMessage(f"Date changed: {new_date.toString('yyyy-MM-dd')}")

        # Could trigger actions or updates here

    def on_time_changed(self, new_time):
        """Handle time change in settings panel."""
        self.statusBar().showMessage(f"Time changed: {new_time.toString('HH:mm')}")

        # Could trigger actions or updates here


def main():
    """Run the demo application."""
    # Create QApplication
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show window
    window = TestWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
