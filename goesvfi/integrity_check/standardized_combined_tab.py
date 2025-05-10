"""
Standardized combined integrity check tab with improved signal connections.

This module provides an improved implementation of the combined integrity check tab
with standardized signal connections using the TabSignalManager, ensuring consistent
data flow between all tab components.
"""

import logging
from typing import Optional, Dict, Any, List, cast
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QSplitter, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from .enhanced_gui_tab import EnhancedIntegrityCheckTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel
from .optimized_timeline_tab import OptimizedTimelineTab
from .satellite_integrity_tab_group import OptimizedResultsTab
from .enhanced_imagery_tab import EnhancedGOESImageryTab
from .view_model import MissingTimestamp
from .signal_manager import connect_integrity_check_tabs, create_signal_flow_diagram

# Configure logging
LOGGER = logging.getLogger(__name__)


class StandardizedCombinedTab(QWidget):
    """
    Standardized combined tab for integrity check, timeline, results, and imagery.
    
    This implementation uses the TabSignalManager to handle signal connections 
    between tabs, ensuring consistent data flow and proper error handling.
    """
    
    # Signals that this tab will emit to integrate with the rest of the application
    dateRangeSelected = pyqtSignal(datetime, datetime)
    timestampSelected = pyqtSignal(datetime)
    itemSelected = pyqtSignal(MissingTimestamp)
    directorySelected = pyqtSignal(str)
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the standardized combined tab.
        
        Args:
            view_model: The EnhancedIntegrityCheckViewModel instance to use
            parent: Optional parent widget
        """
        super().__init__(parent)
        
        # Store view model
        self.view_model = view_model
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create tab widget with styling for better visibility
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)  # More modern appearance
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        
        # Apply custom styling to make tabs more visible
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background-color: #2d2d2d;
            }
            
            QTabBar::tab {
                background-color: #303030;
                color: #b0b0b0;
                min-width: 120px;
                padding: 8px 12px;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            
            QTabBar::tab:selected {
                background-color: #3a3a3a;
                color: white;
                border-left: 2px solid #3498db;
                border-right: 2px solid #3498db;
                border-top: 2px solid #3498db;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #353535;
                color: white;
            }
        """)
        
        # Create individual tabs with consistent design
        self.integrity_tab = EnhancedIntegrityCheckTab(view_model, self)
        self.timeline_tab = OptimizedTimelineTab(parent=self)
        self.results_tab = OptimizedResultsTab(parent=self)
        self.imagery_tab = EnhancedGOESImageryTab(parent=self)
        
        # Add tabs to tab widget with descriptive names
        self.tab_widget.addTab(self.integrity_tab, "File Integrity")
        self.tab_widget.addTab(self.timeline_tab, "Timeline")
        self.tab_widget.addTab(self.results_tab, "Results")
        self.tab_widget.addTab(self.imagery_tab, "GOES Imagery")
        
        # Create information bar for navigation guidance
        self.info_bar = self._create_info_bar()
        
        # Add components to main layout
        layout.addWidget(self.info_bar)
        layout.addWidget(self.tab_widget, 1)  # Give tab widget stretch priority
        
        # Connect signals between tabs using the standardized approach
        self._connect_tab_signals()
        
        # Connect tab widget signals
        self.tab_widget.currentChanged.connect(self._handle_tab_changed)
        
        # Initialize the satellite visualization tabs
        self._initialize_satellite_tabs()
        
        LOGGER.info("Standardized combined tab initialized")
    
    def _create_info_bar(self) -> QWidget:
        """Create an information bar for navigation guidance."""
        info_bar = QFrame()
        info_bar.setMaximumHeight(30)
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-bottom: 1px solid #34495e;
            }
            QLabel {
                color: #ecf0f1;
                padding: 4px;
            }
        """)
        
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(10, 0, 10, 0)
        
        # Display navigation help text
        help_text = "Workflow: 1) Select directory in File Integrity tab, 2) Verify integrity, 3) Use Timeline and Results tabs to analyze, 4) View images in GOES Imagery tab"
        info_label = QLabel(help_text)
        info_label.setStyleSheet("font-size: 11px;")
        
        info_layout.addWidget(info_label)
        
        return info_bar
    
    def _connect_tab_signals(self) -> None:
        """Connect signals between tabs using the standardized approach."""
        # Create a dictionary of tabs
        tabs = {
            "integrity": self.integrity_tab,
            "timeline": self.timeline_tab,
            "results": self.results_tab,
            "imagery": self.imagery_tab,
            "view_model": self.view_model
        }
        
        # Connect tabs using the signal manager
        connect_integrity_check_tabs(tabs)
        
        # Connect combined tab's signals to forward events from child tabs
        self._connect_forwarding_signals()
        
        LOGGER.info("Connected tab signals using standardized approach")
        
        # Generate signal flow diagram for documentation if in debug mode
        import os
        if os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"):
            diagram = create_signal_flow_diagram(tabs)
            try:
                with open("docs/signal_flow_diagram.md", "w") as f:
                    f.write(diagram)
                LOGGER.info("Generated signal flow diagram in docs/signal_flow_diagram.md")
            except Exception as e:
                LOGGER.error(f"Error writing signal flow diagram: {e}")
    
    def _connect_forwarding_signals(self) -> None:
        """Connect signals from child tabs to forward to parent container."""
        # Forward date range signals
        if hasattr(self.integrity_tab, "date_range_changed"):
            self.integrity_tab.date_range_changed.connect(self.dateRangeSelected)
        
        # Forward timestamp signals
        if hasattr(self.timeline_tab, "timestampSelected"):
            self.timeline_tab.timestampSelected.connect(self.timestampSelected)
        
        # Forward item selection signals
        if hasattr(self.results_tab, "itemSelected"):
            self.results_tab.itemSelected.connect(self.itemSelected)
        
        # Forward directory selection signals
        if hasattr(self.integrity_tab, "directory_selected"):
            self.integrity_tab.directory_selected.connect(self.directorySelected)
    
    def _initialize_satellite_tabs(self) -> None:
        """Initialize all satellite-related tabs with data from the view model."""
        if hasattr(self.view_model, 'missing_items') and self.view_model.missing_items:
            # Get the date range and interval from the view model
            start_date = self.view_model.start_date
            end_date = self.view_model.end_date
            total_expected = getattr(self.view_model, 'total_expected', len(self.view_model.missing_items))
            
            # Determine the interval (assume hourly if not specified)
            interval_minutes = 60
            if hasattr(self.view_model, 'expected_interval_minutes'):
                interval_minutes = self.view_model.expected_interval_minutes
            
            # Set the data for each tab
            # Timeline Tab
            self.timeline_tab.set_data(
                self.view_model.missing_items,
                start_date,
                end_date,
                interval_minutes
            )
            
            # Results Tab
            self.results_tab.set_items(
                self.view_model.missing_items, 
                total_expected
            )
            
            LOGGER.info(f"Satellite tabs initialized with {len(self.view_model.missing_items)} items")
    
    def _handle_tab_changed(self, index: int) -> None:
        """
        Handle tab change events to update UI context.
        
        Args:
            index: New tab index
        """
        # Update tab-specific UI elements or state
        tab_name = self.tab_widget.tabText(index)
        LOGGER.debug(f"Switched to tab: {tab_name}")
        
        # If switching to imagery tab, we could check for previews to show
        if index == 3:  # GOES Imagery tab
            self._check_for_imagery_previews()
    
    def _check_for_imagery_previews(self) -> None:
        """Check for available imagery previews to display in the imagery tab."""
        # This method could look for downloaded files from the view model
        # and pass them to the imagery tab for preview generation
        if hasattr(self.view_model, 'missing_items'):
            downloaded_items = [item for item in self.view_model.missing_items 
                               if getattr(item, 'is_downloaded', False) and 
                               getattr(item, 'local_path', '')]
            
            if downloaded_items and hasattr(self.imagery_tab, 'add_previews'):
                LOGGER.info(f"Found {len(downloaded_items)} downloaded items for preview")
                # This assumes the imagery tab has a method to add previews
                # self.imagery_tab.add_previews(downloaded_items)
    
    # --- Public methods for external interaction ---
    
    def update_data(self, missing_items=None, start_date=None, end_date=None, total_expected=None) -> None:
        """
        Update the tab with new data.
        
        Args:
            missing_items: Optional list of missing timestamps to update
            start_date: Optional new start date
            end_date: Optional new end date
            total_expected: Optional total expected count
        """
        # Update view model if values provided
        if missing_items is not None:
            if hasattr(self.view_model, '_missing_items'):
                self.view_model._missing_items = missing_items
            elif hasattr(self.view_model, 'set_missing_items'):
                self.view_model.set_missing_items(missing_items)
        
        if start_date is not None:
            self.view_model.start_date = start_date
            
        if end_date is not None:
            self.view_model.end_date = end_date
            
        if total_expected is not None and hasattr(self.view_model, '_total_expected'):
            self.view_model._total_expected = total_expected
        
        # Update internal tabs
        self._initialize_satellite_tabs()
        
        # Also update integrity tab if it has an update method
        if hasattr(self.integrity_tab, 'update_data'):
            self.integrity_tab.update_data()
    
    def show_integrity_tab(self) -> None:
        """Switch to the integrity tab."""
        self.tab_widget.setCurrentIndex(0)
    
    def show_timeline_tab(self) -> None:
        """Switch to the timeline tab."""
        self.tab_widget.setCurrentIndex(1)
    
    def show_results_tab(self) -> None:
        """Switch to the results tab."""
        self.tab_widget.setCurrentIndex(2)
    
    def show_imagery_tab(self) -> None:
        """Switch to the imagery tab."""
        self.tab_widget.setCurrentIndex(3)
    
    def get_current_tab_name(self) -> str:
        """Get the name of the currently active tab."""
        index = self.tab_widget.currentIndex()
        return self.tab_widget.tabText(index)


# Alias for backward compatibility with existing code
CombinedIntegrityTab = StandardizedCombinedTab