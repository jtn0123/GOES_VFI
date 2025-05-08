"""
Combined Integrity Check and GOES Imagery Tab with Unified Interface

This module provides a combined tab that includes both the enhanced integrity check
functionality and the GOES imagery visualization features in a unified, optimized interface.
"""

import logging
from typing import Optional, cast, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, 
    QStackedWidget, QPushButton, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from .enhanced_gui_tab import EnhancedIntegrityCheckTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel
from .enhanced_imagery_tab import EnhancedGOESImageryTab
from .shared_components import (
    SharedPreviewPanel, SidebarSettingsPanel, 
    CollapsibleSettingsGroup, PreviewMetadata
)

# Configure logging
LOGGER = logging.getLogger(__name__)


class UnifiedCombinedTab(QWidget):
    """
    Combined tab with unified interface for both integrity check and GOES imagery.
    
    This tab integrates:
    1. The enhanced integrity check tab for verifying imagery files
    2. The GOES imagery visualization tab for viewing and processing images
    3. Shared components for a more integrated experience
    """
    
    def __init__(self, view_model: EnhancedIntegrityCheckViewModel, parent=None):
        """
        Initialize the unified combined tab.
        
        Args:
            view_model: The EnhancedIntegrityCheckViewModel instance to use
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.view_model = view_model
        
        # Create layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create tab switcher (more compact buttons)
        self._create_tab_switcher(main_layout)
        
        # Create main content area with shared preview and settings
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Create central content area
        self.central_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create and add main content stack that will contain the tabs
        self._create_main_content_stack()
        
        # Create the shared preview panel
        self.preview_panel = SharedPreviewPanel()
        
        # Create the settings sidebar
        self.settings_panel = SidebarSettingsPanel()
        
        # Add panels to central splitter
        self.central_splitter.addWidget(self.stacked_widget)  # Main tab content
        self.central_splitter.addWidget(self.preview_panel)   # Shared preview
        self.central_splitter.addWidget(self.settings_panel)  # Settings sidebar
        
        # Set initial splitter sizes (main content : preview : settings) ratio ~3:4:2
        self.central_splitter.setSizes([300, 400, 200])
        
        # Add to content layout
        content_layout.addWidget(self.central_splitter)
        
        # Add content widget to main layout
        main_layout.addWidget(content_widget, 1)  # Give it stretch
        
        # Connect signals between components
        self._connect_signals()
        
        # Set initial state
        self._switch_tab(0)  # Start with integrity tab
        
        LOGGER.info("Unified combined tab initialized")
    
    def _create_tab_switcher(self, parent_layout):
        """
        Create the tab switcher component with buttons.
        
        Args:
            parent_layout: Parent layout to add the switcher to
        """
        # Create a widget for the tab buttons
        tab_switcher = QWidget()
        tab_switcher.setMaximumHeight(40)
        
        # Create layout
        switcher_layout = QHBoxLayout(tab_switcher)
        switcher_layout.setContentsMargins(5, 0, 5, 0)
        
        # Create tab buttons
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
        
        # Set minimum width for buttons
        self.integrity_button.setMinimumWidth(120)
        self.imagery_button.setMinimumWidth(120)
        
        # Add to layout
        switcher_layout.addWidget(self.integrity_button)
        switcher_layout.addWidget(self.imagery_button)
        
        # Add split view button
        self.split_view_button = QPushButton("Split View")
        self.split_view_button.setCheckable(True)
        self.split_view_button.setStyleSheet(button_style)
        self.split_view_button.setMinimumWidth(120)
        switcher_layout.addWidget(self.split_view_button)
        
        # Add spacer to push buttons to the left
        switcher_layout.addStretch(1)
        
        # Connect signals
        self.integrity_button.clicked.connect(lambda: self._switch_tab(0))
        self.imagery_button.clicked.connect(lambda: self._switch_tab(1))
        self.split_view_button.clicked.connect(self._toggle_split_view)
        
        # Set default state
        self.integrity_button.setChecked(True)
        
        # Add to parent layout
        parent_layout.addWidget(tab_switcher)
    
    def _create_main_content_stack(self):
        """Create the stacked widget that contains main tab content."""
        # Create stacked widget
        self.stacked_widget = QStackedWidget()
        
        # Create normal view tabs
        self.integrity_tab = EnhancedIntegrityCheckTab(self.view_model, self)
        self.imagery_tab = EnhancedGOESImageryTab(parent=self)
        
        # Create the split view (combination of both tabs)
        self.split_view = QWidget()
        split_layout = QVBoxLayout(self.split_view)
        split_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create inner splitter for split view
        self.view_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Add tabs to the splitter
        self.integrity_container = QWidget()
        integrity_layout = QVBoxLayout(self.integrity_container)
        integrity_layout.setContentsMargins(0, 0, 0, 0)
        integrity_layout.addWidget(self.integrity_tab)
        
        self.imagery_container = QWidget()
        imagery_layout = QVBoxLayout(self.imagery_container)
        imagery_layout.setContentsMargins(0, 0, 0, 0)
        imagery_layout.addWidget(self.imagery_tab)
        
        # Add containers to splitter
        self.view_splitter.addWidget(self.integrity_container)
        self.view_splitter.addWidget(self.imagery_container)
        
        # Add splitter to split view
        split_layout.addWidget(self.view_splitter)
        
        # Add all views to stacked widget
        self.stacked_widget.addWidget(self.integrity_tab)  # Index 0
        self.stacked_widget.addWidget(self.imagery_tab)    # Index 1
        self.stacked_widget.addWidget(self.split_view)     # Index 2
    
    def _connect_signals(self):
        """Connect signals between components for interaction."""
        # Connect preview panel signals
        self.preview_panel.previewSelected.connect(self._on_preview_selected)
        
        # Connect settings panel signals
        # Date/time changes in settings should update both tabs
        self.settings_panel.date_edit.dateChanged.connect(self._on_date_changed)
        self.settings_panel.time_edit.timeChanged.connect(self._on_time_changed)
        
        # Example of tab-specific data sharing
        if hasattr(self.integrity_tab, 'files_downloaded'):
            self.integrity_tab.files_downloaded.connect(self._on_files_downloaded)
    
    def _switch_tab(self, index):
        """
        Switch to the tab at the specified index and update button states.
        
        Args:
            index: Tab index to switch to (0 for integrity, 1 for imagery)
        """
        # Reset split view button if it was active
        if self.split_view_button.isChecked() and index != 2:
            self.split_view_button.setChecked(False)
        
        # Set the current widget
        self.stacked_widget.setCurrentIndex(index)
        
        # Update button states
        self.integrity_button.setChecked(index == 0)
        self.imagery_button.setChecked(index == 1)
        
        # Update settings panel context for the current tab
        self._update_settings_context(index)
        
        LOGGER.info(f"Switched to tab index: {index}")
    
    def _toggle_split_view(self, checked):
        """
        Toggle split view mode.
        
        Args:
            checked: Whether split view is activated
        """
        if checked:
            # Switch to split view
            self.stacked_widget.setCurrentIndex(2)
            # Uncheck other tab buttons
            self.integrity_button.setChecked(False)
            self.imagery_button.setChecked(False)
            LOGGER.info("Enabled split view mode")
        else:
            # Return to previously active tab or default to integrity
            if self.integrity_button.isChecked():
                self.stacked_widget.setCurrentIndex(0)
            else:
                self.stacked_widget.setCurrentIndex(1)
            LOGGER.info("Disabled split view mode")
    
    def _update_settings_context(self, tab_index):
        """
        Update settings panel to show context-specific settings.
        
        Args:
            tab_index: Index of the active tab
        """
        # Show/hide sections based on active tab
        if tab_index == 0:  # Integrity tab
            # Show integrity-specific settings
            self.settings_panel.show_section("advanced", False)  # Hide advanced
            self.settings_panel.show_section("visualization", False)  # Hide viz
            # Could add more specific settings visibility here
        elif tab_index == 1:  # Imagery tab
            # Show imagery-specific settings
            self.settings_panel.show_section("advanced", True)  # Show advanced
            self.settings_panel.show_section("visualization", True)  # Show viz
        else:  # Split view
            # Show all settings for split view
            self.settings_panel.show_section("advanced", True)
            self.settings_panel.show_section("visualization", True)
    
    def _on_preview_selected(self, key, metadata):
        """
        Handle when a preview is selected in the shared preview panel.
        
        Args:
            key: Selected preview key
            metadata: Preview metadata
        """
        # Update settings to match the preview
        if isinstance(metadata, PreviewMetadata):
            # Update date/time
            self.settings_panel.set_date_time(metadata.date_time)
            
            # Could update other settings based on metadata
            LOGGER.info(f"Preview selected: {key}, updated settings")
    
    def _on_date_changed(self, new_date):
        """
        Handle date changes in settings panel.
        
        Args:
            new_date: New date selected
        """
        # Update both tabs with the new date
        # Implementation depends on specific tab APIs
        LOGGER.info(f"Date changed: {new_date.toString('yyyy-MM-dd')}")
        
        # Example: could force refresh of previews or data
    
    def _on_time_changed(self, new_time):
        """
        Handle time changes in settings panel.
        
        Args:
            new_time: New time selected
        """
        # Update both tabs with the new time
        LOGGER.info(f"Time changed: {new_time.toString('HH:mm')}")
    
    def _on_files_downloaded(self, file_list):
        """
        Handle when files are downloaded in the integrity tab.
        
        Args:
            file_list: List of downloaded files
        """
        # Notify the imagery tab about new files
        LOGGER.info(f"Files downloaded: {len(file_list)} files")
        
        # Could add code here to pass the files to the imagery tab
        # or create previews from them
        
        # Example of creating a preview from a downloaded file
        # if file_list and hasattr(self.imagery_tab, 'process_file'):
        #     # Process the first file as an example
        #     first_file = file_list[0]
        #     self.imagery_tab.process_file(first_file)


# For backward compatibility - aliasing the new implementation
CombinedIntegrityAndImageryTab = UnifiedCombinedTab