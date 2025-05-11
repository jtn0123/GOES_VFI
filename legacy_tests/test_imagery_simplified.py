#!/usr/bin/env python3
"""
Simplified test script for GOES imagery tab GUI

This script demonstrates the enhanced GOES imagery functionality without zoom features.
"""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create mock satellite image
def create_mock_image(width=1024, height=1024, channel=13, enhanced=False, text=None):
    """Create a mock satellite image for testing."""
    # Choose colors based on channel type
    if channel <= 6:
        # Visible bands
        bg_color = (200, 200, 240)
        grid_color = (100, 100, 130)
        text_color = (0, 0, 0)
    elif channel <= 10:
        # Water vapor bands
        bg_color = (10, 10, 100)
        grid_color = (70, 70, 160)
        text_color = (255, 255, 255)
    else:
        # IR bands
        bg_color = (20, 20, 20)
        grid_color = (80, 80, 80)
        text_color = (240, 240, 240)

    # Create base image
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw grid lines (longitude/latitude)
    grid_spacing = 64
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Draw Earth outline
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 2.5
    draw.ellipse(
        [
            (center_x - radius, center_y - radius),
            (center_x + radius, center_y + radius),
        ],
        outline=(255, 255, 255),
        width=3,
    )

    # Draw some "clouds" or features
    np.random.seed(channel)  # Make it reproducible but different per channel
    for i in range(20):
        # Calculate position (more likely to be on the "earth" circle)
        angle = np.random.random() * 2 * np.pi
        distance = np.random.random() * radius * 0.9
        x = int(center_x + np.cos(angle) * distance)
        y = int(center_y + np.sin(angle) * distance)

        # Size of feature
        size = np.random.randint(20, radius // 3)

        # Color based on channel and whether enhanced
        if enhanced and channel > 6:
            if channel <= 10:  # Water vapor with enhanced coloring
                r = int(100 + np.random.random() * 100)
                g = int(100 + np.random.random() * 100)
                b = int(200 + np.random.random() * 55)
                color = (r, g, b, 200)
            else:  # IR with enhanced coloring
                # Cold cloud tops are usually colored red/yellow in enhanced IR
                temp = np.random.random()  # Simulated temperature
                if temp < 0.3:  # Very cold (high clouds)
                    r = 255
                    g = int(temp * 200)
                    b = 0
                elif temp < 0.6:  # Medium cold
                    r = 255
                    g = 255
                    b = 0
                else:  # Warmer
                    r = int((1 - temp) * 255)
                    g = int((1 - temp) * 200)
                    b = int((1 - temp) * 100)
                color = (r, g, b, 200)
        else:
            # Standard grayscale intensity for non-enhanced
            intensity = int(180 + np.random.random() * 75)
            color = (intensity, intensity, intensity, 200)

        # Draw the feature (cloud/weather system)
        draw.ellipse(
            [(x - size, y - size), (x + size, y + size)], fill=color, outline=None
        )

    # Add labels and information
    # Add channel information at the top
    if text is None:
        if channel <= 16:
            text = f"GOES-16 Band {channel}"
            if enhanced and channel > 6:
                text += " (Enhanced)"
            if channel <= 6:
                text += " - Visible"
            elif channel <= 10:
                text += " - Water Vapor"
            else:
                text += " - Infrared"
        elif channel == 100:
            text = "True Color RGB Composite"
        elif channel == 103:
            text = "Airmass RGB Composite"
        else:
            text = f"Channel {channel}"

    # Draw title bar
    draw.rectangle([(0, 0), (width, 50)], fill=(0, 0, 0, 180))

    # Use a larger font for the title
    try:
        font = ImageFont.truetype("Arial", 36)
        small_font = ImageFont.truetype("Arial", 24)
    except:
        # Fall back to default if Arial not available
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Center the title text
    text_width = draw.textlength(text, font=font)
    draw.text(((width - text_width) // 2, 10), text, fill=text_color, font=font)

    # Add timestamp at bottom
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle([(0, height - 40), (width, height)], fill=(0, 0, 0, 180))
    draw.text(
        (20, height - 35),
        f"Timestamp: {timestamp}",
        fill=(255, 255, 255),
        font=small_font,
    )

    return img


class EnhancedImageViewer(QWidget):
    """Simple image viewer widget for demo without zoom control."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Create image display area with scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(800, 600)

        # Create image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.image_label.setMinimumSize(600, 400)

        # Set label as the scroll area widget
        self.scroll_area.setWidget(self.image_label)

        # Add scroll area to main layout
        main_layout.addWidget(self.scroll_area)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Channel selection
        channel_group = QGroupBox("Channel")
        channel_layout = QHBoxLayout(channel_group)

        # Channel combo box
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("Band 13 - Clean IR", 13)
        self.channel_combo.addItem("Band 8 - Water Vapor", 8)
        self.channel_combo.addItem("Band 2 - Visible", 2)
        self.channel_combo.addItem("True Color RGB", 100)
        self.channel_combo.addItem("Airmass RGB", 103)
        self.channel_combo.currentIndexChanged.connect(self.changeChannel)

        # Add to layout
        channel_layout.addWidget(self.channel_combo)
        controls_layout.addWidget(channel_group)

        # Enhancement option
        enhancement_group = QGroupBox("Enhancement")
        enhancement_layout = QHBoxLayout(enhancement_group)

        # Enhancement combo
        self.enhance_combo = QComboBox()
        self.enhance_combo.addItem("Standard", False)
        self.enhance_combo.addItem("Enhanced", True)
        self.enhance_combo.currentIndexChanged.connect(self.toggleEnhancement)

        # Add to layout
        enhancement_layout.addWidget(self.enhance_combo)
        controls_layout.addWidget(enhancement_group)

        # Add controls to main layout
        main_layout.addLayout(controls_layout)

        # Initialize properties
        self.current_channel = 13
        self.enhanced = False

        # Load initial image
        self.loadImage()

    def loadImage(self):
        """Load and display a mock satellite image."""
        # Create the mock image
        img = create_mock_image(
            width=1024,
            height=1024,
            channel=self.current_channel,
            enhanced=self.enhanced,
        )

        # Convert to QPixmap
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qimage = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimage)

        # Display the image
        self.image_label.setPixmap(pixmap)

        # Log the change
        logger.info(
            f"Loaded image for channel {self.current_channel} (enhanced: {self.enhanced})"
        )

    @pyqtSlot(int)
    def changeChannel(self, index):
        """Change the displayed channel."""
        self.current_channel = self.channel_combo.itemData(index)
        self.loadImage()

    @pyqtSlot(int)
    def toggleEnhancement(self, index):
        """Toggle image enhancement."""
        self.enhanced = self.enhance_combo.itemData(index)
        self.loadImage()


class EnhancedPreviewDialog(QWidget):
    """Demo of the enhanced preview dialog with better error handling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Enhanced Error Handling Preview")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #2c3e50; color: white; padding: 10px;")
        layout.addWidget(header)

        # Description
        desc = QLabel(
            "This demo shows the improved error handling UI that displays helpful information\n"
            "when satellite imagery cannot be loaded for various reasons."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # Preview image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        # Error selection
        group = QGroupBox("Error Scenario")
        group_layout = QHBoxLayout(group)

        # Combo box for selecting error type
        self.error_combo = QComboBox()
        self.error_combo.addItem("No imagery for date/time", "no_data")
        self.error_combo.addItem("Connection timeout", "timeout")
        self.error_combo.addItem("Invalid/corrupted image", "corrupt")
        self.error_combo.addItem("General error", "general")
        self.error_combo.currentIndexChanged.connect(self.showError)

        group_layout.addWidget(self.error_combo)
        layout.addWidget(group)

        # Initialize with first error type
        self.showError(0)

    def showError(self, index):
        """Show the selected error scenario."""
        error_type = self.error_combo.itemData(index)

        # Create a pixmap for the error preview
        width, height = 600, 500
        pix = QPixmap(width, height)
        pix.fill(QColor(40, 40, 40))  # Dark gray background

        # Create painter for drawing
        from PyQt6.QtGui import QPainter

        painter = QPainter(pix)

        # Draw title bar
        painter.fillRect(0, 0, width, 40, QColor(25, 52, 152))  # Dark blue
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(20, 28, "Preview: Clean IR (Band 13)")

        # Draw status bar
        painter.fillRect(0, 45, width, 30, QColor(180, 32, 32))  # Dark red
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(width // 2 - 100, 66, "STATUS: PREVIEW UNAVAILABLE")

        # Specific error message based on type
        if error_type == "no_data":
            error_msg = "No data found for selected date and time"
            primary_reason = "No imagery data available"
            suggestion = "Try a different date/time or channel"
        elif error_type == "timeout":
            error_msg = "Connection timed out while accessing NOAA server"
            primary_reason = "Server connection timeout"
            suggestion = "Check your internet connection and try again later"
        elif error_type == "corrupt":
            error_msg = "Downloaded file is not a valid image format"
            primary_reason = "Data corruption detected"
            suggestion = "Try a different channel or product type"
        else:
            error_msg = "Error processing satellite data"
            primary_reason = "Error retrieving imagery"
            suggestion = "See details below"

        # Draw main content
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 11))

        # Main heading
        y_pos = 100
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(30, y_pos, f"Issue: {primary_reason}")
        y_pos += 25

        # Context info
        painter.setFont(QFont("Arial", 11))
        painter.drawText(30, y_pos, "Channel: Clean IR (Band 13)")
        y_pos += 20
        painter.drawText(30, y_pos, "Product: FULL_DISK")
        y_pos += 20
        painter.drawText(30, y_pos, f"Date/Time: 2025-05-08 17:45 UTC")
        y_pos += 30

        # Suggestion
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(30, y_pos, "Recommendation:")
        y_pos += 20
        painter.setFont(QFont("Arial", 11))
        painter.drawText(50, y_pos, suggestion)
        y_pos += 30

        # Technical details
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(30, y_pos, "Technical details:")
        y_pos += 20
        painter.setFont(QFont("Arial", 11))
        painter.drawText(50, y_pos, error_msg)
        y_pos += 40

        # Additional help info
        painter.setPen(QColor(180, 230, 255))  # Light blue
        painter.drawText(
            30, y_pos, "You can still proceed with processing using fallback imagery."
        )
        y_pos += 20
        painter.drawText(30, y_pos, "The system will use existing visualized samples.")

        # Add action button visualization
        painter.fillRect(150, 320, 300, 40, QColor(0, 120, 120))  # Teal button
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(175, 345, "Click 'Process Full Image' to continue")

        painter.end()

        # Display the error preview
        self.image_label.setPixmap(pix)

        # Log the change
        logger.info(f"Showing error preview for: {error_msg}")


class MainWindow(QMainWindow):
    """Main application window with tabs for different demos."""

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("GOES Imagery Enhancements Demo")
        self.setGeometry(100, 100, 1000, 800)

        # Create central widget
        central = QWidget()
        layout = QVBoxLayout(central)

        # Create tab widget
        self.tabs = QTabWidget()

        # Add image viewer tab
        self.image_viewer = EnhancedImageViewer()
        self.tabs.addTab(self.image_viewer, "Satellite Imagery")

        # Add error preview tab
        self.error_preview = EnhancedPreviewDialog()
        self.tabs.addTab(self.error_preview, "Error Handling")

        # Add tabs to layout
        layout.addWidget(self.tabs)

        # Add close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Set central widget
        self.setCentralWidget(central)


def main():
    """Run the application."""
    # Create QApplication
    app = QApplication(sys.argv)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
