"""
Enhanced GOES Satellite Imagery Tab

This module provides an enhanced version of the GOES Imagery Tab with additional
features for previewing, comparing, and organizing satellite imagery.
"""

import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QComboBox, QPushButton, QCheckBox, QRadioButton,
    QButtonGroup, QGroupBox, QFrame, QSpacerItem, QSizePolicy,
    QProgressBar, QToolButton, QSpinBox, QDateEdit, QTimeEdit,
    QFileDialog, QMessageBox, QTabWidget, QScrollArea, QSlider,
    QStackedWidget, QDialog
)
from PyQt6.QtCore import Qt, QDateTime, QDate, QTime, pyqtSignal, pyqtSlot, QSize, QTimer, QRect
from PyQt6.QtGui import QPixmap, QIcon, QFont, QMovie, QImage, QPainter

from .goes_imagery import (
    GOESImageryManager, ChannelType, ProductType, 
    ImageryMode, ProcessingMode
)
from .visualization_manager import VisualizationManager, ExtendedChannelType
from .sample_processor import SampleProcessor

# Configure logging
logger = logging.getLogger(__name__)


class SamplePreviewDialog(QDialog):
    """Dialog for previewing sample images and selecting processing options."""
    
    processingConfirmed = pyqtSignal(dict)
    
    def __init__(self, sample_processor: SampleProcessor, 
                 request: Dict[str, Any], 
                 parent: Optional[QWidget] = None) -> None:
        """
        Initialize the sample preview dialog.
        
        Args:
            sample_processor: SampleProcessor instance
            request: Image request parameters
            parent: Parent widget
        """
        super().__init__(parent)
        self.sample_processor = sample_processor
        self.request = request
        self.initUI()
    
    def initUI(self) -> None:
        """Initialize the UI components."""
        self.setWindowTitle("GOES Image Preview")
        self.resize(800, 600)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Title label
        title = QLabel(f"Preview: {ExtendedChannelType.get_display_name(self.request['channel'])}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Preview image - adjusted to match our more compact design
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(600, 350)  # Reduced from 400 to 350
        self.image_label.setStyleSheet("background-color: #202020;")
        self.image_label.setText("Loading preview...")
        
        # Add to layout
        layout.addWidget(self.image_label)
        
        # Processing options group
        options_group = QGroupBox("Processing Options")
        options_layout = QGridLayout(options_group)
        
        # Create options
        self.create_options(options_layout)
        
        # Add options to main layout
        layout.addWidget(options_group)
        
        # Status and progress
        self.status_label = QLabel("Preparing preview...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.process_btn = QPushButton("Process Full Image")
        self.process_btn.clicked.connect(self.confirmProcessing)
        self.process_btn.setEnabled(False)
        
        est_time = self.sample_processor.get_estimated_processing_time(
            self.request['channel'], 
            self.request['product_type']
        )
        self.process_btn.setToolTip(f"Estimated processing time: {est_time:.1f} seconds")
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.process_btn)
        
        layout.addLayout(button_layout)
        
        # Initialize preview loading
        QTimer.singleShot(100, self.loadPreview)
    
    def create_options(self, layout: QGridLayout) -> None:
        """Create processing option controls."""
        # Image type options
        type_label = QLabel("Image Type:")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Standard (Grayscale)", "standard")
        self.type_combo.addItem("Enhanced (Colorized)", "enhanced")
        
        # Channel-specific options
        channel = self.request['channel']
        if isinstance(channel, int):
            channel_num = channel
        elif isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = 13  # Default to IR
        
        if channel_num in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]:
            # IR-specific options
            temp_label = QLabel("Temperature Range:")
            self.min_temp_spin = QSpinBox()
            self.min_temp_spin.setRange(180, 310)
            self.min_temp_spin.setValue(200)
            
            self.max_temp_spin = QSpinBox()
            self.max_temp_spin.setRange(220, 350)
            self.max_temp_spin.setValue(320)
            
            temp_layout = QHBoxLayout()
            temp_layout.addWidget(self.min_temp_spin)
            temp_layout.addWidget(QLabel("-"))
            temp_layout.addWidget(self.max_temp_spin)
            
            layout.addWidget(temp_label, 0, 0)
            layout.addLayout(temp_layout, 0, 1)
        
        # Resolution options
        resolution_label = QLabel("Resolution:")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItem("Full Resolution", "full")
        self.resolution_combo.addItem("Medium (Faster)", "medium")
        self.resolution_combo.addItem("Low (Fastest)", "low")
        
        # Add to layout
        layout.addWidget(type_label, 1, 0)
        layout.addWidget(self.type_combo, 1, 1)
        
        layout.addWidget(resolution_label, 2, 0)
        layout.addWidget(self.resolution_combo, 2, 1)
    
    def loadPreview(self) -> None:
        """Load and display the preview image."""
        try:
            self.progress_bar.setValue(10)
            self.status_label.setText("Downloading sample data...")
            
            # Create sample comparison
            comparison = self.sample_processor.create_sample_comparison(
                self.request['channel'],
                self.request['product_type']
            )
            
            self.progress_bar.setValue(80)
            
            if comparison:
                # Convert PIL Image to QPixmap
                img_data = comparison.tobytes("raw", "RGB")
                qimg = QImage(img_data, comparison.width, comparison.height, 
                             comparison.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                
                # Display the image
                self.image_label.setPixmap(pixmap)
                self.status_label.setText("Preview loaded successfully")
                self.process_btn.setEnabled(True)
            else:
                # Create a fallback preview image with text explanation
                self.createFallbackPreview()
                self.status_label.setText("Could not load imagery - using sample visualization")
                # Still enable processing despite preview failure
                self.process_btn.setEnabled(True)
        
        except Exception as e:
            logger.error(f"Error loading preview: {e}")
            self.createFallbackPreview(error_msg=str(e))
            self.status_label.setText("Failed to load preview - using sample visualization")
            # Still enable processing despite preview failure
            self.process_btn.setEnabled(True)
            
        finally:
            self.progress_bar.setValue(100)
            
    def createFallbackPreview(self, error_msg: Optional[Any] = None) -> None:
        """Create a fallback preview image when download/processing fails."""
        # Create a more compact image with text and visual indicators (reduced height)
        width, height = 600, 350  # Reduced from 500 to 350 for better fit
        pix = QPixmap(width, height)
        pix.fill(Qt.GlobalColor.darkGray)
        
        # Add text explanation
        painter = QPainter(pix)
        
        # Create a better title bar
        painter.fillRect(0, 0, width, 30, Qt.GlobalColor.darkBlue)  # Slightly smaller title bar
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        
        # Determine channel and product info
        channel = self.request['channel']
        if isinstance(channel, int):
            channel_num = channel
        else:
            channel_num = channel.number
            
        channel_name = ExtendedChannelType.get_display_name(self.request['channel'])
        product_name = self.request['product_type'].name
        
        # Draw title (adjusted positioning for smaller header)
        title_text = f"Preview: {channel_name} ({product_name})"
        painter.drawText(20, 22, title_text)
        
        # Draw info icon in top right
        info_icon_rect = QRect(width - 35, 2, 26, 26)
        painter.drawText(info_icon_rect, Qt.AlignmentFlag.AlignCenter, "ℹ")
        
        # Draw main content
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 12))
        
        # Display appropriate error message
        status_text = "STATUS: PREVIEW UNAVAILABLE"
        
        # Create message based on error
        if error_msg:
            # Organize error into a more helpful message
            if "timeout" in str(error_msg).lower():
                primary_reason = "Server connection timeout"
                suggestion = "Check your internet connection and try again later"
            elif "no data found" in str(error_msg).lower():
                primary_reason = "No imagery data available for the selected date/time"
                suggestion = "Try a different date/time or channel"
            elif "not a valid image" in str(error_msg).lower():
                primary_reason = "The retrieved imagery is corrupted or invalid"
                suggestion = "Try a different channel or product type"
            else:
                primary_reason = "Error retrieving imagery"
                suggestion = "See details below"
                
            # Format the primary message
            message_lines = [
                f"Issue: {primary_reason}",
                f"Channel: {channel_name} (Channel {channel_num})",
                f"Product: {product_name}",
                "",
                f"Suggestion: {suggestion}",
                "",
                "Technical details:",
                str(error_msg),
                "",
                "You can still proceed with processing.",
                "The system will use fallback imagery samples."
            ]
        else:
            # No specific error, provide general guidance
            message_lines = [
                f"Could not load preview for {channel_name} ({product_name}).",
                "",
                "Possible reasons:",
                "• No imagery data available for the selected date/time",
                "• Network connection issues accessing NOAA servers",
                "• Temporary server outage for this specific product",
                "",
                "Recommendations:",
                "• Try a different date/time (ideally within the last 12 hours)",
                "• Try a different channel (Band 13 IR has most reliable coverage)",
                "• Try Full Disk product type instead of Mesoscale",
                "",
                "You can still continue with processing.",
                "The system will use fallback imagery samples."
            ]
        
        # Draw status banner (adjusted position for smaller header)
        status_rect = QRect(0, 40, width, 25)
        painter.fillRect(status_rect, Qt.GlobalColor.darkRed)
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status_text)
        
        # Draw each line of text - more compact spacing
        painter.setFont(QFont('Arial', 10))
        y = 80  # Start text closer to status bar
        for line in message_lines:
            painter.drawText(30, y, line)
            y += 20  # Reduced line spacing from 25 to 20
            
        # Draw helpful action buttons visually (decorative) - more compact
        action_rect = QRect(30, height - 50, width - 60, 35)  # Moved up & smaller height
        painter.fillRect(action_rect, Qt.GlobalColor.darkCyan)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        painter.drawText(action_rect, Qt.AlignmentFlag.AlignCenter, 
                        "Click 'Process Full Image' to continue with fallback data")
        
        painter.end()
        
        # Set the fallback image
        self.image_label.setPixmap(pix)
    
    def confirmProcessing(self) -> None:
        """Confirm processing and collect options."""
        # Collect selected options
        options = {
            'image_type': self.type_combo.currentData(),
            'resolution': self.resolution_combo.currentData()
        }
        
        # Add IR-specific options if available
        if hasattr(self, 'min_temp_spin'):
            options['min_temp'] = self.min_temp_spin.value()
            options['max_temp'] = self.max_temp_spin.value()
        
        # Update original request with options
        self.request.update(options)
        
        # Emit signal with updated request
        self.processingConfirmed.emit(self.request)
        
        # Close dialog
        self.accept()


