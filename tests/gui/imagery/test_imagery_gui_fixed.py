#!/usr/bin/env python3
"""
Test script for GOES imagery tab GUI with working controls

This script mocks external dependencies to demonstrate the enhanced GUI functionality
with properly working zoom controls and preview features.
"""

import io
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create temp directory for mock imagery
TEMP_DIR = Path(tempfile.mkdtemp(prefix="mock_goes_"))


# Create mock image for testing
def create_mock_image(
    width=600, height=500, channel=13, product="FULL_DISK", is_enhanced=False
):
    """Create a mock image for testing."""
    # Choose color scheme based on channel
    if channel <= 6:  # Visible
        bg_color = (200, 200, 200)
        text_color = (0, 0, 0)
        gradient_colors = [(255, 255, 255), (120, 120, 120)]
    elif channel <= 10:  # Water vapor
        bg_color = (0, 0, 100)
        text_color = (255, 255, 255)
        gradient_colors = [(50, 50, 150), (0, 0, 50)]
    else:  # IR
        bg_color = (30, 30, 30)
        text_color = (255, 255, 255)
        gradient_colors = [(100, 100, 100), (10, 10, 10)]

    # Create the image
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Create a gradient background based on channel type
    for y in range(height):
        # Linear interpolation between the two gradient colors
        ratio = y / height
        r = int(gradient_colors[0][0] * (1 - ratio) + gradient_colors[1][0] * ratio)
        g = int(gradient_colors[0][1] * (1 - ratio) + gradient_colors[1][1] * ratio)
        b = int(gradient_colors[0][2] * (1 - ratio) + gradient_colors[1][2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw simulated Earth/cloud features
    # Draw a circle to simulate Earth
    earth_center = (width // 2, height // 2)
    earth_radius = min(width, height) // 3
    draw.ellipse(
        [
            (earth_center[0] - earth_radius, earth_center[1] - earth_radius),
            (earth_center[0] + earth_radius, earth_center[1] + earth_radius),
        ],
        outline=(255, 255, 255),
        width=2,
    )

    # Add some "clouds" (random white patches)
    np.random.seed(channel)  # Make it reproducible but different per channel
    for _ in range(20):
        x = np.random.randint(width // 4, width * 3 // 4)
        y = np.random.randint(height // 4, height * 3 // 4)
        size = np.random.randint(10, 50)
        cloud_color = (255, 255, 255, 128)  # Semi-transparent white

        # Draw a random cloud shape
        for i in range(5):  # Draw multiple overlapping circles for cloud shape
            cx = x + np.random.randint(-size // 4, size // 4)
            cy = y + np.random.randint(-size // 4, size // 4)
            cs = size // 2 + np.random.randint(-size // 4, size // 4)
            draw.ellipse(
                [(cx - cs, cy - cs), (cx + cs, cy + cs)], fill=cloud_color, outline=None
            )

    # Add text
    try:
        title_font = ImageFont.truetype("Arial", 24)
        detail_font = ImageFont.truetype("Arial", 16)
    except IOError:
        # Fallback to default
        title_font = ImageFont.load_default()
        detail_font = ImageFont.load_default()

    if channel <= 16:
        title = f"GOES-16 Band {channel}"
        if is_enhanced and channel > 6:
            title += " (Enhanced)"
    elif channel == 100:
        title = "True Color RGB"
    elif channel == 103:
        title = "Airmass RGB"
    elif channel == 104:
        title = "Fire Temperature RGB"
    else:
        title = f"Channel {channel}"

    # Draw title at top
    draw.rectangle([(0, 0), (width, 40)], fill=(0, 0, 0, 180))
    draw.text((10, 10), title, fill=text_color, font=title_font)

    # Draw timestamp at bottom
    timestamp = "2025-05-08 17:45:00 UTC"
    draw.rectangle([(0, height - 30), (width, height)], fill=(0, 0, 0, 180))
    draw.text(
        (10, height - 25), f"{product} • {timestamp}", fill=text_color, font=detail_font
    )

    # Add some color enhancements if this is an enhanced version
    if is_enhanced and channel > 6:
        # Create color overlay for IR/WV bands
        if 7 <= channel <= 10:  # Water vapor
            overlay = np.zeros((height, width, 3), dtype=np.uint8)
            for y in range(height):
                for x in range(width):
                    dist = np.sqrt(
                        ((x - earth_center[0]) / earth_radius) ** 2
                        + ((y - earth_center[1]) / earth_radius) ** 2
                    )
                    if dist < 1.2:  # Inside and near Earth
                        # Blue-based gradient for water vapor
                        overlay[y, x, 0] = int(100 * (1 - dist))  # R
                        overlay[y, x, 1] = int(100 * (1 - dist))  # G
                        overlay[y, x, 2] = int(240 * (1 - dist))  # B

            # Convert overlay to PIL Image and blend with original
            overlay_img = Image.fromarray(overlay)
            img = Image.blend(img, overlay_img, alpha=0.7)

        elif 11 <= channel <= 16:  # IR bands
            overlay = np.zeros((height, width, 3), dtype=np.uint8)
            for y in range(height):
                for x in range(width):
                    dist = np.sqrt(
                        ((x - earth_center[0]) / earth_radius) ** 2
                        + ((y - earth_center[1]) / earth_radius) ** 2
                    )
                    if dist < 1.2:  # Inside and near Earth
                        if dist < 0.7:  # Cold cloud tops (center)
                            # Reddish for cold cloud tops
                            overlay[y, x, 0] = 240  # R
                            overlay[y, x, 1] = int(100 * dist)  # G
                            overlay[y, x, 2] = int(80 * dist)  # B
                        else:  # Warmer areas (edges)
                            # Transition to yellow/green for warmer areas
                            overlay[y, x, 0] = int(240 * (1.2 - dist))  # R
                            overlay[y, x, 1] = int(220 * (1.2 - dist))  # G
                            overlay[y, x, 2] = 0  # B

            # Convert overlay to PIL Image and blend with original
            overlay_img = Image.fromarray(overlay)
            img = Image.blend(img, overlay_img, alpha=0.6)

    return img


# Save sample imagery to temp dir
def create_sample_images():
    """Create sample imagery files for testing."""
    # Create samples for a few bands
    for channel in [2, 7, 8, 13, 100]:
        # Standard version
        img = create_mock_image(channel=channel, is_enhanced=False)
        path = TEMP_DIR / f"band_{channel:02d}_standard.png"
        img.save(path)

        # Enhanced version for appropriate bands
        if channel >= 7:
            img_enh = create_mock_image(channel=channel, is_enhanced=True)
            path_enh = TEMP_DIR / f"band_{channel:02d}_enhanced.png"
            img_enh.save(path_enh)

    print(f"Created sample imagery in {TEMP_DIR}")
    return TEMP_DIR


# Create mock sample processor
class MockSampleProcessor:
    """Mock class for SampleProcessor that provides working previews."""

    def __init__(self, *args, **kwargs):
        self.temp_dir = TEMP_DIR

    def get_estimated_processing_time(
        self, channel, product_type, full_resolution=False
    ):
        """Mock estimated processing time."""
        return 5.0

    def create_sample_comparison(self, channel, product_type, date=None):
        """Create a mock sample comparison."""
        # Create a composite image with multiple sample types
        width, height = 800, 600
        img = Image.new("RGB", (width, height), color=(40, 40, 40))

        # Create 3 sample images
        std_img = create_mock_image(400, 300, channel, product_type.name, False)
        enh_img = create_mock_image(400, 300, channel, product_type.name, True)
        web_img = create_mock_image(400, 300, channel, product_type.name, True)

        # Paste them into the composite
        img.paste(std_img, (0, 0))
        img.paste(enh_img, (400, 0))
        img.paste(web_img, (200, 300))

        # Add labels
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial", 18)
        except IOError:
            font = ImageFont.load_default()

        draw.text((10, 10), "Standard", fill=(255, 255, 255), font=font)
        draw.text((410, 10), "Enhanced", fill=(255, 255, 255), font=font)
        draw.text((210, 310), "From NOAA CDN", fill=(255, 255, 255), font=font)

        return img

    def download_web_sample(self, channel, product_type, size="600x600"):
        """Mock downloading a web sample."""
        return create_mock_image(600, 400, channel, product_type.name, True)


# Apply mocks to the necessary modules
def apply_mocks():
    """Apply mocks for the GUI test."""
    # Create the sample imagery
    image_dir = create_sample_images()

    # Mock SampleProcessor class
    patches = [
        patch(
            "goesvfi.integrity_check.sample_processor.SampleProcessor",
            MockSampleProcessor,
        ),
        patch(
            "goesvfi.integrity_check.enhanced_imagery_tab.SampleProcessor",
            MockSampleProcessor,
        ),
    ]

    return patches


# Create a simplified version of the imagery tab for testing
def create_test_window():
    """Create a test window to show the imagery tab."""
    from goesvfi.integrity_check.enhanced_imagery_tab import EnhancedGOESImageryTab

    # Create a main window
    window = QMainWindow()
    window.setWindowTitle("GOES Imagery Visualization (Mocked Data)")
    window.setGeometry(100, 100, 1200, 800)

    # Create central widget and layout
    central = QWidget()
    layout = QVBoxLayout(central)

    # Create the enhanced imagery tab
    tab = EnhancedGOESImageryTab()

    # Add some explanatory text
    info_label = QLabel(
        "This is a demonstration of the enhanced GOES imagery UI with mocked satellite data."
    )
    info_label.setStyleSheet(
        "background-color: #007ACC; color: white; padding: 8px; font-weight: bold;"
    )
    info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    usage_text = """
    <html>
    <body style="font-family: Arial; font-size: 12px;">
    <p><b>Demo Controls:</b></p>
    <ul>
      <li>Select different channels in the left panel</li>
      <li>Click "Preview" to see mocked preview imagery</li>
      <li>Click "Download & Process" to simulate processing</li>
      <li>Try the IR, Water Vapor, Visible, and RGB tabs for different imagery types</li>
      <li>The fallback preview will demonstrate error handling if connection fails</li>
    </ul>
    <p><b>Note:</b> This uses simulated imagery - no actual satellite data is being downloaded.</p>
    </body>
    </html>
    """
    usage_label = QLabel(usage_text)

    # Add to layout
    layout.addWidget(info_label)
    layout.addWidget(usage_label)
    layout.addWidget(tab, stretch=1)

    # Set central widget
    window.setCentralWidget(central)

    return window


def main():
    """Run the GUI test."""
    print("Starting enhanced GOES Imagery Tab GUI test with mocked data...")

    # Apply mocks
    patches = apply_mocks()
    for p in patches:
        p.start()

    try:
        # Create a QApplication
        app = QApplication(sys.argv)

        # Create and show the test window
        window = create_test_window()
        window.show()

        # Run the application
        sys.exit(app.exec())

    finally:
        # Stop all patches
        for p in patches:
            p.stop()

        # Cleanup temp directory
        try:
            import shutil

            shutil.rmtree(TEMP_DIR)
            print(f"Cleaned up temporary directory: {TEMP_DIR}")
        except Exception as e:
            print(f"Warning: Failed to clean up temp directory: {e}")


if __name__ == "__main__":
    main()
