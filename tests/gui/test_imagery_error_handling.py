#!/usr/bin/env python3
"""
Test script specifically for GOES imagery error handling

This script focuses on demonstrating the enhanced error handling and fallback
mechanisms for the GOES imagery tab.
"""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the two implementations we want to compare
from goesvfi.integrity_check.enhanced_imagery_tab import EnhancedGOESImageryTab
from goesvfi.integrity_check.sample_processor import SampleProcessor


# Create mock image for testing - improved version
def create_mock_image(width=600, height=350, channel=13, enhanced=False):
    """Create a mock image for testing."""
    # Choose colors based on channel
    if channel <= 6:  # Visible bands
        bg_color = (150, 150, 220)
        text_color = (10, 10, 10)
    elif channel <= 10:  # Water vapor bands
        bg_color = (20, 20, 120)
        text_color = (240, 240, 240)
    else:  # IR bands
        bg_color = (40, 40, 40)
        text_color = (240, 240, 240)

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Add title and timestamp
    try:
        font = ImageFont.truetype("Arial", 20)
        small_font = ImageFont.truetype("Arial", 14)
    except IOError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Create title text
    title = f"GOES-16 Band {channel} Test Image"

    # Add title bar
    draw.rectangle([(0, 0), (width, 30)], fill=(0, 0, 60))
    draw.text((20, 5), title, fill=(255, 255, 255), font=font)

    # Add Earth circle
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 4
    draw.ellipse(
        [
            (center_x - radius, center_y - radius),
            (center_x + radius, center_y + radius),
        ],
        outline=(255, 255, 255),
        width=3,
    )

    # Add timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle([(0, height - 25), (width, height)], fill=(0, 0, 60))
    draw.text((10, height - 20), current_time, fill=(255, 255, 255), font=small_font)

    return img