class EnhancedImageSelectionPanel(QWidget):
    """Enhanced panel for selecting satellite imagery options."""
    
    imageRequested = pyqtSignal(dict)
    previewRequested = pyqtSignal(dict)
    
    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.initUI()
    
    def initUI(self) -> None:
        """Initialize the UI components with optimized space usage."""
        # Main layout with minimal margins
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
        layout.setSpacing(2)  # Minimal spacing

        # Create tab widget for organizing channel groups with wider layout to show all tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)  # More compact tab appearance
        # Make tabs more compact but ensure they're all visible
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 3px 6px;
                height: 20px;
                min-width: 60px;
                max-width: 120px;
            }
            QTabBar::scroller {
                width: 20px;
            }
        """)
        # Enable scrolling tabs to ensure all tabs are accessible
        self.tabs.setUsesScrollButtons(True)

        # Create tabs for different channel groups
        self.create_ir_tab()
        self.create_water_vapor_tab()
        self.create_visible_tab()
        self.create_rgb_tab()

        # Add tabs to widget with stretch priority
        layout.addWidget(self.tabs, 1)
        
        # Create control panel with enhanced styling and better visual organization
        # Use a frame with subtle styling to visually separate the controls
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 2px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 2px 8px;
                min-height: 22px;
            }
            QComboBox:hover {
                background-color: #3a3a3a;
                border-color: #555;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QDateEdit, QTimeEdit {
                background-color: #333;
                color: white;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 2px;
                min-height: 22px;
            }
            QDateEdit:hover, QTimeEdit:hover {
                background-color: #3a3a3a;
                border-color: #555;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #555;
                border-radius: 2px;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
            }
        """)

        fields_layout = QGridLayout(control_frame)
        fields_layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
        fields_layout.setHorizontalSpacing(4)  # Reduced spacing
        fields_layout.setVerticalSpacing(4)  # Reduced spacing

        # Row 1: Product Type with icon
        product_label = QLabel("<b>Product:</b>")
        product_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.product_combo = QComboBox()
        self.product_combo.setIconSize(QSize(16, 16))

        for product in ProductType:
            display_name = product.name.replace('_', ' ').title()
            # Add icons based on product type name (without using enum comparison)
            if display_name.lower() == "full disk":
                self.product_combo.addItem("🌎 " + display_name, product)
            elif "conus" in display_name.lower():
                self.product_combo.addItem("🇺🇸 " + display_name, product)
            elif "mesoscale" in display_name.lower():
                self.product_combo.addItem("🔍 " + display_name, product)
            else:
                self.product_combo.addItem(display_name, product)

        fields_layout.addWidget(product_label, 0, 0)
        fields_layout.addWidget(self.product_combo, 0, 1, 1, 3)

        # Row 2: Date and Time with calendar/clock icons
        date_label = QLabel("<b>Date:</b> 📅")
        date_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        time_label = QLabel("<b>Time:</b> 🕒")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.time_edit = QTimeEdit(QTime.currentTime())
        self.time_edit.setDisplayFormat("HH:mm")

        fields_layout.addWidget(date_label, 1, 0)
        fields_layout.addWidget(self.date_edit, 1, 1)
        fields_layout.addWidget(time_label, 1, 2)
        fields_layout.addWidget(self.time_edit, 1, 3)

        # Row 3: Verify check (with better UI text)
        self.verify_check = QCheckBox("Preview before processing")
        self.verify_check.setChecked(True)
        self.verify_check.setToolTip("Show a preview before generating the full image")
        fields_layout.addWidget(self.verify_check, 2, 0, 1, 4)

        # Add the frame directly to the main layout
        layout.addWidget(control_frame)
        
        # Button container with attractive styling
        button_container = QWidget()
        button_container.setStyleSheet("""
            QPushButton {
                min-height: 34px;
                border-radius: 6px;
                font-weight: bold;
                padding: 6px 18px;
                font-size: 11pt;
            }
            QPushButton#preview {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4a4a, stop:1 #383838);
                color: white;
                border: 1px solid #555;
            }
            QPushButton#preview:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #555555, stop:1 #444444);
                border: 1px solid #666;
            }
            QPushButton#process {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: 1px solid #4a8cce;
            }
            QPushButton#process:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3eacff, stop:1 #3498db);
                border: 1px solid #4a8cce;
            }
        """)

        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(8, 8, 8, 8)
        button_layout.setSpacing(10)

        # Create visually distinct buttons with icons
        self.preview_btn = QPushButton("🔍 Preview")
        self.preview_btn.setObjectName("preview")
        self.preview_btn.clicked.connect(self.requestPreview)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setToolTip("Preview the selected channel before processing")

        self.download_btn = QPushButton("⚙️ Process")
        self.download_btn.setObjectName("process")
        self.download_btn.clicked.connect(self.requestImage)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setToolTip("Process the selected channel imagery")

        button_layout.addWidget(self.preview_btn)
        button_layout.addWidget(self.download_btn)

        # Add button container to main layout
        layout.addWidget(button_container)

        # Add to original field layout for backward compatibility
        # but hide these buttons as we'll use our better styled ones
        dummy_btn1 = QPushButton("Preview")
        dummy_btn1.setVisible(False)
        dummy_btn2 = QPushButton("Process")
        dummy_btn2.setVisible(False)
        fields_layout.addWidget(dummy_btn1, 2, 2)
        fields_layout.addWidget(dummy_btn2, 2, 3)
    
    def create_ir_tab(self) -> None:
        """Create tab for infrared channels with a compact layout and scientific organization."""
        ir_tab = QWidget()
        ir_layout = QVBoxLayout(ir_tab)
        ir_layout.setContentsMargins(3, 3, 3, 3)
        ir_layout.setSpacing(4)

        # Add explanatory header with scientific context
        header = QLabel("Infrared Channels (Thermal)")
        header.setStyleSheet("""
            font-weight: bold;
            color: #e0e0e0;
            background-color: #333;
            padding: 5px;
            border-radius: 4px;
            font-size: 12pt;
            border: 1px solid #4a8cce;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ir_layout.addWidget(header)

        # Add description of IR channels
        desc = QLabel("Thermal channels detect heat radiation from Earth and clouds. Used for temperature measurement, cloud studies, and nighttime imaging.")
        desc.setStyleSheet("color: #ccc; font-size: 9pt; font-style: italic;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ir_layout.addWidget(desc)

        # Create scrollable area to ensure buttons are always accessible
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create container widget for buttons
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(2, 2, 2, 2)  # Minimal margins
        grid_layout.setSpacing(4)  # Slightly increased spacing for readability

        # Group 1: Primary IR Channels (most commonly used)
        group1_label = QLabel("Primary IR Channels")
        group1_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group1_label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add primary IR channels
        ch13_btn = self.create_channel_button(
            13, "Clean IR", "10.3 μm",
            "Primary infrared window channel. Used for cloud detection, fog/dew point, temperature, and surface/cloud top temperature."
        )
        ch07_btn = self.create_channel_button(
            7, "Shortwave IR", "3.9 μm",
            "Shortwave window. Used for fire detection, fog/stratus, and nighttime cloud discrimination."
        )
        ch14_btn = self.create_channel_button(
            14, "IR Longwave", "11.2 μm",
            "Longwave infrared window. Similar to Band 13 but less sensitive to water vapor."
        )

        grid_layout.addWidget(ch13_btn, 1, 0)
        grid_layout.addWidget(ch07_btn, 1, 1)
        grid_layout.addWidget(ch14_btn, 1, 2)

        # Group 2: Specialized IR Channels
        group2_label = QLabel("Specialized IR Channels")
        group2_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group2_label, 2, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add specialized IR channels
        ch15_btn = self.create_channel_button(
            15, "IR 'Dirty'", "12.3 μm",
            "Dirty longwave window. Sensitive to volcanic ash and dust. Used with Band 13 for split window techniques."
        )
        ch11_btn = self.create_channel_button(
            11, "Cloud Phase", "8.4 μm",
            "Cloud phase detection. Helps distinguish between ice and water clouds."
        )
        ch12_btn = self.create_channel_button(
            12, "Ozone", "9.6 μm",
            "Ozone absorption. Used for total ozone estimation and jet stream identification."
        )
        ch16_btn = self.create_channel_button(
            16, "CO2 Longwave", "13.3 μm",
            "CO2 absorption band. Used for cloud height detection and atmospheric motion vectors."
        )

        grid_layout.addWidget(ch15_btn, 3, 0)
        grid_layout.addWidget(ch11_btn, 3, 1)
        grid_layout.addWidget(ch12_btn, 3, 2)
        grid_layout.addWidget(ch16_btn, 4, 0)

        # Default selection - most commonly used channel
        ch13_btn.setChecked(True)

        # Add container to scroll area
        scroll.setWidget(container)

        # Add scroll area to layout
        ir_layout.addWidget(scroll)

        # Add the tab with descriptive icon and name
        self.tabs.addTab(ir_tab, "🔴 IR")
    
    def create_water_vapor_tab(self) -> None:
        """Create tab for water vapor channels with scientific organization."""
        wv_tab = QWidget()
        wv_layout = QVBoxLayout(wv_tab)
        wv_layout.setContentsMargins(3, 3, 3, 3)
        wv_layout.setSpacing(4)

        # Add explanatory header with scientific context
        header = QLabel("Water Vapor Channels")
        header.setStyleSheet("""
            font-weight: bold;
            color: #e0e0e0;
            background-color: #333;
            padding: 5px;
            border-radius: 4px;
            font-size: 12pt;
            border: 1px solid #4a8cce;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wv_layout.addWidget(header)

        # Add description of water vapor channels
        desc = QLabel("Water vapor channels detect atmospheric moisture at different altitudes. Essential for tracking atmospheric motion, jet streams, and storm development.")
        desc.setStyleSheet("color: #ccc; font-size: 9pt; font-style: italic;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wv_layout.addWidget(desc)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Create container widget
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(4)

        # Add informative label
        altitude_info = QLabel("Channels are organized by atmospheric altitude:")
        altitude_info.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(altitude_info, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add channel selection buttons with scientific descriptions
        ch08_btn = self.create_channel_button(
            8, "Upper-Level WV", "6.2 μm",
            "Detects water vapor in the upper atmosphere (approximately 350-500 mb). Shows high-altitude moisture and helps track jet streams and upper-level disturbances."
        )
        ch09_btn = self.create_channel_button(
            9, "Mid-Level WV", "6.9 μm",
            "Detects water vapor in the mid-atmosphere (approximately 500-700 mb). Provides information about mid-level moisture content and atmospheric circulation."
        )
        ch10_btn = self.create_channel_button(
            10, "Lower-Level WV", "7.3 μm",
            "Detects water vapor in the lower atmosphere (approximately 700-850 mb). Useful for tracking lower tropospheric moisture and potential thunderstorm development."
        )

        # Add visual diagram (as text)
        level_diagram = QLabel("""
        Atmospheric Levels:      Example Features:

        Upper (6.2 μm)           Jet streams, high clouds
           ↑
        Mid (6.9 μm)             Mid-level moisture, fronts
           ↑
        Lower (7.3 μm)           Low-level moisture, fog
        """)
        level_diagram.setStyleSheet("""
            color: #dddddd;
            font-size: 9pt;
            font-family: monospace;
            background-color: #252525;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #3c3c3c;
        """)

        # Add to grid layout with organization by height
        grid_layout.addWidget(ch08_btn, 1, 0)
        grid_layout.addWidget(ch09_btn, 1, 1)
        grid_layout.addWidget(ch10_btn, 1, 2)
        grid_layout.addWidget(level_diagram, 2, 0, 1, 3)

        # Add container to scroll area
        scroll.setWidget(container)
        wv_layout.addWidget(scroll)

        # Add the tab with descriptive icon
        self.tabs.addTab(wv_tab, "💧 Water")
    
    def create_visible_tab(self) -> None:
        """Create tab for visible and near-IR channels with scientific organization."""
        vis_tab = QWidget()
        vis_layout = QVBoxLayout(vis_tab)
        vis_layout.setContentsMargins(3, 3, 3, 3)
        vis_layout.setSpacing(4)

        # Add explanatory header with scientific context
        header = QLabel("Visible & Near-IR Channels")
        header.setStyleSheet("""
            font-weight: bold;
            color: #e0e0e0;
            background-color: #333;
            padding: 5px;
            border-radius: 4px;
            font-size: 12pt;
            border: 1px solid #4a8cce;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vis_layout.addWidget(header)

        # Add description of visible channels
        desc = QLabel("Visible and near-infrared channels show reflected sunlight from Earth's surface, clouds, and atmosphere. These channels are only effective during daylight hours.")
        desc.setStyleSheet("color: #ccc; font-size: 9pt; font-style: italic;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vis_layout.addWidget(desc)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Create container widget
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(4)

        # Group 1: Visible Light Channels
        group1_label = QLabel("Visible Spectrum Channels")
        group1_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group1_label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add visible channels with scientific descriptions
        ch01_btn = self.create_channel_button(
            1, "Blue", "0.47 μm",
            "Blue visible channel. Used for daytime aerosol detection and as a component of true-color imagery. Helps detect dust, haze, and smoke."
        )
        ch02_btn = self.create_channel_button(
            2, "Red", "0.64 μm",
            "Red visible channel. Primary visible band for cloud detection, monitoring dust storms, and volcano plumes. Component of true-color imagery."
        )
        ch03_btn = self.create_channel_button(
            3, "Veggie", "0.86 μm",
            "Near-IR vegetation channel. Strongly reflects healthy vegetation. Used for vegetation health monitoring, fire monitoring, and fog detection."
        )

        grid_layout.addWidget(ch01_btn, 1, 0)
        grid_layout.addWidget(ch02_btn, 1, 1)
        grid_layout.addWidget(ch03_btn, 1, 2)

        # Group 2: Special Near-IR Channels
        group2_label = QLabel("Near-IR Specialty Channels")
        group2_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group2_label, 2, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add specialized near-IR channels
        ch04_btn = self.create_channel_button(
            4, "Cirrus", "1.37 μm",
            "Cirrus cloud detection. This channel readily detects thin cirrus clouds which might be missed by other channels."
        )
        ch05_btn = self.create_channel_button(
            5, "Snow/Ice", "1.6 μm",
            "Snow/Ice discrimination. Helps distinguish between clouds (highly reflective) and snow/ice (absorbs at this wavelength)."
        )
        ch06_btn = self.create_channel_button(
            6, "Cloud Particle", "2.2 μm",
            "Cloud particle size. Helps distinguish between water and ice clouds based on particle size. Also useful for land applications."
        )

        # Add information about typical applications
        applications = QLabel("""
        • True Color images use bands 1, 2, and 3
        • Snow detection uses band 5
        • Cirrus cloud detection uses band 4
        • Daytime fog detection uses bands 3 and 2
        """)
        applications.setStyleSheet("""
            color: #dddddd;
            font-size: 9pt;
            background-color: #252525;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #3c3c3c;
        """)
        applications.setWordWrap(True)

        grid_layout.addWidget(ch04_btn, 3, 0)
        grid_layout.addWidget(ch05_btn, 3, 1)
        grid_layout.addWidget(ch06_btn, 3, 2)
        grid_layout.addWidget(applications, 4, 0, 1, 3)

        # Add container to scroll area
        scroll.setWidget(container)
        vis_layout.addWidget(scroll)

        # Add the tab with descriptive icon
        self.tabs.addTab(vis_tab, "☀️ Visible")
    
    def create_rgb_tab(self) -> None:
        """Create tab for RGB composite products with scientific organization."""
        rgb_tab = QWidget()
        rgb_layout = QVBoxLayout(rgb_tab)
        rgb_layout.setContentsMargins(3, 3, 3, 3)
        rgb_layout.setSpacing(4)

        # Add explanatory header with scientific context
        header = QLabel("RGB Composite Products")
        header.setStyleSheet("""
            font-weight: bold;
            color: #e0e0e0;
            background-color: #333;
            padding: 5px;
            border-radius: 4px;
            font-size: 12pt;
            border: 1px solid #4a8cce;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rgb_layout.addWidget(header)

        # Add description of RGB composite products
        desc = QLabel("RGB composites combine multiple satellite channels to highlight specific atmospheric and surface features. These derived products simplify analysis of complex phenomena.")
        desc.setStyleSheet("color: #ccc; font-size: 9pt; font-style: italic;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rgb_layout.addWidget(desc)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Create container widget
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(4)

        # Group 1: Basic RGB Products
        group1_label = QLabel("Standard RGB Products")
        group1_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group1_label, 0, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add RGB composite buttons with descriptions
        true_color_btn = self.create_channel_button(
            100, "True Color", "RGB",
            "Natural-looking RGB composite made from Bands 1 (blue), 2 (red), and 3 (green, approximated). Shows Earth as the human eye would see it."
        )
        airmass_btn = self.create_channel_button(
            103, "Airmass RGB", "RGB",
            "Distinguishes between warm/cold and dry/moist air masses. Useful for tracking jet streams, frontal systems, and high-level moisture."
        )

        grid_layout.addWidget(true_color_btn, 1, 0)
        grid_layout.addWidget(airmass_btn, 1, 1)

        # Group 2: Specialized RGB Products
        group2_label = QLabel("Specialized RGB Products")
        group2_label.setStyleSheet("""
            color: #aaddff;
            font-weight: bold;
            margin-top: 5px;
            font-size: 10pt;
            background-color: #2a2a2a;
            padding: 3px;
            border-radius: 3px;
        """)
        grid_layout.addWidget(group2_label, 2, 0, 1, 3, Qt.AlignmentFlag.AlignCenter)

        # Add specialized RGB products
        fire_rgb_btn = self.create_channel_button(
            104, "Fire Temperature", "RGB",
            "Highlights hot spots related to fires. Combines shortwave IR and visible bands to detect active fires and hot surfaces."
        )
        dust_rgb_btn = self.create_channel_button(
            105, "Dust RGB", "RGB",
            "Detects airborne dust and sand. Uses split window IR channels to distinguish dust from other features."
        )
        cloud_phase_btn = self.create_channel_button(
            106, "Day Cloud Phase", "RGB",
            "Distinguishes between ice clouds (red), water clouds (white/cyan), and snow (green). Helps identify different cloud types and phase states."
        )

        # Add RGB composite information
        rgb_info = QLabel("""
        RGB composites are created by assigning different channels to the
        red, green, and blue components of a color image. Each has specific
        applications for weather forecasting and analysis:

        • True Color: General Earth viewing, smoke, dust, clouds
        • Airmass: Jet streams, air masses, stratospheric intrusions
        • Fire: Active fire detection, hot surfaces
        • Dust: Dust and sand storms, aerosol tracking
        • Cloud Phase: Cloud type identification, aviation safety
        """)
        rgb_info.setStyleSheet("""
            color: #dddddd;
            font-size: 9pt;
            background-color: #252525;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #3c3c3c;
        """)
        rgb_info.setWordWrap(True)

        grid_layout.addWidget(fire_rgb_btn, 3, 0)
        grid_layout.addWidget(dust_rgb_btn, 3, 1)
        grid_layout.addWidget(cloud_phase_btn, 3, 2)
        grid_layout.addWidget(rgb_info, 4, 0, 1, 3)

        # Add container to scroll area
        scroll.setWidget(container)
        rgb_layout.addWidget(scroll)

        # Add the tab with descriptive icon
        self.tabs.addTab(rgb_tab, "🌈 RGB")
    
    def create_channel_button(self, channel_num: int, name: str, wavelength: str, description: str = "") -> QPushButton:
        """Create a visually-enhanced button for channel selection with improved readability.

        Args:
            channel_num: The ABI channel number
            name: Display name for the channel
            wavelength: Wavelength in μm or other unit
            description: Optional scientific description of the channel
        """
        # Use push button with enhanced styling
        button = QPushButton()
        button.setCheckable(True)
        button.setProperty("class", "channel-button")

        # Create more sophisticated icon selection based on channel type and name
        icon = ""

        # IR channels (heat)
        if "IR" in name or name in ["Clean IR", "IR Longwave", "IR 'Dirty'", "Shortwave IR"]:
            icon = "🔴"  # Red circle for IR

        # Water vapor channels
        elif "WV" in name or "Water" in name or name in ["Upper-Level WV", "Mid-Level WV", "Lower-Level WV"]:
            icon = "💧"  # Water drop for Water Vapor

        # Visible light channels
        elif name in ["Blue", "Red", "Veggie"] or "Visible" in name:
            icon = "☀️"  # Sun for Visible

        # Snow/Ice channels
        elif "Snow" in name or "Ice" in name:
            icon = "❄️"  # Snowflake for snow/ice

        # Cloud-related channels
        elif "Cloud" in name or "Cirrus" in name:
            icon = "☁️"  # Cloud for cloud channels

        # Ozone channel
        elif "Ozone" in name:
            icon = "🌍"  # Earth for atmosphere/ozone

        # RGB composite products
        elif "RGB" in wavelength:
            if "True Color" in name:
                icon = "🌈"  # Rainbow for true color
            elif "Fire" in name:
                icon = "🔥"  # Fire for fire temperature
            elif "Dust" in name:
                icon = "🌪️"  # Tornado for dust
            elif "Airmass" in name:
                icon = "🌬️"  # Wind for airmass
            elif "Cloud" in name:
                icon = "☁️"  # Cloud for cloud phase
            else:
                icon = "🌈"  # Rainbow for other RGB products

        # Format text with proper spacing and alignment for better display
        # For RGB composites, we don't need to show band number
        if "RGB" in wavelength:
            label_text = f"{icon} {name}\n{wavelength}"
        else:
            label_text = f"{icon} {name}\n{wavelength}\nBand {channel_num}"

        # Set the text directly on the button
        button.setText(label_text)
        button.setMinimumWidth(100)  # Moderate width to fit more in a row
        button.setMaximumHeight(70)  # Slightly shorter for better vertical space usage

        # Add detailed tooltips with scientific information
        tooltip = f"ABI Band {channel_num}: {name}\nWavelength: {wavelength}"

        # Add scientific description if provided
        if description:
            tooltip += f"\n\n{description}"

        button.setToolTip(tooltip)

        # Apply enhanced styling for better text appearance in all tabs
        button.setStyleSheet("""
            QPushButton {
                text-align: center;
                padding: 6px;
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QPushButton:checked {
                background-color: #2b5d8e;
                border: 1px solid #3a6ea5;
                font-weight: bold;
            }
        """)

        # Store channel number as a property
        # We're setting a custom attribute, so we need to tell type checker to ignore this
        button.channel = channel_num  # type: ignore[attr-defined]

        # Add to button group if not already created
        if not hasattr(self, 'channel_group'):
            self.channel_group = QButtonGroup(self)
            self.channel_group.setExclusive(True)

        self.channel_group.addButton(button)

        # Set minimum height for consistent button sizing but allow them to grow if needed
        button.setMinimumHeight(60)

        # Add cursor change on hover for better usability
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        return button
    
    def get_selected_channel(self) -> int:
        """Get the selected channel number."""
        if not hasattr(self, 'channel_group'):
            return 13  # Default to clean IR

        # Get the checked button from the group
        selected = self.channel_group.checkedButton()
        if selected is None:
            return 13

        # Access the channel attribute we set dynamically
        # We need to use type: ignore for the custom attribute we set
        # Also need to explicitly cast to int to avoid Any return type
        return int(selected.channel)  # type: ignore[attr-defined]
    
    def get_datetime(self) -> datetime:
        """Get the selected date and time."""
        date = self.date_edit.date().toPyDate()
        time = self.time_edit.time().toPyTime()
        
        return datetime.combine(date, time)
    
    def requestPreview(self) -> None:
        """Request a preview of the selected imagery."""
        # Get selected options
        channel = self.get_selected_channel()
        product_idx = self.product_combo.currentIndex()
        product = self.product_combo.itemData(product_idx)
        date_time = self.get_datetime()
        
        # Create request
        request = {
            'channel': channel,
            'product_type': product,
            'date_time': date_time,
            'preview': True
        }
        
        # Emit signal
        self.previewRequested.emit(request)
    
    def requestImage(self) -> None:
        """Request full processing of the selected imagery."""
        # Get selected options
        channel = self.get_selected_channel()
        product_idx = self.product_combo.currentIndex()
        product = self.product_combo.itemData(product_idx)
        date_time = self.get_datetime()
        verify = self.verify_check.isChecked()
        
        # Create request
        request = {
            'channel': channel,
            'product_type': product,
            'date_time': date_time,
            'verify': verify
        }
        
        # Emit signal with request parameters
        self.imageRequested.emit(request)


class EnhancedImageViewPanel(QWidget):
    """Enhanced panel for viewing satellite imagery with additional features."""
    
    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self.initUI()
    
    def initUI(self) -> None:
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Image display tab widget
        self.view_tabs = QTabWidget()
        
        # Add tabs for different views
        self.create_single_view_tab()
        self.create_comparison_view_tab()
        self.create_time_series_tab()
        
        # Add tabs to layout
        layout.addWidget(self.view_tabs)
        
        # Status bar
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel("Ready")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.progress)
        
        layout.addWidget(status_frame)
    
    def create_single_view_tab(self) -> None:
        """Create tab for single image view."""
        single_tab = QWidget()
        layout = QVBoxLayout(single_tab)
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(600, 600)
        self.image_label.setStyleSheet("background-color: #202020;")
        
        # Default message
        self.image_label.setText("No imagery loaded")
        
        # Add scroll area for large images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_label)
        
        layout.addWidget(scroll)
        
        # Add controls for image manipulation
        controls_layout = QHBoxLayout()
        
        # Zoom controls
        zoom_label = QLabel("Zoom:")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        controls_layout.addWidget(zoom_label)
        controls_layout.addWidget(self.zoom_slider, 1)
        
        # Save button
        self.save_btn = QPushButton("Save Image")
        self.save_btn.clicked.connect(self.saveImage)
        
        controls_layout.addWidget(self.save_btn)
        
        layout.addLayout(controls_layout)
        
        # Add the tab
        self.view_tabs.addTab(single_tab, "Single View")
    
    def create_comparison_view_tab(self) -> None:
        """Create tab for comparison view (side-by-side)."""
        comp_tab = QWidget()
        layout = QVBoxLayout(comp_tab)
        
        # Split view
        self.comparison_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left image
        self.left_image = QLabel()
        self.left_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_image.setMinimumSize(300, 400)
        self.left_image.setStyleSheet("background-color: #202020;")
        self.left_image.setText("Image 1")
        
        # Right image
        self.right_image = QLabel()
        self.right_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_image.setMinimumSize(300, 400)
        self.right_image.setStyleSheet("background-color: #202020;")
        self.right_image.setText("Image 2")
        
        # Add to splitter
        self.comparison_splitter.addWidget(self.left_image)
        self.comparison_splitter.addWidget(self.right_image)
        
        # Set equal sizes
        self.comparison_splitter.setSizes([500, 500])
        
        layout.addWidget(self.comparison_splitter)
        
        # Add the tab
        self.view_tabs.addTab(comp_tab, "Comparison")
    
    def create_time_series_tab(self) -> None:
        """Create tab for time series animation."""
        ts_tab = QWidget()
        layout = QVBoxLayout(ts_tab)
        
        # Animation display
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_label.setMinimumSize(600, 600)
        self.animation_label.setStyleSheet("background-color: #202020;")
        self.animation_label.setText("No animation loaded")
        
        layout.addWidget(self.animation_label)
        
        # Animation controls
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        
        self.animation_slider = QSlider(Qt.Orientation.Horizontal)
        self.animation_slider.setRange(0, 100)
        self.animation_slider.setValue(0)
        
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.animation_slider, 1)
        
        layout.addLayout(controls_layout)
        
        # Add the tab
        self.view_tabs.addTab(ts_tab, "Time Series")
    
    def showImage(self, image_path: Path) -> None:
        """Display an image."""
        self.view_tabs.setCurrentIndex(0)  # Switch to single view tab
        
        if not image_path or not Path(image_path).exists():
            self.image_label.setText("Image not found")
            return
        
        # Load and display the image
        pixmap = QPixmap(str(image_path))
        
        # Apply zoom if needed
        zoom = self.zoom_slider.value() / 100.0
        if zoom != 1.0:
            width = int(pixmap.width() * zoom)
            height = int(pixmap.height() * zoom)
            pixmap = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
        
        self.image_label.setPixmap(pixmap)
        
        # Update status
        file_size = os.path.getsize(image_path) / 1024  # KB
        self.status_label.setText(f"Loaded: {Path(image_path).name} ({file_size:.1f} KB)")
    
    def showComparison(self, left_path: Path, right_path: Path, left_label: Optional[Any] = None, right_label: Optional[Any] = None) -> None:
        """Display side-by-side comparison."""
        self.view_tabs.setCurrentIndex(1)  # Switch to comparison tab
        
        # Left image
        if left_path and Path(left_path).exists():
            left_pixmap = QPixmap(str(left_path))
            self.left_image.setPixmap(left_pixmap)
            if left_label:
                # TODO: Add label overlay
                pass
        else:
            self.left_image.setText("Image not found")
        
        # Right image
        if right_path and Path(right_path).exists():
            right_pixmap = QPixmap(str(right_path))
            self.right_image.setPixmap(right_pixmap)
            if right_label:
                # TODO: Add label overlay
                pass
        else:
            self.right_image.setText("Image not found")
        
        # Update status
        self.status_label.setText("Comparison view loaded")
    
    def showLoading(self, message: str = "Loading imagery...") -> None:
        """Show loading message."""
        self.image_label.clear()
        self.image_label.setText(message)
        self.status_label.setText(message)
    
    def setProgress(self, value: Any, max_value: int = 100) -> None:
        """Update progress bar."""
        self.progress.setVisible(True)
        self.progress.setMaximum(max_value)
        self.progress.setValue(value)
    
    def hideProgress(self) -> None:
        """Hide progress bar."""
        self.progress.setVisible(False)
    
    def saveImage(self) -> None:
        """Save the current image to a file."""
        # Currently displayed pixmap
        pixmap = self.image_label.pixmap()
        if not pixmap or pixmap.isNull():
            QMessageBox.warning(self, "Save Error", "No image to save")
            return
        
        # Get save file path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Save the image
        if pixmap.save(file_path):
            self.status_label.setText(f"Image saved to: {file_path}")
        else:
            QMessageBox.warning(self, "Save Error", "Failed to save image")
    
    def clearView(self) -> None:
        """Clear all views."""
        self.image_label.clear()
        self.image_label.setText("No imagery loaded")
        self.left_image.clear()
        self.left_image.setText("Image 1")
        self.right_image.clear()
        self.right_image.setText("Image 2")
        self.animation_label.clear()
        self.animation_label.setText("No animation loaded")
        self.status_label.setText("Ready")
        self.hideProgress()


class EnhancedGOESImageryTab(QWidget):
    """Enhanced tab for viewing GOES satellite imagery with additional features."""

    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._apply_stylesheet()
        self.initUI()
        self.initManagers()

    def _apply_stylesheet(self) -> None:
        """Apply dedicated stylesheet for better visibility in dark theme."""
        self.setStyleSheet("""
            /* Panel styling for better visibility */
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                background-color: #2a2a2a;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 5px;
                color: #e0e0e0;
            }

            /* Enhanced Selection panel with better visual distinction */
            QPushButton.channel-button {
                background-color: #252525;
                color: #e0e0e0;
                padding: 4px;  /* Reduced padding */
                border: 1px solid #3c3c3c;
                border-radius: 4px;  /* Smaller radius */
                min-height: 28px;  /* Reduced height */
                text-align: center;
                /* Add gradient background for depth */
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d2d2d, stop:1 #222222);
                /* Add slight shadow effect */
                margin: 2px 2px;  /* Reduced margins */
                /* Better text display for multiline content */
                line-height: 120%;  /* Tighter line spacing */
                font-size: 11pt;
            }

            QPushButton.channel-button:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3a3a, stop:1 #303030);
                border: 1px solid #5a5a5a;
                /* Add glow effect */
                color: white;
            }

            QPushButton.channel-button:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2b5d8e, stop:1 #1d4878);
                border: 2px solid #4a8cce;
                color: white;
                font-weight: bold;
                /* Add subtle shadow for selected state */
                padding: 5px; /* Adjust for thicker border */
            }

            /* Label enhancements */
            QLabel.channel-name {
                font-weight: bold;
                color: #e0e0e0;
            }

            QLabel.channel-info {
                color: #b0b0b0;
                font-size: 10pt;
            }

            /* Enhanced Tab styling with stronger visual identity */
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2a2a2a;
                border-radius: 3px;
            }

            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #333333, stop:1 #272727);
                color: #b0b0b0;
                border: 1px solid #444;
                border-bottom-color: #444;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                min-width: 90px;
                font-weight: normal;
                margin-right: 2px; /* Space between tabs */
            }

            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a6ea5, stop:1 #2b5d8e);
                color: white;
                border: 1px solid #4a8cce;
                border-bottom: none; /* Hide bottom border on selected tab */
                font-weight: bold;
                padding-top: 7px; /* Make selected tab appear slightly taller */
            }

            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d3d3d, stop:1 #333333);
                color: white;
                border-color: #555;
            }
        """)
    
    def initUI(self) -> None:
        """Initialize the UI components with optimized vertical space."""
        # Main splitter layout
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Control panel (left side) - with scroll area for better space usage
        self.selection_panel = EnhancedImageSelectionPanel()

        # Wrap selection panel in highly optimized scroll area to maximize vertical space utilization
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.selection_panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Set vertical scroll bar policy to show only when needed
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Make the scroll area more compact by removing any padding/margins
        scroll_area.setContentsMargins(0, 0, 0, 0)
        # Set the scroll area to have a width that ensures tabs are fully visible
        scroll_area.setMinimumWidth(350)  # Increased for better tab visibility
        scroll_area.setMaximumWidth(450)  # Increased to allow enough space for all tabs
        # We want the scroll area to take as little horizontal space as needed
        scroll_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # Image view panel (right side)
        self.view_panel = EnhancedImageViewPanel()

        # Add to splitter
        self.main_splitter.addWidget(scroll_area)
        self.main_splitter.addWidget(self.view_panel)

        # Set relative sizes (4:6 ratio) to give more space to the controls/tabs
        self.main_splitter.setSizes([400, 600])
        # Make splitter handle more compact but visually distinct
        self.main_splitter.setHandleWidth(5)
        # Style the splitter handle to be more visible
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #444;
                border: 1px solid #555;
                border-width: 0 1px;
            }
            QSplitter::handle:hover {
                background-color: #3498db;  /* Highlight on hover */
            }
        """)

        # Main layout with minimal margins
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.main_splitter)
        
        # Connect signals
        self.selection_panel.imageRequested.connect(self.handleImageRequest)
        self.selection_panel.previewRequested.connect(self.handlePreviewRequest)
    
    def initManagers(self) -> None:
        """Initialize the necessary managers."""
        # Create visualization manager
        self.viz_manager = VisualizationManager(
            base_dir=Path.home() / "Downloads" / "goes_imagery",
            satellite="G16"
        )
        
        # Create sample processor
        self.sample_processor = SampleProcessor(
            visualization_manager=self.viz_manager,
            satellite="G16"
        )
        
        # Create imagery manager (uses different path)
        self.imagery_manager = GOESImageryManager()
    
    def handlePreviewRequest(self, request: Any) -> None:
        """Handle request for image preview."""
        # Show loading state
        self.view_panel.showLoading("Preparing preview...")
        
        # Create preview dialog
        preview_dialog = SamplePreviewDialog(self.sample_processor, request, self)
        preview_dialog.processingConfirmed.connect(self.handleImageRequest)
        
        # Show the dialog (non-modal)
        preview_dialog.setModal(False)
        preview_dialog.show()
    
    def handleImageRequest(self, request: Any) -> None:
        """Handle request for image processing."""
        # Show loading state
        self.view_panel.showLoading(f"Processing {ExtendedChannelType.get_display_name(request['channel'])}...")
        
        # Start a timer to simulate processing steps
        self.processing_start = time.time()
        self.processing_request = request
        self.processing_timer = QTimer(self)
        self.processing_timer.timeout.connect(self.updateProcessingProgress)
        self.processing_timer.start(250)  # Update every 250ms
        
        # Estimate total processing time
        channel = request.get('channel', 13)
        product = request.get('product_type', ProductType.FULL_DISK)
        
        full_res = request.get('resolution') == 'full' if 'resolution' in request else False
        self.processing_total = self.sample_processor.get_estimated_processing_time(
            channel, product, full_res
        )
        
        # Use a timer to simulate processing
        QTimer.singleShot(int(self.processing_total * 1000), 
                         lambda: self.finalizeImageProcessing(request))
    
    def updateProcessingProgress(self) -> None:
        """Update the processing progress display."""
        elapsed = time.time() - self.processing_start
        progress = min(95, int(100 * elapsed / self.processing_total))
        
        channel_name = ExtendedChannelType.get_display_name(self.processing_request['channel'])
        
        if progress < 25:
            message = f"Downloading {channel_name} data..."
        elif progress < 50:
            message = f"Processing {channel_name} data..."
        elif progress < 75:
            message = "Applying enhancements..."
        else:
            message = "Finalizing image..."
        
        self.view_panel.status_label.setText(message)
        self.view_panel.setProgress(progress)
    
    def finalizeImageProcessing(self, request: Any) -> None:
        """Finalize the image processing simulation."""
        try:
            # Stop the progress timer
            if hasattr(self, 'processing_timer') and self.processing_timer.isActive():
                self.processing_timer.stop()
            
            # Get sample image path (for demonstration)
            # In a real implementation, this would be the actual processed image
            channel = request['channel']
            
            # For simplicity, we'll just use the existing visualized images
            visualized_dir = Path.home() / "Downloads" / "goes_channels" / "visualized"
            
            if isinstance(channel, int):
                channel_num = channel
            else:
                channel_num = channel.number
                
            # Choose an appropriate sample image based on channel
            if channel_num <= 16:
                # Regular ABI bands
                if channel_num <= 6:
                    # Visible and near-IR
                    sample_path = visualized_dir / f"band_{channel_num:02d}_vis.png"
                else:
                    # IR bands
                    colorized = request.get('image_type') == 'enhanced'
                    if colorized:
                        sample_path = visualized_dir / f"band_{channel_num:02d}_color.png"
                    else:
                        sample_path = visualized_dir / f"band_{channel_num:02d}_ir.png"
            else:
                # RGB composites
                if channel_num == 100:  # True color
                    sample_path = visualized_dir / "derived_products" / "true_color.png"
                elif channel_num == 103:  # Airmass
                    sample_path = Path.home() / "Downloads" / "goes_channels" / "rgb_composites" / "airmass_rgb.png"
                elif channel_num == 104:  # Fire RGB
                    sample_path = Path.home() / "Downloads" / "goes_channels" / "rgb_composites" / "fire_temperature_rgb.png"
                elif channel_num == 105:  # Day Cloud Phase
                    sample_path = Path.home() / "Downloads" / "goes_channels" / "rgb_composites" / "day_cloud_phase_rgb.png"
                elif channel_num == 106:  # Dust RGB
                    sample_path = Path.home() / "Downloads" / "goes_channels" / "rgb_composites" / "dust_rgb.png"
                else:
                    # Default to natural color for other composites
                    sample_path = Path.home() / "Downloads" / "goes_channels" / "rgb_composites" / "natural_color_rgb.png"
            
            # Display the image
            if sample_path.exists():
                # Update progress for final loading
                self.view_panel.setProgress(100)
                
                # Display the image
                self.view_panel.showImage(sample_path)
                
                # Success message
                channel_name = ExtendedChannelType.get_display_name(channel)
                self.view_panel.status_label.setText(
                    f"{channel_name} image processed successfully"
                )
            else:
                self.view_panel.image_label.setText("Image processing failed")
                self.view_panel.status_label.setText("Failed to process image")
            
            # Hide progress after short delay
            QTimer.singleShot(1000, self.view_panel.hideProgress)
            
        except Exception as e:
            logger.error(f"Error finalizing image processing: {e}")
            self.view_panel.image_label.setText(f"Error: {str(e)}")
            self.view_panel.status_label.setText("Failed to process image")
            self.view_panel.hideProgress()


# Example usage if run directly
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    window.setWindowTitle("Enhanced GOES Imagery Tab Demo")
    window.setGeometry(100, 100, 1200, 800)
    
    layout = QVBoxLayout(window)
    tab = EnhancedGOESImageryTab()
    layout.addWidget(tab)
    
    window.show()
    sys.exit(app.exec())