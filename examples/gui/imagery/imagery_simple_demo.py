#!/usr/bin/env python3
"""
Simplified test script for GOES imagery tab GUI

This script demonstrates the enhanced preview dialog with mocked data.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Create mock satellite image (simpler version)
def create_mock_satellite_image(width=600, height=400, channel=13, text=None):
    """Create a simple mock satellite image."""
    # Choose colors based on channel type
    if channel <= 6:  # Visible bands
        bg_color = (200, 200, 200)
        fg_color = (50, 50, 50)
    elif channel <= 10:  # Water vapor bands
        bg_color = (50, 50, 150)
        fg_color = (200, 200, 255)
    else:  # IR bands
        bg_color = (30, 30, 30)
        fg_color = (200, 200, 200)

    # Create image
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw a central circle representing Earth
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 3
    draw.ellipse(
        [
            (center_x - radius, center_y - radius),
            (center_x + radius, center_y + radius),
        ],
        outline=fg_color,
        width=3,
    )

    # Draw a few "clouds"
    for i in range(10):
        x = center_x + int(radius * 0.7 * np.cos(i * np.pi / 5))
        y = center_y + int(radius * 0.7 * np.sin(i * np.pi / 5))
        cloud_size = radius // 4
        draw.ellipse(
            [(x - cloud_size, y - cloud_size), (x + cloud_size, y + cloud_size)],
            fill=(255, 255, 255, 128),
            outline=None,
        )

    # Add text
    if text is None:
        if channel <= 16:
            text = f"GOES-16 Band {channel}"
        elif channel == 100:
            text = "True Color RGB"
        elif channel == 103:
            text = "Airmass RGB"
        else:
            text = f"Channel {channel}"

    # Try to use a font, fallback to default if necessary
    try:
        font = ImageFont.truetype("Arial", 24)
    except IOError:
        font = ImageFont.load_default()

    # Add text at top
    draw.rectangle([(0, 0), (width, 40)], fill=(0, 0, 0))
    text_width = draw.textlength(text, font=font)
    draw.text(((width - text_width) // 2, 5), text, fill=(255, 255, 255), font=font)

    # Add timestamp at bottom
    timestamp = "2025-05-08 17:45:00 UTC"
    draw.rectangle([(0, height - 30), (width, height)], fill=(0, 0, 0))
    draw.text(
        (10, height - 25),
        timestamp,
        fill=(255, 255, 255),
        font=ImageFont.load_default(),
    )

    return img


# Mock dialog that demonstrates the enhanced error handling UI
class MockPreviewDialog(QDialog):
    """Dialog showing the enhanced preview fallback UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        """Initialize the UI components."""
        self.setWindowTitle("Enhanced Preview Dialog Demo")
        self.resize(800, 600)

        # Main layout
        layout = QVBoxLayout(self)

        # Header label
        header = QLabel("Enhanced Preview Dialog with Error Handling")
        header.setStyleSheet(
            "background-color: #3F51B5; color: white; padding: 10px; font-weight: bold; font-size: 16px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Instructions
        instructions = QLabel(
            "This demonstrates the enhanced fallback preview with better error handling.\n"
            "The buttons below show how the UI handles different error scenarios."
        )
        instructions.setStyleSheet("padding: 10px;")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)

        # Preview image area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setStyleSheet("background-color: #202020;")
        self.image_label.setText("Preview area")
        layout.addWidget(self.image_label)

        # Buttons for different error scenarios
        button_layout = QHBoxLayout()

        self.timeout_btn = QPushButton("Show Timeout Error")
        self.timeout_btn.clicked.connect(lambda: self.showFallbackPreview("Connection timed out after 30 seconds"))

        self.not_found_btn = QPushButton("Show Not Found Error")
        self.not_found_btn.clicked.connect(lambda: self.showFallbackPreview("No data found for the selected date/time"))

        self.corrupted_btn = QPushButton("Show Corrupted Data Error")
        self.corrupted_btn.clicked.connect(lambda: self.showFallbackPreview("Downloaded file is not a valid image"))

        self.success_btn = QPushButton("Show Success")
        self.success_btn.clicked.connect(self.showSuccessPreview)

        button_layout.addWidget(self.timeout_btn)
        button_layout.addWidget(self.not_found_btn)
        button_layout.addWidget(self.corrupted_btn)
        button_layout.addWidget(self.success_btn)

        layout.addLayout(button_layout)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        # Show a default error preview
        QTimer.singleShot(
            500,
            lambda: self.showFallbackPreview("No imagery available for the selected date/time"),
        )

    def showFallbackPreview(self, error_msg):
        """Create and show a fallback preview with error info."""
        # Create a larger image with text and visual indicators
        width, height = 600, 500
        pix = QPixmap(width, height)
        pix.fill(Qt.GlobalColor.darkGray)

        # Get painter
        painter = pix.toImage().bits()  # Wrong way, need to use QPainter

        # The pixmap itself doesn't support direct drawing, we need to use QPainter
        from PyQt6.QtGui import QFont, QPainter, QRect

        painter = QPainter(pix)

        # Create a better title bar
        painter.fillRect(0, 0, width, 40, Qt.GlobalColor.darkBlue)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        # Draw title
        channel_name = "Clean IR (Band 13)"
        product_name = "FULL_DISK"
        channel_num = 13

        title_text = f"Preview: {channel_name} ({product_name})"
        painter.drawText(20, 27, title_text)

        # Draw info icon in top right
        info_icon_rect = QRect(width - 35, 5, 30, 30)
        painter.drawText(info_icon_rect, Qt.AlignmentFlag.AlignCenter, "ℹ")

        # Draw main content
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 12))

        # Display appropriate error message
        status_text = "STATUS: PREVIEW UNAVAILABLE"

        # Create message based on error
        if "timeout" in error_msg.lower():
            primary_reason = "Server connection timeout"
            suggestion = "Check your internet connection and try again later"
        elif "no data found" in error_msg.lower():
            primary_reason = "No imagery data available for the selected date/time"
            suggestion = "Try a different date/time or channel"
        elif "not a valid image" in error_msg.lower():
            primary_reason = "The retrieved imagery is corrupted or invalid"
            suggestion = "Try a different channel or product type"
        else:
            primary_reason = "Error retrieving imagery"
            suggestion = "See details below"

        # Format the message lines
        message_lines = [
            f"Issue: {primary_reason}",
            f"Channel: {channel_name} (Channel {channel_num})",
            f"Product: {product_name}",
            "",
            f"Suggestion: {suggestion}",
            "",
            "Technical details:",
            error_msg,
            "",
            "You can still proceed with processing.",
            "The system will use fallback imagery samples.",
        ]

        # Draw status banner
        status_rect = QRect(0, 50, width, 30)
        painter.fillRect(status_rect, Qt.GlobalColor.darkRed)
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status_text)

        # Draw each line of text
        painter.setFont(QFont("Arial", 11))
        y = 100
        for line in message_lines:
            painter.drawText(30, y, line)
            y += 25

        # Draw helpful action buttons visually (decorative)
        action_rect = QRect(30, height - 80, width - 60, 50)
        painter.fillRect(action_rect, Qt.GlobalColor.darkCyan)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(
            action_rect,
            Qt.AlignmentFlag.AlignCenter,
            "Click 'Process Full Image' to continue with fallback data",
        )

        painter.end()

        # Set the image
        self.image_label.setPixmap(pix)

    def showSuccessPreview(self):
        """Show a successful preview image."""
        # Create a mock satellite image
        img = create_mock_satellite_image(600, 400, 13)

        # Convert to QPixmap
        qimg = QImage(
            img.tobytes("raw", "RGB"),
            img.width,
            img.height,
            img.width * 3,
            QImage.Format.Format_RGB888,
        )
        pixmap = QPixmap.fromImage(qimg)

        # Set the image
        self.image_label.setPixmap(pixmap)


def main():
    """Run the mock preview dialog test."""
    print("Starting GOES Enhanced Preview Dialog Test")

    # Create QApplication
    app = QApplication(sys.argv)

    # Create and show dialog
    dialog = MockPreviewDialog()
    dialog.show()

    # Run app
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