# Create mock fallback preview image with error information
def create_fallback_preview(
    channel=13, error_msg="No data found for the selected date/time"
):
    """Create a fallback preview with error information."""
    width, height = 600, 350

    # Create PIL image
    img = Image.new("RGB", (width, height), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)

    # Draw title bar
    draw.rectangle([(0, 0), (width, 30)], fill=(25, 52, 152))  # Dark blue

    # Create fonts
    try:
        title_font = ImageFont.truetype("Arial", 18)
        header_font = ImageFont.truetype("Arial", 14)
        body_font = ImageFont.truetype("Arial", 12)
    except IOError:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    # Draw title
    channel_name = f"Band {channel}"
    if channel == 13:
        channel_name = "Clean IR (Band 13)"
    elif channel == 8:
        channel_name = "Water Vapor (Band 8)"
    elif channel == 100:
        channel_name = "True Color RGB"

    draw.text(
        (20, 7), f"Preview: {channel_name}", fill=(255, 255, 255), font=title_font
    )

    # Draw status bar
    draw.rectangle([(0, 35), (width, 55)], fill=(180, 32, 32))  # Dark red
    draw.text(
        (width // 2 - 95, 40),
        "STATUS: PREVIEW UNAVAILABLE",
        fill=(255, 255, 255),
        font=header_font,
    )

    # Determine error type and recommendations
    if "timeout" in error_msg.lower():
        primary_reason = "Server connection timeout"
        suggestion = "Check your internet connection and try again later"
    elif "no data" in error_msg.lower():
        primary_reason = "No imagery data available for the selected date/time"
        suggestion = "Try a different date/time or channel"
    elif "invalid" in error_msg.lower() or "corrupt" in error_msg.lower():
        primary_reason = "The retrieved imagery is corrupted or invalid"
        suggestion = "Try a different channel or product type"
    else:
        primary_reason = "Error retrieving imagery"
        suggestion = "See details below"

    # Draw content - more compact layout
    y_pos = 70
    draw.text(
        (20, y_pos), f"Issue: {primary_reason}", fill=(255, 255, 255), font=header_font
    )
    y_pos += 25

    draw.text(
        (20, y_pos),
        f"Channel: {channel_name} | Product: FULL_DISK",
        fill=(255, 255, 255),
        font=body_font,
    )
    y_pos += 20
    draw.text(
        (20, y_pos),
        f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC",
        fill=(255, 255, 255),
        font=body_font,
    )
    y_pos += 25

    draw.text((20, y_pos), "Recommendation:", fill=(255, 255, 255), font=header_font)
    y_pos += 20
    draw.text((35, y_pos), suggestion, fill=(255, 255, 255), font=body_font)
    y_pos += 25

    draw.text((20, y_pos), "Technical details:", fill=(255, 255, 255), font=header_font)
    y_pos += 20
    draw.text((35, y_pos), error_msg, fill=(200, 200, 200), font=body_font)
    y_pos += 25

    # Help text
    draw.text(
        (20, y_pos),
        "You can still proceed with processing. The system will use fallback imagery samples.",
        fill=(100, 200, 255),
        font=body_font,
    )

    # Draw action button at bottom
    button_y = height - 35
    draw.rectangle(
        [(width // 2 - 130, button_y), (width // 2 + 130, button_y + 25)],
        fill=(0, 120, 120),
        outline=(255, 255, 255),
    )
    draw.text(
        (width // 2 - 120, button_y + 5),
        "Click 'Process Full Image' to continue",
        fill=(255, 255, 255),
        font=body_font,
    )

    return img


# Mock imagery for testing
class MockImagerySamples:
    @staticmethod
    def get_mock_fallback(channel=13, error="No data available"):
        """Get a mock fallback preview with error information"""
        return create_fallback_preview(channel=channel, error_msg=error)


# Mock the necessary components
def apply_mocks():
    """Apply mocks for testing error handling"""
    # Create and patch SampleProcessor methods
    mock_sample_processor = MagicMock()

    # Mock download methods to cause errors
    mock_sample_processor.download_sample_data.side_effect = Exception(
        "No data found for current date"
    )
    mock_sample_processor.download_web_sample.side_effect = Exception(
        "Connection timeout accessing NOAA server"
    )

    # Patch SampleProcessor class to return our mock
    mock_sample_processor_class = MagicMock(return_value=mock_sample_processor)

    # Apply all patches
    patches = [
        patch(
            "goesvfi.integrity_check.sample_processor.SampleProcessor",
            mock_sample_processor_class,
        ),
        patch(
            "goesvfi.integrity_check.enhanced_imagery_tab.SampleProcessor",
            mock_sample_processor_class,
        ),
    ]

    return patches


class ErrorDisplayTab(QWidget):
    """Tab specifically for demonstrating error handling"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header = QLabel("Enhanced GOES Error Handling Demo")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #003366; color: white; padding: 5px;")
        layout.addWidget(header)

        # Error type selection
        error_group = QGroupBox("Select Error Type")
        error_layout = QVBoxLayout(error_group)

        # Create radio buttons for different errors
        self.error_group = QButtonGroup(self)

        self.radio_timeout = QRadioButton("Connection Timeout")
        self.radio_timeout.setChecked(True)
        self.error_group.addButton(self.radio_timeout)
        error_layout.addWidget(self.radio_timeout)

        self.radio_no_data = QRadioButton("No Data Available")
        self.error_group.addButton(self.radio_no_data)
        error_layout.addWidget(self.radio_no_data)

        self.radio_corrupt = QRadioButton("Invalid Image Data")
        self.error_group.addButton(self.radio_corrupt)
        error_layout.addWidget(self.radio_corrupt)

        layout.addWidget(error_group)

        # Display area
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(600, 350)
        self.preview_label.setMaximumSize(600, 350)
        self.preview_label.setStyleSheet("background-color: #202020;")
        layout.addWidget(self.preview_label)

        # Action buttons
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Show Error Preview")
        self.refresh_btn.clicked.connect(self.refresh_preview)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # Show initial preview
        QTimer.singleShot(100, self.refresh_preview)

    def refresh_preview(self):
        """Show a preview based on the selected error type"""
        if self.radio_timeout.isChecked():
            error_msg = (
                "Connection timeout after 30 seconds when connecting to NOAA server"
            )
        elif self.radio_no_data.isChecked():
            error_msg = "No data found for the selected date/time"
        elif self.radio_corrupt.isChecked():
            error_msg = "Downloaded file is not a valid image format"
        else:
            error_msg = "Unknown error occurred"

        # Create fallback preview image
        img = create_fallback_preview(channel=13, error_msg=error_msg)

        # Convert to QPixmap
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qimg = QImage.fromData(buf.getvalue())
        pixmap = QPixmap.fromImage(qimg)

        # Display in preview area
        self.preview_label.setPixmap(pixmap)


class TestWindow(QMainWindow):
    """Test window for GOES imagery error handling"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GOES Imagery Error Handling Test")
        self.setGeometry(100, 100, 1200, 900)

        # Create central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Create layout with minimal margins
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Create tab widget
        tab_widget = QTabWidget()

        # Create our direct error handling demo tab
        self.error_tab = ErrorDisplayTab()
        tab_widget.addTab(self.error_tab, "Error Handling Demo")

        # Create the full enhanced imagery tab
        self.imagery_tab = EnhancedGOESImageryTab()
        tab_widget.addTab(self.imagery_tab, "Full Imagery Tab")

        # Add tab widget to layout
        layout.addWidget(tab_widget)

        # Make sure directories exist for testing
        self.ensure_test_directories()

    def ensure_test_directories(self):
        """Ensure necessary directories exist for testing."""
        # Base directories
        dirs = [
            Path.home() / "Downloads" / "goes_imagery",
            Path.home() / "Downloads" / "goes_channels" / "visualized",
            Path.home() / "Downloads" / "goes_channels" / "rgb_composites",
            Path.home()
            / "Downloads"
            / "goes_channels"
            / "visualized"
            / "derived_products",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


def main():
    """Main function to run the test application."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Apply mocks to cause errors for testing
    patches = apply_mocks()
    for p in patches:
        p.start()

    try:
        # Create and show the window
        window = TestWindow()
        window.show()

        # Run the application
        sys.exit(app.exec())
    finally:
        # Stop patches
        for p in patches:
            p.stop()


if __name__ == "__main__":
    main()
