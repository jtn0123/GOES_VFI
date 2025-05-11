"""
Shared UI Components for GOES Imagery and Integrity Check Tabs

This module provides shared components that can be used by both the GOES Imagery
and Integrity Check tabs for improved integration and user experience.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TypeVar, Union, cast

from PyQt6.QtCore import QDate, QRect, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

# Configure logging
logger = logging.getLogger(__name__)


class PreviewMetadata:
    """Class to store metadata for preview images"""

    def __init__(
        self,
        channel: Union[int, str],
        product_type: Any,
        date_time: datetime,
        source: str,
        data_path: Optional[Path] = None,
        processing_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize preview metadata.

        Args:
            channel: Channel number or identifier
            product_type: Product type (Full Disk, Mesoscale, etc.)
            date_time: Date and time of the imagery
            source: Source of the preview (S3, NOAA CDN, etc.)
            data_path: Optional path to the raw data file
            processing_options: Optional dictionary of processing options
        """
        self.channel = channel
        self.product_type = product_type
        self.date_time = date_time
        self.source = source
        self.data_path = data_path
        self.processing_options = processing_options or {}
        self.creation_time = datetime.now()

    def get_key(self) -> str:
        """
        Generate a unique key for this preview metadata.

        Returns:
            String key in format "channel_product_YYYYMMDD_HHMMSS"
        """
        date_str = self.date_time.strftime("%Y%m%d_%H%M%S")
        return f"{self.channel}_{self.product_type}_{date_str}"

    def get_display_name(self) -> str:
        """
        Get a human-readable display name for this preview.

        Returns:
            Display name string
        """
        date_str = self.date_time.strftime("%Y-%m-%d %H:%M")

        # Handle different channel types
        if isinstance(self.channel, int):
            if self.channel <= 16:
                channel_name = f"Band {self.channel}"
            elif self.channel == 100:
                channel_name = "True Color"
            elif self.channel == 103:
                channel_name = "Airmass RGB"
            elif self.channel == 104:
                channel_name = "Fire RGB"
            else:
                channel_name = f"Channel {self.channel}"
        else:
            channel_name = str(self.channel)

        # Format product type
        if hasattr(self.product_type, "name"):
            product_name = self.product_type.name.replace("_", " ")
        else:
            product_name = str(self.product_type)

        return f"{channel_name} - {product_name} - {date_str}"


