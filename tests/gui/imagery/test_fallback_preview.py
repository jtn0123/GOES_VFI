#!/usr/bin/env python3
"""
Simple test for the fallback preview feature
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QDialog
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor

class FallbackPreviewDemo(QDialog):
    """Simple demo of the enhanced fallback preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enhanced Error Handling Demo")
        self.setGeometry(100, 100, 800, 600)
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("GOES Imagery Enhanced Error Handling")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: #2c3e50; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "This demo shows the improved error handling and fallback preview UI for GOES imagery.\n"
            "The buttons below show different error scenarios the system can now handle gracefully."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("margin: 10px;")
        layout.addWidget(desc)
        
        # Preview image area
        self.image_label = QLabel()
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setStyleSheet("background-color: #202020; border: 1px solid #444;")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)
        
        # Buttons for different scenarios
        btn_timeout = QPushButton("Show Connection Timeout Error")
        btn_timeout.clicked.connect(
            lambda: self.createFallbackPreview("Connection timed out while accessing NOAA server")
        )
        layout.addWidget(btn_timeout)
        
        btn_not_found = QPushButton("Show 'No Data Available' Error")
        btn_not_found.clicked.connect(
            lambda: self.createFallbackPreview("No data found for selected date and time")
        )
        layout.addWidget(btn_not_found)
        
        btn_corrupt = QPushButton("Show Corrupted Data Error")
        btn_corrupt.clicked.connect(
            lambda: self.createFallbackPreview("Downloaded file is not a valid image format")
        )
        layout.addWidget(btn_corrupt)
        
        btn_general = QPushButton("Show General Error")
        btn_general.clicked.connect(
            lambda: self.createFallbackPreview("Error processing satellite data")
        )
        layout.addWidget(btn_general)
        
        # Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
        
        # Show a fallback preview initially
        self.createFallbackPreview("No data found for selected date and time")
    
    def createFallbackPreview(self, error_msg):
        """Create an enhanced fallback preview image."""
        # Create a pixmap for the preview
        width, height = 600, 400
        pix = QPixmap(width, height)
        pix.fill(QColor(40, 40, 40))  # Dark gray background
        
        # Create painter for drawing
        painter = QPainter(pix)
        
        # Draw title bar
        painter.fillRect(0, 0, width, 40, QColor(25, 52, 152))  # Dark blue
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        painter.drawText(20, 28, "Preview: Clean IR (Band 13)")
        
        # Draw status bar
        painter.fillRect(0, 45, width, 30, QColor(180, 32, 32))  # Dark red
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(width//2 - 100, 66, "STATUS: PREVIEW UNAVAILABLE")
        
        # Determine error type for better message
        if "timeout" in error_msg.lower():
            primary_reason = "Server connection timeout"
            suggestion = "Check your internet connection and try again later"
        elif "no data found" in error_msg.lower() or "selected date" in error_msg.lower():
            primary_reason = "No imagery data available"
            suggestion = "Try a different date/time or channel"
        elif "not a valid" in error_msg.lower() or "corrupt" in error_msg.lower():
            primary_reason = "Data corruption detected"
            suggestion = "Try a different channel or product type"
        else:
            primary_reason = "Error retrieving imagery"
            suggestion = "See details below"
        
        # Draw main content
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 11))
        
        # Main heading
        y_pos = 100
        painter.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        painter.drawText(30, y_pos, f"Issue: {primary_reason}")
        y_pos += 25
        
        # Context info
        painter.setFont(QFont('Arial', 11))
        painter.drawText(30, y_pos, "Channel: Clean IR (Band 13)")
        y_pos += 20
        painter.drawText(30, y_pos, "Product: FULL_DISK") 
        y_pos += 20
        painter.drawText(30, y_pos, f"Date/Time: 2025-05-08 17:45 UTC")
        y_pos += 30
        
        # Suggestion
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(30, y_pos, "Recommendation:")
        y_pos += 20
        painter.setFont(QFont('Arial', 11))
        painter.drawText(50, y_pos, suggestion)
        y_pos += 30
        
        # Technical details
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(30, y_pos, "Technical details:")
        y_pos += 20
        painter.setFont(QFont('Arial', 11))
        painter.drawText(50, y_pos, error_msg)
        y_pos += 40
        
        # Additional help info
        painter.setPen(QColor(180, 230, 255))  # Light blue
        painter.drawText(30, y_pos, "You can still proceed with processing using fallback imagery.")
        y_pos += 20
        painter.drawText(30, y_pos, "The system will use existing visualized samples.")
        
        # Add action button visualization
        painter.fillRect(150, 320, 300, 40, QColor(0, 120, 120))  # Teal button
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(175, 345, "Click 'Process Full Image' to continue")
        
        painter.end()
        
        # Set the preview image
        self.image_label.setPixmap(pix)
        
        # Print to console for demonstration
        print(f"Showing fallback preview for error: {error_msg}")

def main():
    """Run the demo application."""
    app = QApplication(sys.argv)
    demo = FallbackPreviewDemo()
    demo.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()