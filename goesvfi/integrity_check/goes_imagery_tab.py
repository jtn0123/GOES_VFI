"""GOES Satellite Imagery Tab.

This module extends the Integrity Check tab with satellite imagery capabilities,
providing UI components for selecting and viewing different GOES products.
"""

from PyQt6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class GOESImageryTab(QWidget):
    """Tab for GOES satellite imagery display and analysis."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the GOES imagery tab."""
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Add header
        header = QLabel("GOES Satellite Imagery")
        header.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #EFEFEF;
                padding: 12px 16px;
                margin-bottom: 10px;
            }
            """
        )
        layout.addWidget(header)

        # Create control panel
        from PyQt6.QtWidgets import QFormLayout, QFrame, QHBoxLayout

        control_panel = QFrame()
        control_panel.setProperty("class", "ControlFrame")
        control_layout = QFormLayout(control_panel)
        control_layout.setSpacing(10)

        # Product selection
        product_label = QLabel("Product Type:")
        product_label.setProperty("class", "StandardLabel")
        self.product_combo = QComboBox()
        self.product_combo.addItems(["Full Disk", "CONUS", "Mesoscale"])
        self.product_combo.setToolTip("Select the GOES product type to display")
        control_layout.addRow(product_label, self.product_combo)

        # Channel selection
        channel_label = QLabel("Channel/Band:")
        channel_label.setProperty("class", "StandardLabel")
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([
            "Band 13 (IR)",
            "Band 14 (IR)",
            "True Color",
            "Cloud Top",
            "Temperature",
        ])
        self.channel_combo.setToolTip("Select the satellite band or composite to display")
        control_layout.addRow(channel_label, self.channel_combo)

        layout.addWidget(control_panel)

        # Enhanced action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.load_button = QPushButton("Load Imagery")
        # Use default button styling from theme
        self.load_button.setToolTip("Load and display the selected imagery")
        button_layout.addWidget(self.load_button)

        refresh_button = QPushButton("Refresh")
        # Use default button styling from theme
        refresh_button.setToolTip("Refresh available imagery")
        button_layout.addWidget(refresh_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Enhanced status label
        self.status_label = QLabel("✅ Ready - Select product and channel to load imagery")
        self.status_label.setProperty("class", "StatusSuccess")
        layout.addWidget(self.status_label)

        # Add stretch to push everything to the top
        layout.addStretch()

    def cleanup(self) -> None:
        """Clean up resources."""
