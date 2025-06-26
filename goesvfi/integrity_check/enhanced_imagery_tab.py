"""Enhanced GOES Satellite Imagery Tab

This module provides an enhanced version of the GOES Imagery Tab with additional
features for previewing, comparing, and organizing satellite imagery.
"""

from datetime import datetime
from typing import Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class EnhancedGOESImageryTab(QWidget):
    """Enhanced GOES Imagery Tab for satellite image visualization.

    Provides comprehensive satellite imagery display with product selection,
    band comparison, and temporal navigation capabilities.
    """

    # Signals
    imageRequested = pyqtSignal(dict)
    timestampChanged = pyqtSignal(datetime)
    productChanged = pyqtSignal(str)
    bandChanged = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the enhanced imagery tab.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.current_data: List[Any] = []
        self.current_timestamp: Optional[datetime] = None

        # Initialize UI widget attributes to satisfy pylint
        self.product_combo: Optional[QComboBox] = None
        self.satellite_combo: Optional[QComboBox] = None
        self.band_combo: Optional[QComboBox] = None
        self.enhancement_combo: Optional[QComboBox] = None
        self.load_btn: Optional[QPushButton] = None
        self.refresh_btn: Optional[QPushButton] = None
        self.compare_btn: Optional[QPushButton] = None
        self.animate_btn: Optional[QPushButton] = None
        self.image_area: Optional[QScrollArea] = None
        self.info_panel: Optional[QWidget] = None
        self.image_label: Optional[QLabel] = None
        self.info_content: Optional[QLabel] = None
        self.status_label: Optional[QLabel] = None

        self.initUI()
        LOGGER.info("Enhanced GOES Imagery Tab initialized")

    def initUI(self) -> None:
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        self._create_header(layout)

        # Control panel
        self._create_control_panel(layout)

        # Main content area
        self._create_main_content(layout)

        # Status bar
        self._create_status_bar(layout)

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the enhanced header section."""
        header = QLabel("GOES Satellite Imagery Viewer")
        header.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #EFEFEF;
                padding: 15px;
            }
            """
        )
        layout.addWidget(header)

    def _create_control_panel(self, layout: QVBoxLayout) -> None:
        """Create the enhanced control panel."""
        control_frame = QFrame()
        control_frame.setStyleSheet(
            """
            QFrame {
                background-color: #3D3D3D;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 10px;
            }
            QLabel {
                color: #EFEFEF;
                font-weight: bold;
                font-size: 12px;
            }
            QComboBox {
                background-color: #3D3D3D;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                color: #EFEFEF;
                min-width: 140px;
            }
            QComboBox:focus {
                border: 1px solid #6C9BD1;
            }
            QPushButton {
                background-color: #4A4A4A;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 15px;
                color: #EFEFEF;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5A5A;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
            """
        )

        control_layout = QGridLayout(control_frame)
        control_layout.setSpacing(12)

        # Row 1: Product and Satellite selection
        control_layout.addWidget(QLabel("Product:"), 0, 0)
        self.product_combo = QComboBox()
        self.product_combo.addItems(
            [
                "Full Disk (ABI-L2-CMIPF)",
                "CONUS (ABI-L2-CMIPC)",
                "Mesoscale-1 (ABI-L2-CMIPM1)",
                "Mesoscale-2 (ABI-L2-CMIPM2)",
            ]
        )
        self.product_combo.setToolTip("Select GOES-R ABI product type")
        self.product_combo.currentTextChanged.connect(self._on_product_changed)
        control_layout.addWidget(self.product_combo, 0, 1)

        control_layout.addWidget(QLabel("Satellite:"), 0, 2)
        self.satellite_combo = QComboBox()
        self.satellite_combo.addItems(["GOES-16 (East)", "GOES-18 (West)"])
        self.satellite_combo.setToolTip("Select GOES satellite")
        control_layout.addWidget(self.satellite_combo, 0, 3)

        # Row 2: Band and Enhancement selection
        control_layout.addWidget(QLabel("Band/Channel:"), 1, 0)
        self.band_combo = QComboBox()
        self.band_combo.addItems(
            [
                "Band 13 (10.3 μm IR)",
                "Band 14 (11.2 μm IR)",
                "Band 15 (12.3 μm IR)",
                "True Color RGB",
                "Enhanced IR",
                "Sea Surface Temp",
            ]
        )
        self.band_combo.setToolTip("Select spectral band or composite")
        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        control_layout.addWidget(self.band_combo, 1, 1)

        control_layout.addWidget(QLabel("Enhancement:"), 1, 2)
        self.enhancement_combo = QComboBox()
        self.enhancement_combo.addItems(
            [
                "Auto Contrast",
                "Temperature Scale",
                "Rainbow",
                "Grayscale",
                "Linear",
            ]
        )
        self.enhancement_combo.setToolTip("Select color enhancement")
        control_layout.addWidget(self.enhancement_combo, 1, 3)

        # Row 3: Action buttons
        button_layout = QHBoxLayout()

        self.load_btn = QPushButton("Load Image")
        self.load_btn.setToolTip("Load the selected satellite image")
        self.load_btn.clicked.connect(self._load_current_image)
        button_layout.addWidget(self.load_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Refresh available imagery")
        button_layout.addWidget(self.refresh_btn)

        self.compare_btn = QPushButton("Compare")
        self.compare_btn.setToolTip("Compare multiple images side-by-side")
        button_layout.addWidget(self.compare_btn)

        self.animate_btn = QPushButton("Animate")
        self.animate_btn.setToolTip("Create animation from time series")
        button_layout.addWidget(self.animate_btn)

        button_layout.addStretch()
        control_layout.addLayout(button_layout, 2, 0, 1, 4)

        layout.addWidget(control_frame)

    def _create_main_content(self, layout: QVBoxLayout) -> None:
        """Create the main content area with image display."""
        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Image display
        self.image_area = self._create_image_display_area()
        splitter.addWidget(self.image_area)

        # Right side: Info panel
        self.info_panel = self._create_info_panel()
        splitter.addWidget(self.info_panel)

        # Set initial sizes (70% image, 30% info)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

    def _create_image_display_area(self) -> QWidget:
        """Create the image display area."""
        container = QFrame()
        container.setStyleSheet(
            """
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #454545;
                border-radius: 8px;
            }
            """
        )

        layout = QVBoxLayout(container)

        # Image display label
        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            """
            QLabel {
                color: #888888;
                font-size: 16px;
                font-weight: bold;
                min-height: 400px;
                background-color: #222222;
                border: 2px dashed #444444;
                border-radius: 6px;
            }
            """
        )

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)

        return container

    def _create_info_panel(self) -> QWidget:
        """Create the information panel."""
        container = QFrame()
        container.setStyleSheet(
            """
            QFrame {
                background-color: #2d2d2d;
                border: 2px solid #454545;
                border-radius: 8px;
            }
            QLabel {
                color: #f0f0f0;
                font-size: 11px;
            }
            """
        )

        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # Title
        title = QLabel("📊 Image Information")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Info content
        self.info_content = QLabel("📄 Select an image to view details")
        self.info_content.setWordWrap(True)
        self.info_content.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.info_content)

        layout.addStretch()

        return container

    def _create_status_bar(self, layout: QVBoxLayout) -> None:
        """Create the status bar."""
        self.status_label = QLabel("✅ Ready - Select product and band to load imagery")
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #66ff66;
                background-color: #2a2a2a;
                padding: 8px 15px;
                border-radius: 6px;
                border-left: 4px solid #66ff66;
                font-weight: bold;
            }
            """
        )
        layout.addWidget(self.status_label)

    def _on_product_changed(self, product: str) -> None:
        """Handle product selection change."""
        self.productChanged.emit(product)
        self._update_status(f"🔄 Product changed to: {product}")

    def _on_band_changed(self, band: str) -> None:
        """Handle band selection change."""
        self.bandChanged.emit(band)
        self._update_status(f"🌈 Band changed to: {band}")

    def _load_current_image(self) -> None:
        """Load the currently selected image."""
        params = {
            "product": self.product_combo.currentText(),
            "satellite": self.satellite_combo.currentText(),
            "band": self.band_combo.currentText(),
            "enhancement": self.enhancement_combo.currentText(),
            "timestamp": self.current_timestamp,
        }

        self._update_status("🔄 Loading image...")
        self.imageRequested.emit(params)

    def _update_status(self, message: str) -> None:
        """Update the status label with a new message."""
        # Determine color based on message content
        if "error" in message.lower() or "failed" in message.lower():
            color = "#ff6666"
            border_color = "#ff6666"
        elif "loading" in message.lower() or "processing" in message.lower():
            color = "#ffaa66"
            border_color = "#ffaa66"
        elif any(word in message.lower() for word in ["completed", "success", "loaded"]):
            color = "#66ff66"
            border_color = "#66ff66"
        else:
            color = "#66aaff"
            border_color = "#66aaff"

        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background-color: #2a2a2a;
                padding: 8px 15px;
                border-radius: 6px;
                border-left: 4px solid {border_color};
                font-weight: bold;
            }}
            """
        )

    def requestImage(self, params: dict) -> None:
        """Request a satellite image with given parameters.

        Args:
            params: Dictionary of image request parameters
        """
        self._update_status("Processing image request...")
        self.imageRequested.emit(params)

    def loadTimestamp(self, timestamp: Any) -> None:
        """Load imagery for a specific timestamp.

        Args:
            timestamp: Timestamp to load imagery for
        """
        self.current_timestamp = timestamp
        self.timestampChanged.emit(timestamp)
        self._update_info_panel()
        self._update_status(f"Timestamp set to: {timestamp}")

    def set_data(self, items: List[Any], start_date: datetime, end_date: datetime) -> None:
        """Set data for the imagery tab.

        Args:
            items: List of data items
            start_date: Start date of the data range
            end_date: End date of the data range
        """
        self.current_data = items
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        self._update_status(f"Data updated: {len(items)} items from {start_str} to {end_str}")

    def _update_info_panel(self) -> None:
        """Update the information panel with current selection details."""
        if self.current_timestamp:
            info_text = f"""
            <b>Current Timestamp:</b><br>
            {self.current_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}<br><br>

            <b>Product:</b><br>
            {self.product_combo.currentText()}<br><br>

            <b>Satellite:</b><br>
            {self.satellite_combo.currentText()}<br><br>

            <b>Band:</b><br>
            {self.band_combo.currentText()}<br><br>

            <b>Enhancement:</b><br>
            {self.enhancement_combo.currentText()}<br><br>

            <b>📁 Available Data:</b><br>
            {len(self.current_data)} items loaded
            """
        else:
            info_text = "📄 Select a timestamp to view image details"

        self.info_content.setText(info_text)
