"""
Combined Integrity Check and GOES Imagery Tab

This module provides a combined tab that includes both the enhanced integrity check
functionality and the GOES imagery visualization features in a tabbed interface.
"""

import logging
from typing import Optional, cast

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QStackedWidget, QPushButton
)
from PyQt6.QtCore import Qt

from .enhanced_gui_tab import EnhancedIntegrityCheckTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel
from .enhanced_imagery_tab import EnhancedGOESImageryTab

# Configure logging
LOGGER = logging.getLogger(__name__)


class CombinedIntegrityAndImageryTab(QWidget):
    """
    Combined tab that includes both integrity check and GOES imagery functionality.
    
    This tab contains:
    1. The enhanced integrity check tab for verifying imagery files
    2. The GOES imagery visualization tab for viewing and processing images
    """
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the combined tab.
        
        Args:
            view_model: The EnhancedIntegrityCheckViewModel instance to use
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a more compact tab switcher using buttons in a horizontal layout
        tab_switcher = QWidget()
        tab_switcher.setMaximumHeight(40)  # Limit height for compactness
        switcher_layout = QHBoxLayout(tab_switcher)
        switcher_layout.setContentsMargins(5, 0, 5, 0)  # Minimal margins
        
        # Create the stacked widget (instead of tab widget)
        self.stacked_widget = QStackedWidget(self)
        
        # Create integrity check tab
        self.integrity_tab = EnhancedIntegrityCheckTab(view_model, self)
        
        # Create GOES imagery tab
        self.imagery_tab = EnhancedGOESImageryTab(parent=self)
        
        # Add both pages to the stacked widget
        self.stacked_widget.addWidget(self.integrity_tab)  # Index 0
        self.stacked_widget.addWidget(self.imagery_tab)    # Index 1
        
        # Create switcher buttons
        self.integrity_button = QPushButton("File Integrity")
        self.imagery_button = QPushButton("GOES Imagery")
        
        # Style the buttons to look like tabs
        button_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #b0b0b0;
                border: none;
                padding: 5px 10px;
                border-bottom: 2px solid transparent;
            }
            QPushButton:checked, QPushButton:pressed {
                color: white;
                background-color: #444444;
                border-bottom: 2px solid #3498db;
            }
        """
        self.integrity_button.setStyleSheet(button_style)
        self.imagery_button.setStyleSheet(button_style)
        self.integrity_button.setCheckable(True)
        self.imagery_button.setCheckable(True)
        
        # Set fixed width for consistent appearance
        self.integrity_button.setMinimumWidth(120)
        self.imagery_button.setMinimumWidth(120)
        
        # Add to switcher layout
        switcher_layout.addWidget(self.integrity_button)
        switcher_layout.addWidget(self.imagery_button)
        switcher_layout.addStretch(1)  # Push buttons to the left
        
        # Connect button signals
        self.integrity_button.clicked.connect(lambda: self._switch_tab(0))
        self.imagery_button.clicked.connect(lambda: self._switch_tab(1))
        
        # Set initial state
        self.integrity_button.setChecked(True)
        
        # Add components to main layout
        layout.addWidget(tab_switcher)
        layout.addWidget(self.stacked_widget)
        
        # Connect signals between tabs if needed
        # For example, when files are downloaded in integrity tab,
        # the imagery tab could be notified to update its file list
        # self.integrity_tab.files_downloaded.connect(self.imagery_tab.refresh_files)
        
        LOGGER.info("Combined integrity and imagery tab initialized")
        
    def _switch_tab(self, index: int) -> None:
        """Switch to the tab at the specified index and update button states."""
        self.stacked_widget.setCurrentIndex(index)
        
        # Update button checked states
        self.integrity_button.setChecked(index == 0)
        self.imagery_button.setChecked(index == 1)