class SharedPreviewPanel(QWidget):
    """
    Shared preview panel component for displaying and caching imagery previews.

    This panel provides a unified interface for previewing GOES satellite imagery
    across different tabs, with caching to prevent duplicated downloads.
    """

    # Custom signals
    previewAvailable = pyqtSignal(str, object)  # Key, metadata
    previewSelected = pyqtSignal(str, object)  # Key, metadata
    previewUpdated = pyqtSignal(str)  # Key
    previewRemoved = pyqtSignal(str)  # Key
    previewBookmarked = pyqtSignal(str, bool)  # Key, is_bookmarked

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the shared preview panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.preview_cache: Dict[
            str, Dict[str, Any]
        ] = {}  # Key -> {'image': QPixmap, 'metadata': PreviewMetadata}
        self.bookmarks: Set[str] = set()  # Set of bookmarked preview keys
        self.current_key: Optional[str] = None  # Currently displayed preview key

        self.initUI()

    def initUI(self) -> None:
        """Initialize the UI components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Preview display area
        self.preview_frame = QFrame()
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setMinimumSize(600, 400)

        preview_layout = QVBoxLayout(self.preview_frame)

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #202020;")
        self.image_label.setText(self.tr("No preview available"))

        # Add to scroll area for large images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_label)

        preview_layout.addWidget(scroll)

        # Preview info panel
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setMaximumHeight(100)
        info_layout = QGridLayout(info_frame)

        # Labels for metadata
        self.info_channel = QLabel(self.tr("Channel: -"))
        self.info_product = QLabel(self.tr("Product: -"))
        self.info_datetime = QLabel(self.tr("Date/Time: -"))
        self.info_source = QLabel(self.tr("Source: -"))

        # Info layout
        info_layout.addWidget(QLabel(self.tr("Preview Information:")), 0, 0, 1, 2)
        info_layout.addWidget(self.info_channel, 1, 0)
        info_layout.addWidget(self.info_product, 1, 1)
        info_layout.addWidget(self.info_datetime, 2, 0)
        info_layout.addWidget(self.info_source, 2, 1)

        # Action buttons
        action_layout = QHBoxLayout()

        self.bookmark_btn = QPushButton(self.tr("Bookmark"))
        self.bookmark_btn.setCheckable(True)
        self.bookmark_btn.clicked.connect(self.toggleBookmark)

        self.process_btn = QPushButton(self.tr("Process Full Image"))

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.valueChanged.connect(self.updateZoom)

        action_layout.addWidget(QLabel(self.tr("Zoom:")))
        action_layout.addWidget(self.zoom_slider)
        action_layout.addWidget(self.bookmark_btn)
        action_layout.addWidget(self.process_btn)

        # Add components to layout
        layout.addWidget(self.preview_frame)
        layout.addWidget(info_frame)
        layout.addLayout(action_layout)

    def addPreview(
        self, key: str, image: QPixmap, metadata: PreviewMetadata, select: bool = True
    ) -> None:
        """
        Add a preview image to the cache.

        Args:
            key: Unique key for the preview
            image: Preview image as QPixmap
            metadata: Metadata for the preview
            select: Whether to select this preview immediately
        """
        self.preview_cache[key] = {"image": image, "metadata": metadata}

        # Emit signal that a new preview is available
        self.previewAvailable.emit(key, metadata)

        # Select the preview if requested
        if select:
            self.selectPreview(key)

        logger.info(f"Added preview to cache: {key}")

    def selectPreview(self, key: str) -> None:
        """
        Select and display a specific preview.

        Args:
            key: Key of the preview to select
        """
        if key not in self.preview_cache:
            logger.warning(f"Cannot select preview, key not found: {key}")
            return

        # Update current key
        self.current_key = key

        # Get preview data
        preview_data = self.preview_cache[key]
        image = preview_data["image"]
        metadata = preview_data["metadata"]

        # Display image
        self.image_label.setPixmap(image)

        # Update info panel
        self.info_channel.setText(f"Channel: {metadata.channel}")

        if hasattr(metadata.product_type, "name"):
            product_name = metadata.product_type.name.replace("_", " ")
        else:
            product_name = str(metadata.product_type)
        self.info_product.setText(f"Product: {product_name}")

        date_str = metadata.date_time.strftime("%Y-%m-%d %H:%M UTC")
        self.info_datetime.setText(f"Date/Time: {date_str}")

        self.info_source.setText(f"Source: {metadata.source}")

        # Update bookmark button state
        self.bookmark_btn.setChecked(key in self.bookmarks)

        # Emit signal
        self.previewSelected.emit(key, metadata)

        logger.info(f"Selected preview: {key}")

    def getPreview(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific preview from the cache.

        Args:
            key: Key of the preview to get

        Returns:
            Dictionary with 'image' and 'metadata' or None if not found
        """
        return self.preview_cache.get(key)

    def getCurrentPreview(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently selected preview.

        Returns:
            Dictionary with 'image' and 'metadata' or None if no preview selected
        """
        if self.current_key is None:
            return None

        return self.preview_cache.get(self.current_key)

    def clearPreviews(self) -> None:
        """Clear all non-bookmarked previews from the cache."""
        # Keep only bookmarked previews
        keys_to_remove = [
            key for key in self.preview_cache if key not in self.bookmarks
        ]

        for key in keys_to_remove:
            del self.preview_cache[key]
            self.previewRemoved.emit(key)

        # Reset current preview if it was removed
        if self.current_key and self.current_key not in self.preview_cache:
            self.current_key = None
            self.image_label.clear()
            self.image_label.setText(self.tr("No preview available"))
            self.info_channel.setText(self.tr("Channel: -"))
            self.info_product.setText(self.tr("Product: -"))
            self.info_datetime.setText(self.tr("Date/Time: -"))
            self.info_source.setText(self.tr("Source: -"))

        logger.info(f"Cleared {len(keys_to_remove)} non-bookmarked previews")

    def removePreview(self, key: str) -> None:
        """
        Remove a specific preview from the cache.

        Args:
            key: Key of the preview to remove
        """
        if key in self.preview_cache:
            del self.preview_cache[key]

            # Remove from bookmarks if present
            if key in self.bookmarks:
                self.bookmarks.remove(key)

            # Reset current preview if it was the one removed
            if self.current_key == key:
                self.current_key = None
                self.image_label.clear()
                self.image_label.setText(self.tr("No preview available"))
                self.info_channel.setText(self.tr("Channel: -"))
                self.info_product.setText(self.tr("Product: -"))
                self.info_datetime.setText(self.tr("Date/Time: -"))
                self.info_source.setText(self.tr("Source: -"))

            # Emit signal
            self.previewRemoved.emit(key)

            logger.info(f"Removed preview: {key}")

    def updateZoom(self) -> None:
        """Update the zoom level of the current preview."""
        if self.current_key is None or self.current_key not in self.preview_cache:
            return

        # Get original image
        preview_data = self.preview_cache[self.current_key]
        original = preview_data["image"]

        # Apply zoom
        zoom = self.zoom_slider.value() / 100.0
        if zoom != 1.0:
            width = int(original.width() * zoom)
            height = int(original.height() * zoom)
            scaled = original.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setPixmap(original)

    def toggleBookmark(self, checked: bool) -> None:
        """
        Toggle bookmark status for the current preview.

        Args:
            checked: New bookmark state
        """
        if self.current_key is None:
            return

        if checked:
            self.bookmarks.add(self.current_key)
        elif self.current_key in self.bookmarks:
            self.bookmarks.remove(self.current_key)

        # Emit signal
        self.previewBookmarked.emit(self.current_key, checked)

        logger.info(f"Preview {self.current_key} bookmark set to {checked}")

    def getBookmarkedPreviews(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all bookmarked previews.

        Returns:
            Dictionary of key -> preview data for all bookmarked previews
        """
        return {
            key: self.preview_cache[key]
            for key in self.bookmarks
            if key in self.preview_cache
        }

    def createFallbackPreview(
        self,
        channel: Union[int, str],
        product_type: Any,
        date_time: datetime,
        error_msg: str,
    ) -> Tuple[QPixmap, PreviewMetadata]:
        """
        Create a fallback preview image with error information.

        Args:
            channel: Channel number or identifier
            product_type: Product type
            date_time: Date and time of the imagery
            error_msg: Error message to display

        Returns:
            Tuple of (QPixmap, PreviewMetadata)
        """
        # Create a fallback preview image with text and visual indicators
        width, height = 600, 350
        pix = QPixmap(width, height)
        pix.fill(QColor(40, 40, 40))

        # Add text explanation
        painter = QPainter(pix)

        # Create a better title bar
        painter.fillRect(0, 0, width, 30, QColor(25, 52, 152))  # Dark blue
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))

        # Determine channel info
        if isinstance(channel, int):
            if channel <= 16:
                channel_name = f"Band {channel}"
            elif channel == 100:
                channel_name = "True Color"
            elif channel == 103:
                channel_name = "Airmass RGB"
            else:
                channel_name = f"Channel {channel}"
        else:
            channel_name = str(channel)

        # Format product type
        if hasattr(product_type, "name"):
            product_name = product_type.name.replace("_", " ")
        else:
            product_name = str(product_type)

        # Draw title
        title_text = f"Preview: {channel_name} ({product_name})"
        painter.drawText(20, 22, title_text)

        # Draw status banner
        status_rect = QRect(0, 40, width, 25)
        painter.fillRect(status_rect, QColor(180, 32, 32))  # Dark red
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(
            status_rect, Qt.AlignmentFlag.AlignCenter, "STATUS: PREVIEW UNAVAILABLE"
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

        # Draw content in a more compact layout
        painter.setFont(QFont("Arial", 10))
        y = 80  # Start text closer to status bar

        # Issue details
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(20, y, f"Issue: {primary_reason}")
        y += 25

        # Parameters
        painter.setFont(QFont("Arial", 10))
        painter.drawText(20, y, f"Channel: {channel_name} | Product: {product_name}")
        y += 20
        painter.drawText(
            20, y, f"Date/Time: {date_time.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        y += 25

        # Recommendation
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(20, y, "Recommendation:")
        y += 20
        painter.setFont(QFont("Arial", 10))
        painter.drawText(35, y, suggestion)
        y += 25

        # Technical details
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        painter.drawText(20, y, "Technical details:")
        y += 20
        painter.setFont(QFont("Arial", 10))

        # Split error message if too long
        max_chars = 70
        error_words = error_msg.split()
        error_lines = []
        current_line = ""

        for word in error_words:
            if len(current_line + " " + word) <= max_chars:
                current_line += " " + word if current_line else word
            else:
                error_lines.append(current_line)
                current_line = word

        if current_line:
            error_lines.append(current_line)

        for line in error_lines:
            painter.drawText(35, y, line)
            y += 20

        # Help text
        y += 5
        painter.setPen(QColor(100, 200, 255))
        painter.drawText(
            20,
            y,
            "You can still proceed with processing using fallback imagery samples.",
        )

        # Finish painting
        painter.end()

        # Create metadata for the fallback preview
        metadata = PreviewMetadata(
            channel=channel,
            product_type=product_type,
            date_time=date_time,
            source="Fallback",
            processing_options={"error": error_msg},
        )

        return pix, metadata


class CollapsibleSettingsGroup(QWidget):
    """
    Collapsible settings group with toggle header.

    This widget provides a collapsible container for settings with a header that can
    be clicked to expand or collapse the content.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the collapsible settings group.

        Args:
            title: Title to display in the header
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Create layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create header
        self.header = QWidget()
        self.header.setMinimumHeight(30)
        self.header.setMaximumHeight(30)
        self.header.setStyleSheet(
            """
            background-color: #404040;
            border-top: 1px solid #505050;
            border-bottom: 1px solid #505050;
        """
        )

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(5, 0, 5, 0)

        self.toggle_btn = QPushButton(self.tr("▼"))
        self.toggle_btn.setFixedWidth(20)
        self.toggle_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
            }
        """
        )
        self.toggle_btn.clicked.connect(self.toggle_content)

        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Create content container
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(15, 5, 5, 5)

        # Add to main layout
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.content)

        # Initial state
        self.expanded = True

    def toggle_content(self) -> None:
        """Toggle content visibility."""
        self.expanded = not self.expanded
        self.content.setVisible(self.expanded)
        self.toggle_btn.setText(self.tr("▼" if self.expanded else "▶"))

    def addWidget(self, widget: QWidget) -> None:
        """
        Add a widget to the content area.

        Args:
            widget: Widget to add
        """
        self.content_layout.addWidget(widget)

    def addLayout(self, layout: QLayout) -> None:
        """
        Add a layout to the content area.

        Args:
            layout: Layout to add
        """
        self.content_layout.addLayout(layout)


