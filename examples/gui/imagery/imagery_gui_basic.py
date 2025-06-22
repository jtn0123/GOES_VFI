#!/usr/bin/env python3
"""
Test script for GOES imagery tab GUI

This script mocks external dependencies to demonstrate the GUI functionality
without requiring active internet connections or satellite data access.
"""

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create mock image for testing - improved version
def create_mock_image(width=600, height=500, channel=13, enhanced=False):
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

    # Create a gradient background
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Create gradient
    for y in range(height):
        color_value = int(180 * (y / height))

        if channel <= 6:  # Visible bands - blue/white gradient
            draw.line(
                [(0, y), (width, y)],
                fill=(
                    150 + color_value // 2,
                    150 + color_value // 2,
                    220 - color_value,
                ),
            )
        elif channel <= 10:  # Water vapor - blue gradient
            draw.line([(0, y), (width, y)], fill=(20, 20, 120 + color_value))
        else:  # IR bands - grayscale
            if enhanced:
                # Enhanced IR uses color to show temperature (orange/red for cold, blue for warm)
                if y < height / 3:
                    # Cold cloud tops (orange/red)
                    draw.line(
                        [(0, y), (width, y)], fill=(220, 100 - color_value // 2, 0)
                    )
                else:
                    # Warm areas (blue/green)
                    draw.line(
                        [(0, y), (width, y)],
                        fill=(0, 100 + color_value // 2, 100 + color_value),
                    )
            else:
                # Standard IR is grayscale
                c = 40 + color_value
                draw.line([(0, y), (width, y)], fill=(c, c, c))

    # Add "Earth" circle and features
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 3

    # Earth outline
    draw.ellipse(
        [
            (center_x - radius, center_y - radius),
            (center_x + radius, center_y + radius),
        ],
        outline=(255, 255, 255),
        width=3,
    )

    # Add some "weather features" (randomly positioned based on channel)
    np.random.seed(channel)  # Make it reproducible but different per channel
    for i in range(15):
        # Random position within Earth circle
        angle = np.random.random() * 2 * np.pi
        distance = np.random.random() * radius * 0.8
        x = int(center_x + np.cos(angle) * distance)
        y = int(center_y + np.sin(angle) * distance)

        # Size of feature
        size = np.random.randint(10, radius // 4)

        # Different appearance based on channel
        if channel <= 6:  # Visible - white clouds
            feature_color = (255, 255, 255, 150)
        elif channel <= 10:  # Water vapor - blue clouds
            if enhanced:
                # Enhanced water vapor shows moisture levels in color
                feature_color = (100, 100, 200 + np.random.randint(0, 55), 180)
            else:
                feature_color = (200, 200, 255, 150)
        else:  # IR - temperature based
            if enhanced:
                # Temperature-based coloring for IR
                temp = np.random.random()
                if temp < 0.3:  # Cold
                    feature_color = (255, 50, 0, 200)
                elif temp < 0.6:  # Medium
                    feature_color = (255, 180, 0, 200)
                else:  # Warm
                    feature_color = (0, 180, 255, 200)
            else:
                # Grayscale for standard IR
                gray = 200 + np.random.randint(0, 55)
                feature_color = (gray, gray, gray, 150)

        # Draw the feature
        draw.ellipse([(x - size, y - size), (x + size, y + size)], fill=feature_color)

    # Add channel information and timestamp
    try:
        font = ImageFont.truetype("Arial", 24)
        small_font = ImageFont.truetype("Arial", 16)
    except IOError:
        # Fallback to default
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Create title text
    if channel <= 16:
        title = f"GOES-16 Band {channel}"
        if channel <= 6:
            title += " (Visible)"
        elif channel <= 10:
            title += " (Water Vapor)"
        else:
            title += " (Infrared)"

        if enhanced and channel > 6:
            title += " - Enhanced"
    elif channel == 100:
        title = "True Color RGB Composite"
    elif channel == 103:
        title = "Airmass RGB"
    else:
        title = f"Channel {channel}"

    # Add title bar
    draw.rectangle([(0, 0), (width, 40)], fill=(0, 0, 60))
    draw.text((20, 10), title, fill=(255, 255, 255), font=font)

    # Add timestamp
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle([(0, height - 30), (width, height)], fill=(0, 0, 60))
    draw.text((10, height - 25), current_time, fill=(255, 255, 255), font=small_font)

    return img


# Create mock fallback preview image with error information
def create_fallback_preview(
    channel=13, error_msg="No data found for the selected date/time"
):
    """Create a fallback preview with error information."""
    width, height = 600, 350  # Reduce height to fit in window better

    # Create PIL image
    img = Image.new("RGB", (width, height), color=(40, 40, 40))
    draw = ImageDraw.Draw(img)

    # Draw title bar
    draw.rectangle([(0, 0), (width, 30)], fill=(25, 52, 152))  # Dark blue

    # Create fonts - smaller for more compact layout
    try:
        title_font = ImageFont.truetype("Arial", 18)
        header_font = ImageFont.truetype("Arial", 14)
        body_font = ImageFont.truetype("Arial", 12)
    except IOError:
        # Fallback to default
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

    # Help text (more compact)
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


# Mock imagery test helpers
class MockImagerySamples:
    """Helper to create and manage mock imagery samples"""

    @staticmethod
    def get_mock_sample(channel=13, enhanced=False):
        """Get a mock sample image"""
        return create_mock_image(channel=channel, enhanced=enhanced)

    @staticmethod
    def get_mock_comparison(channel=13):
        """Get a mock comparison image with multiple samples"""
        width, height = 800, 600

        # Create a composite image with three panels
        img = Image.new("RGB", (width, height), color=(40, 40, 40))

        # Create three sample variations
        standard = create_mock_image(
            width=380, height=280, channel=channel, enhanced=False
        )
        enhanced = create_mock_image(
            width=380, height=280, channel=channel, enhanced=True
        )
        web = create_mock_image(width=380, height=280, channel=channel, enhanced=True)

        # Paste them into the composite
        img.paste(standard, (10, 10))
        img.paste(enhanced, (410, 10))
        img.paste(web, (210, 310))

        # Add labels
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial", 18)
        except IOError:
            font = ImageFont.load_default()

        draw.text((20, 20), "Standard", fill=(255, 255, 255), font=font)
        draw.text((420, 20), "Enhanced", fill=(255, 255, 255), font=font)
        draw.text((220, 320), "NOAA CDN", fill=(255, 255, 255), font=font)

        return img

    @staticmethod
    def get_mock_fallback(channel=13, error="No data available"):
        """Get a mock fallback preview with error information"""
        return create_fallback_preview(channel=channel, error_msg=error)


# Mock the necessary modules and methods
def apply_mocks():
    """Apply necessary mocks for the GUI test."""
    # Create and patch SampleProcessor methods
    mock_sample_processor = MagicMock()

    # Mock create_sample_comparison to return our enhanced mock imagery
    def mock_create_comparison(*args, **kwargs):
        channel = args[0] if args else 13
        return MockImagerySamples.get_mock_comparison(channel=channel)

    mock_sample_processor.create_sample_comparison.side_effect = mock_create_comparison

    # Mock get_estimated_processing_time
    mock_sample_processor.get_estimated_processing_time.return_value = 5.0

    # Mock download_sample_data
    mock_sample_processor.download_sample_data.return_value = Path(
        "/tmp/mock_sample.nc"
    )

    # Mock download_web_sample to return appropriate mock imagery
    def mock_download_web_sample(*args, **kwargs):
        channel = args[0] if args else 13
        return MockImagerySamples.get_mock_sample(channel=channel, enhanced=True)

    mock_sample_processor.download_web_sample.side_effect = mock_download_web_sample

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


def main():
    """Run the GUI test."""
    print("Starting GOES Imagery Tab GUI test with mocked data sources...")

    # Apply mocks
    patches = apply_mocks()
    for p in patches:
        p.start()

    try:
        # Import the module
        from goesvfi.integrity_check.enhanced_imagery_tab import EnhancedGOESImageryTab

        # Create a QApplication
        app = QApplication(sys.argv)

        # Create main window
        window = QMainWindow()
        window.setWindowTitle("GOES Imagery Tab (Mocked Data)")
        window.setGeometry(100, 100, 1200, 900)  # Make window taller

        # Create central widget
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(5)  # Reduce spacing between elements
        main_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins

        # Add header with instructions
        header = QLabel("GOES Imagery Test - With Enhanced Error Handling")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #003366; color: white; padding: 5px;")
        main_layout.addWidget(header)

        # Add compact description (optional - can be removed if space is tight)
        description = QLabel(
            "Try 'Preview' to see imagery comparisons with improved error handling"
        )
        description.setStyleSheet("background-color: #f0f0f0; padding: 3px;")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(description)

        # Create the tab
        tab = EnhancedGOESImageryTab()
        main_layout.addWidget(tab, stretch=1)

        # Add a demonstration of the fallback preview directly
        fallback_group = QGroupBox("Error Handling Preview Demo")
        fallback_layout = QVBoxLayout(fallback_group)
        fallback_layout.setSpacing(3)  # Reduce spacing
        fallback_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins

        # Add buttons to show different error types - compact horizontal layout
        button_layout = QHBoxLayout()

        # Create buttons for different error scenarios
        timeout_btn = QPushButton("Connection Timeout")
        timeout_btn.clicked.connect(
            lambda: show_fallback_preview(
                "Connection timeout after 30 seconds when connecting to NOAA server"
            )
        )

        nodata_btn = QPushButton("No Data Found")
        nodata_btn.clicked.connect(
            lambda: show_fallback_preview("No data found for the selected date/time")
        )

        corrupt_btn = QPushButton("Invalid Data")
        corrupt_btn.clicked.connect(
            lambda: show_fallback_preview("Downloaded file is not a valid image format")
        )

        # Add buttons to layout
        button_layout.addWidget(timeout_btn)
        button_layout.addWidget(nodata_btn)
        button_layout.addWidget(corrupt_btn)
        fallback_layout.addLayout(button_layout)

        # Preview area - smaller size to fit in window
        fallback_preview = QLabel()
        fallback_preview.setFixedSize(600, 350)  # Fixed size that's more compact
        fallback_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fallback_preview.setScaledContents(True)  # Scale contents to fit
        fallback_preview.setText("Loading preview...")
        fallback_layout.addWidget(fallback_preview)

        # Add to main layout with fixed height
        main_layout.addWidget(fallback_group)
        fallback_group.setMaximumHeight(450)  # Limit maximum height

        # Function to show fallback preview
        def show_fallback_preview(error_msg):
            # Create fallback preview image - smaller size for better fit
            img = create_fallback_preview(channel=13, error_msg=error_msg)
            img = img.resize((600, 350), Image.LANCZOS)  # Resize to fit area

            # Convert to QPixmap
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)

            # Display in preview area
            fallback_preview.setPixmap(pixmap)
            logger.info("Showing fallback preview for: %s", error_msg)

        # Show initial fallback preview immediately
        QTimer.singleShot(
            100,
            lambda: show_fallback_preview("No data found for the selected date/time"),
        )

        # Set central widget
        window.setCentralWidget(central)

        # Show the window
        window.show()

        # Run the application
        sys.exit(app.exec())

    finally:
        # Stop all patches
        for p in patches:
            p.stop()


if __name__ == "__main__":
    main()
