#!/usr/bin/env python3
"""
Test script for GOES imagery tab GUI with working zoom control

This script demonstrates satellite image viewing with a properly functioning
zoom control that starts fully zoomed out.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import io

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow,
    QLabel, QPushButton, QSlider, QSpinBox, QComboBox,
    QScrollArea, QSizePolicy, QGroupBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap, QImage, QFont

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    img = Image.new('RGB', (width, height), color=bg_color)
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
        [(center_x - radius, center_y - radius), 
         (center_x + radius, center_y + radius)],
        outline=(255, 255, 255),
        width=3
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
            [(x - size, y - size), (x + size, y + size)],
            fill=color,
            outline=None
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
    draw.text(
        ((width - text_width) // 2, 10),
        text,
        fill=text_color,
        font=font
    )
    
    # Add timestamp at bottom
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.rectangle([(0, height-40), (width, height)], fill=(0, 0, 0, 180))
    draw.text(
        (20, height-35),
        f"Timestamp: {timestamp}",
        fill=(255, 255, 255),
        font=small_font
    )
    
    # Add coordinates grid markers
    for i, x in enumerate(range(grid_spacing, width, grid_spacing*4)):
        draw.text((x, 60), f"{i*10}°E", fill=text_color, font=small_font)
    
    for i, y in enumerate(range(grid_spacing, height, grid_spacing*4)):
        draw.text((10, y), f"{i*10}°N", fill=text_color, font=small_font)
    
    return img


class ImageViewerWithZoom(QWidget):
    """Image viewer widget with working zoom control."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create image scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(800, 600)
        
        # Create image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(600, 400)
        
        # Set label as the scroll area widget
        self.scroll_area.setWidget(self.image_label)
        
        # Add scroll area to main layout
        main_layout.addWidget(self.scroll_area)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Zoom control group
        zoom_group = QGroupBox("Image Zoom")
        zoom_layout = QHBoxLayout(zoom_group)
        
        # Zoom label
        zoom_label = QLabel("Zoom:")
        zoom_label.setFont(QFont("Arial", 12))
        
        # Zoom slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 200)  # 10% to 200%
        self.zoom_slider.setValue(25)  # Start zoomed out at 25%
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.valueChanged.connect(self.updateZoom)
        
        # Zoom percentage display
        self.zoom_value = QLabel("25%")
        self.zoom_value.setFixedWidth(60)
        self.zoom_value.setFont(QFont("Arial", 12))
        
        # Add widgets to zoom layout
        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(self.zoom_slider, 1)  # Stretch factor of 1
        zoom_layout.addWidget(self.zoom_value)
        
        # Add zoom group to controls layout
        controls_layout.addWidget(zoom_group)
        
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
        
        # Add widgets to channel layout
        channel_layout.addWidget(self.channel_combo)
        
        # Add channel group to controls layout
        controls_layout.addWidget(channel_group)
        
        # Enhancement option
        enhancement_group = QGroupBox("Enhancement")
        enhancement_layout = QHBoxLayout(enhancement_group)
        
        # Enhancement checkbox
        self.enhance_check = QComboBox()
        self.enhance_check.addItem("Standard", False)
        self.enhance_check.addItem("Enhanced", True)
        self.enhance_check.currentIndexChanged.connect(self.toggleEnhancement)
        
        # Add widgets to enhancement layout
        enhancement_layout.addWidget(self.enhance_check)
        
        # Add enhancement group to controls layout
        controls_layout.addWidget(enhancement_group)
        
        # Add controls layout to main layout
        main_layout.addLayout(controls_layout)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Reset button
        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.clicked.connect(self.resetView)
        
        # Add widgets to button layout
        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch(1)
        
        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        # Add button layout to main layout
        main_layout.addLayout(button_layout)
        
        # Initialize with an image
        self.current_channel = 13
        self.enhanced = False
        self.loadImage()
        
    def loadImage(self):
        """Load a mock satellite image based on current settings."""
        # Create mock image
        img = create_mock_image(
            width=2048,
            height=2048,
            channel=self.current_channel,
            enhanced=self.enhanced
        )
        
        # Convert PIL image to QPixmap
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        qimg = QImage.fromData(img_bytes.getvalue())
        
        self.original_pixmap = QPixmap.fromImage(qimg)
        
        # Update zoom with current slider value to apply correct zoom
        self.updateZoom(self.zoom_slider.value())
        
    @pyqtSlot(int)
    def updateZoom(self, value):
        """Update the image zoom level based on slider value."""
        if not hasattr(self, 'original_pixmap'):
            return
            
        # Calculate zoom factor
        zoom_factor = value / 100.0
        
        # Update zoom value label
        self.zoom_value.setText(f"{value}%")
        
        # Calculate new size
        new_width = int(self.original_pixmap.width() * zoom_factor)
        new_height = int(self.original_pixmap.height() * zoom_factor)
        
        # Create scaled pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            new_width, 
            new_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Set the pixmap to the label
        self.image_label.setPixmap(scaled_pixmap)
        
        # Adjust label size to match scaled pixmap
        self.image_label.setFixedSize(scaled_pixmap.size())
        
        # Log
        logger.info(f"Zoom updated to {value}% - Image size: {new_width}x{new_height}")
    
    @pyqtSlot(int)
    def changeChannel(self, index):
        """Change the displayed channel."""
        channel = self.channel_combo.itemData(index)
        self.current_channel = channel
        self.loadImage()
        logger.info(f"Changed to channel {channel}")
    
    @pyqtSlot(int)
    def toggleEnhancement(self, index):
        """Toggle image enhancement."""
        enhanced = self.enhance_check.itemData(index)
        self.enhanced = enhanced
        self.loadImage()
        logger.info(f"Enhancement toggled: {enhanced}")
    
    def resetView(self):
        """Reset view to original state."""
        self.zoom_slider.setValue(25)  # Back to 25% zoom
        self.loadImage()
        logger.info("View reset")


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("GOES Satellite Imagery Viewer")
        self.setGeometry(100, 100, 1000, 800)
        
        # Create central widget
        central = QWidget()
        main_layout = QVBoxLayout(central)
        
        # Add header
        header = QLabel("GOES Satellite Imagery Viewer - Enhanced Zoom Control")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("background-color: #1A237E; color: white; padding: 10px;")
        main_layout.addWidget(header)
        
        # Add description
        desc = QLabel(
            "This demo shows satellite imagery with a properly functioning zoom control.\n"
            "The image starts fully zoomed out so you can see the entire image."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setFont(QFont("Arial", 12))
        desc.setStyleSheet("margin: 10px;")
        main_layout.addWidget(desc)
        
        # Create image viewer
        self.viewer = ImageViewerWithZoom()
        main_layout.addWidget(self.viewer)
        
        # Set central widget
        self.setCentralWidget(central)


def main():
    """Run the application."""
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create main window
    window = MainWindow()
    window.show()
    
    # Run the app
    sys.exit(app.exec())


if __name__ == "__main__":
    main()