class SidebarSettingsPanel(QWidget):
    """
    Sidebar panel for settings with collapsible sections.

    This widget provides a vertically-oriented sidebar for settings, with
    collapsible sections for different categories of settings.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the sidebar settings panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Set fixed width for the sidebar
        self.setMinimumWidth(280)
        self.setMaximumWidth(300)

        # Set styling
        self.setStyleSheet(
            """
            background-color: #2a2a2a;
            border-left: 1px solid #404040;
        """
        )

        # Create scrollable layout
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        # Title section
        title_widget = QWidget()
        title_widget.setStyleSheet("background-color: #303030;")
        title_layout = QVBoxLayout(title_widget)

        title_label = QLabel(self.tr("Settings"))
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(title_label)

        # Add to layout
        self.container_layout.addWidget(title_widget)

        # Presets section
        self.presets_group = CollapsibleSettingsGroup("Quick Actions")
        self.create_presets_section(self.presets_group)
        self.container_layout.addWidget(self.presets_group)

        # Data section (date/time, product, etc.)
        self.data_group = CollapsibleSettingsGroup("Data Selection")
        self.create_data_section(self.data_group)
        self.container_layout.addWidget(self.data_group)

        # Visualization section
        self.viz_group = CollapsibleSettingsGroup("Visualization")
        self.create_visualization_section(self.viz_group)
        self.container_layout.addWidget(self.viz_group)

        # Processing section
        self.processing_group = CollapsibleSettingsGroup("Processing")
        self.create_processing_section(self.processing_group)
        self.container_layout.addWidget(self.processing_group)

        # Advanced section
        self.advanced_group = CollapsibleSettingsGroup("Advanced")
        self.create_advanced_section(self.advanced_group)
        self.container_layout.addWidget(self.advanced_group)

        # Add spacer at the bottom
        self.container_layout.addStretch()

        # Set scroll area widget
        self.scroll_area.setWidget(self.container)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll_area)

    def create_presets_section(self, group: CollapsibleSettingsGroup) -> None:
        """
        Create the presets section with quick action buttons.

        Args:
            group: CollapsibleSettingsGroup to add the content to
        """
        presets_layout = QVBoxLayout()
        presets_layout.setContentsMargins(0, 0, 0, 0)

        # Quick action buttons
        quick_preview_btn = QPushButton(self.tr("Quick Preview"))
        quick_preview_btn.setIcon(QIcon.fromTheme("view-preview"))

        full_res_btn = QPushButton(self.tr("Full Resolution"))

        multi_channel_btn = QPushButton(self.tr("Multi-Channel"))

        # Add to layout
        presets_layout.addWidget(quick_preview_btn)
        presets_layout.addWidget(full_res_btn)
        presets_layout.addWidget(multi_channel_btn)

        group.addLayout(presets_layout)

    def create_data_section(self, group: CollapsibleSettingsGroup) -> None:
        """
        Create the data selection section (date/time, product, etc.).

        Args:
            group: CollapsibleSettingsGroup to add the content to
        """
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(0, 5, 0, 5)

        # Add date control
        date_label = QLabel(self.tr("Date:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")

        date_layout = QHBoxLayout()
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_edit)

        # Add time control
        time_label = QLabel(self.tr("Time:"))
        self.time_edit = QTimeEdit(QTime.currentTime())
        self.time_edit.setDisplayFormat("HH:mm")

        time_layout = QHBoxLayout()
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_edit)

        # Add satellite selector
        satellite_label = QLabel(self.tr("Satellite:"))
        self.satellite_combo = QComboBox()
        self.satellite_combo.addItem(self.tr("GOES-16 (East)"))
        self.satellite_combo.addItem(self.tr("GOES-18 (West)"))

        satellite_layout = QHBoxLayout()
        satellite_layout.addWidget(satellite_label)
        satellite_layout.addWidget(self.satellite_combo)

        # Add product type selector
        product_label = QLabel(self.tr("Product Type:"))
        self.product_combo = QComboBox()
        self.product_combo.addItem(self.tr("Full Disk"))
        self.product_combo.addItem(self.tr("CONUS"))
        self.product_combo.addItem(self.tr("Mesoscale 1"))
        self.product_combo.addItem(self.tr("Mesoscale 2"))

        product_layout = QHBoxLayout()
        product_layout.addWidget(product_label)
        product_layout.addWidget(self.product_combo)

        # Add to the main layout
        data_layout.addLayout(date_layout)
        data_layout.addLayout(time_layout)
        data_layout.addLayout(satellite_layout)
        data_layout.addLayout(product_layout)
        data_layout.addStretch()

        group.addLayout(data_layout)

    def create_visualization_section(self, group: CollapsibleSettingsGroup) -> None:
        """
        Create the visualization section.

        Args:
            group: CollapsibleSettingsGroup to add the content to
        """
        viz_layout = QVBoxLayout()
        viz_layout.setContentsMargins(0, 5, 0, 5)

        # Channel tabs for better organization
        channel_tabs = QTabWidget()
        channel_tabs.setStyleSheet(
            """
            QTabBar::tab {
                padding: 4px 8px;
            }
        """
        )

        # Create IR tab
        ir_tab = QWidget()
        ir_layout = QVBoxLayout(ir_tab)
        ir_layout.setContentsMargins(5, 5, 5, 5)

        # IR channel buttons
        ir_group = QButtonGroup()

        ch13_btn = QRadioButton("Clean IR (13)")
        ch13_btn.setChecked(True)
        ir_group.addButton(ch13_btn)

        ch14_btn = QRadioButton("Longwave IR (14)")
        ir_group.addButton(ch14_btn)

        ch15_btn = QRadioButton("'Dirty' IR (15)")
        ir_group.addButton(ch15_btn)

        ir_layout.addWidget(ch13_btn)
        ir_layout.addWidget(ch14_btn)
        ir_layout.addWidget(ch15_btn)
        ir_layout.addStretch()

        # Create WV tab
        wv_tab = QWidget()
        wv_layout = QVBoxLayout(wv_tab)
        wv_layout.setContentsMargins(5, 5, 5, 5)

        # Water vapor channel buttons
        wv_group = QButtonGroup()

        ch08_btn = QRadioButton("Upper-Level WV (8)")
        wv_group.addButton(ch08_btn)

        ch09_btn = QRadioButton("Mid-Level WV (9)")
        wv_group.addButton(ch09_btn)

        ch10_btn = QRadioButton("Lower-Level WV (10)")
        wv_group.addButton(ch10_btn)

        wv_layout.addWidget(ch08_btn)
        wv_layout.addWidget(ch09_btn)
        wv_layout.addWidget(ch10_btn)
        wv_layout.addStretch()

        # Create RGB tab
        rgb_tab = QWidget()
        rgb_layout = QVBoxLayout(rgb_tab)
        rgb_layout.setContentsMargins(5, 5, 5, 5)

        # RGB composite buttons
        rgb_group = QButtonGroup()

        true_color_btn = QRadioButton("True Color")
        rgb_group.addButton(true_color_btn)

        airmass_btn = QRadioButton("Airmass RGB")
        rgb_group.addButton(airmass_btn)

        fire_btn = QRadioButton("Fire Temperature")
        rgb_group.addButton(fire_btn)

        rgb_layout.addWidget(true_color_btn)
        rgb_layout.addWidget(airmass_btn)
        rgb_layout.addWidget(fire_btn)
        rgb_layout.addStretch()

        # Add tabs
        channel_tabs.addTab(ir_tab, "IR")
        channel_tabs.addTab(wv_tab, "WV")
        channel_tabs.addTab(rgb_tab, "RGB")

        # Add enhancement options
        enhancement_label = QLabel(self.tr("Enhancement:"))
        self.enhancement_combo = QComboBox()
        self.enhancement_combo.addItem(self.tr("Standard (Grayscale)"))
        self.enhancement_combo.addItem(self.tr("Enhanced (Colorized)"))

        enhancement_layout = QHBoxLayout()
        enhancement_layout.addWidget(enhancement_label)
        enhancement_layout.addWidget(self.enhancement_combo)

        # Add to the main layout
        viz_layout.addWidget(channel_tabs)
        viz_layout.addLayout(enhancement_layout)

        group.addLayout(viz_layout)

    def create_processing_section(self, group: CollapsibleSettingsGroup) -> None:
        """
        Create the processing section.

        Args:
            group: CollapsibleSettingsGroup to add the content to
        """
        proc_layout = QVBoxLayout()
        proc_layout.setContentsMargins(0, 5, 0, 5)

        # Resolution options
        resolution_label = QLabel(self.tr("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItem(self.tr("Full Resolution"))
        self.resolution_combo.addItem(self.tr("Medium (Faster)"))
        self.resolution_combo.addItem(self.tr("Low (Fastest)"))

        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(resolution_label)
        resolution_layout.addWidget(self.resolution_combo)

        # Output format
        format_label = QLabel(self.tr("Output Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem(self.tr("PNG"))
        self.format_combo.addItem(self.tr("JPEG"))
        self.format_combo.addItem(self.tr("TIFF"))

        format_layout = QHBoxLayout()
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)

        # Add options
        self.preview_check = QCheckBox(self.tr("Preview before processing"))
        self.preview_check.setChecked(True)

        self.cache_check = QCheckBox(self.tr("Cache downloaded data"))
        self.cache_check.setChecked(True)

        # Add to the main layout
        proc_layout.addLayout(resolution_layout)
        proc_layout.addLayout(format_layout)
        proc_layout.addWidget(self.preview_check)
        proc_layout.addWidget(self.cache_check)
        proc_layout.addStretch()

        group.addLayout(proc_layout)

    def create_advanced_section(self, group: CollapsibleSettingsGroup) -> None:
        """
        Create the advanced options section.

        Args:
            group: CollapsibleSettingsGroup to add the content to
        """
        advanced_layout = QVBoxLayout()
        advanced_layout.setContentsMargins(0, 5, 0, 5)

        # Temperature range (for IR channels)
        temp_group = QGroupBox(self.tr("Temperature Range (K)"))
        temp_layout = QHBoxLayout(temp_group)

        self.min_temp_spin = QSpinBox()
        self.min_temp_spin.setRange(180, 310)
        self.min_temp_spin.setValue(200)

        self.max_temp_spin = QSpinBox()
        self.max_temp_spin.setRange(220, 350)
        self.max_temp_spin.setValue(320)

        temp_layout.addWidget(QLabel(self.tr("Min:")))
        temp_layout.addWidget(self.min_temp_spin)
        temp_layout.addWidget(QLabel(self.tr("Max:")))
        temp_layout.addWidget(self.max_temp_spin)

        # Gamma correction (for all channels)
        gamma_group = QGroupBox(self.tr("Gamma Correction"))
        gamma_layout = QHBoxLayout(gamma_group)

        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(50, 150)  # 0.5 to 1.5
        self.gamma_slider.setValue(100)  # 1.0

        self.gamma_label = QLabel(self.tr("1.0"))

        gamma_layout.addWidget(self.gamma_slider)
        gamma_layout.addWidget(self.gamma_label)

        # Connect gamma slider to label update
        self.gamma_slider.valueChanged.connect(
            lambda v: self.gamma_label.setText(f"{v/100:.1f}")
        )

        # Data source options
        source_group = QGroupBox(self.tr("Data Sources"))
        source_layout = QVBoxLayout(source_group)

        self.use_s3_check = QCheckBox(self.tr("Use AWS S3 (Raw Data)"))
        self.use_s3_check.setChecked(True)

        self.use_cdn_check = QCheckBox(self.tr("Use NOAA CDN (Web Images)"))
        self.use_cdn_check.setChecked(True)

        self.use_rammb_check = QCheckBox(self.tr("Use RAMMB Slider (Alternative)"))
        self.use_rammb_check.setChecked(True)

        source_layout.addWidget(self.use_s3_check)
        source_layout.addWidget(self.use_cdn_check)
        source_layout.addWidget(self.use_rammb_check)

        # Add to the main layout
        advanced_layout.addWidget(temp_group)
        advanced_layout.addWidget(gamma_group)
        advanced_layout.addWidget(source_group)
        advanced_layout.addStretch()

        group.addLayout(advanced_layout)

    def get_date_time(self) -> datetime:
        """
        Get the selected date and time.

        Returns:
            datetime object
        """
        date = self.date_edit.date().toPyDate()
        time = self.time_edit.time().toPyTime()
        return datetime.combine(date, time)

    def set_date_time(self, dt: datetime) -> None:
        """
        Set the date and time controls.

        Args:
            dt: datetime to set
        """
        self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        self.time_edit.setTime(QTime(dt.hour, dt.minute))

    def get_satellite(self) -> str:
        """
        Get the selected satellite.

        Returns:
            Satellite identifier ('G16' or 'G18')
        """
        idx = self.satellite_combo.currentIndex()
        return "G16" if idx == 0 else "G18"

    def get_product_type(self) -> str:
        """
        Get the selected product type.

        Returns:
            Product type string
        """
        return self.product_combo.currentText().upper().replace(" ", "_")

    def show_section(self, section_name: str, show: bool = True) -> None:
        """
        Show or hide a specific section.

        Args:
            section_name: Name of the section to show/hide ("presets", "data",
                         "visualization", "processing", or "advanced")
            show: Whether to show (True) or hide (False) the section
        """
        if section_name == "presets":
            self.presets_group.setVisible(show)
        elif section_name == "data":
            self.data_group.setVisible(show)
        elif section_name == "visualization":
            self.viz_group.setVisible(show)
        elif section_name == "processing":
            self.processing_group.setVisible(show)
        elif section_name == "advanced":
            self.advanced_group.setVisible(show)
