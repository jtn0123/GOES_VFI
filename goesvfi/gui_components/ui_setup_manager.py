"""UI setup functionality for MainWindow."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget

from goesvfi.date_sorter.gui_tab import DateSorterTab
from goesvfi.file_sorter.gui_tab import FileSorterTab
from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab
from goesvfi.gui_tabs.main_tab import MainTab
from goesvfi.gui_tabs.model_library_tab import ModelLibraryTab
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.combined_tab import CombinedIntegrityAndImageryTab
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.reconciler import Reconciler
from goesvfi.integrity_check.remote.cdn_store import CDNStore
from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.integrity_check.time_index import TimeIndex
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class UISetupManager:
    """Manages UI setup and tab creation for MainWindow."""

    def setup_tab_widget(self, main_window: Any) -> None:
        """Configure the tab widget appearance and behavior.

        Args:
            main_window: The MainWindow instance
        """
        main_window.tab_widget = QTabWidget()
        # Set tabs to left side for better vertical space usage
        main_window.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        # Enable document mode for a more compact appearance
        main_window.tab_widget.setDocumentMode(True)
        # Set elide mode for tabs to make them more compact
        main_window.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)

        # Apply custom styling
        main_window.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid  #3c3c3c;
                background-color:  #2a2a2a;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab:left {
                background-color:  #303030;
                color:  #b0b0b0;
                border: 1px solid  #444;
                border-right: none;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
                min-height: 30px;
                padding: 6px;
                margin: 2px 0;
                margin-right: -1px; /* Create slight overlap with the pane */
            }
            QTabBar::tab:left:selected {
                background-color:  #2a2a2a;
                color: white;
                border-left: 3px solid  #3498db; /* Blue accent for selected tab */
                padding-left: 4px; /* Compensate for thicker border */
            }
            QTabBar::tab:left:hover:!selected {
                background-color:  #383838;
                border-left: 2px solid  #666;
                padding-left: 5px; /* Compensate for border */
            }
        """
        )

    def create_all_tabs(self, main_window: Any) -> None:
        """Create and configure all application tabs.

        Args:
            main_window: The MainWindow instance
        """
        # Create main tab
        main_window.main_tab = MainTab(
            main_view_model=main_window.main_view_model,
            image_loader=main_window.image_loader,
            sanchez_processor=main_window.sanchez_processor,
            image_cropper=main_window.image_cropper,
            settings=main_window.settings,
            request_previews_update_signal=main_window.request_previews_update,
            main_window_ref=main_window,
            parent=main_window,
        )

        # Create FFmpeg settings tab
        main_window.ffmpeg_settings_tab = FFmpegSettingsTab(parent=main_window)
        main_window.ffmpeg_settings_tab.set_enabled(main_window.current_encoder == "FFmpeg")

        # Create model library tab
        main_window.model_library_tab = ModelLibraryTab(parent=main_window)

        # Create sorter tabs
        main_window.file_sorter_tab = FileSorterTab(
            view_model=main_window.main_view_model.file_sorter_vm, parent=main_window
        )
        main_window.date_sorter_tab = DateSorterTab(
            view_model=main_window.main_view_model.date_sorter_vm, parent=main_window
        )

        # Create integrity check tab
        self.create_integrity_check_tab(main_window)

        # Add all tabs to widget
        main_window.tab_widget.addTab(main_window.main_tab, "Main")
        main_window.tab_widget.addTab(main_window.ffmpeg_settings_tab, "FFmpeg Settings")
        main_window.tab_widget.addTab(main_window.model_library_tab, "Model Library")
        main_window.tab_widget.addTab(main_window.file_sorter_tab, "File Sorter")
        main_window.tab_widget.addTab(main_window.date_sorter_tab, "Date Sorter")
        main_window.tab_widget.addTab(main_window.combined_tab, "Satellite Integrity")

    def create_integrity_check_tab(self, main_window: Any) -> None:
        """Create and configure the integrity check tab.

        Args:
            main_window: The MainWindow instance
        """
        # Create the database directory if it doesn't exist
        db_dir = Path.home() / ".goes_vfi" / "integrity_check"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "cache.db"

        # Create CacheDB instance for the integrity check
        cache_db = CacheDB(db_path=db_path)

        # Initialize stores
        cdn_store = CDNStore(resolution=TimeIndex.CDN_RES)
        s3_store = S3Store(aws_region="us-east-1")

        # Create a reconciler with the cache db path
        reconciler = Reconciler(cache_db_path=db_path)

        # Create the integrity check view model and tab with all necessary components
        main_window.integrity_check_vm = EnhancedIntegrityCheckViewModel(
            base_reconciler=reconciler,
            cache_db=cache_db,
            cdn_store=cdn_store,
            s3_store=s3_store,
        )

        # Disable the disk space timer since it blocks the application
        if hasattr(main_window.integrity_check_vm, "_disk_space_timer"):
            if main_window.integrity_check_vm._disk_space_timer.isRunning():
                main_window.integrity_check_vm._disk_space_timer.terminate()
                main_window.integrity_check_vm._disk_space_timer.wait()

        # Use the combined tab which includes both enhanced integrity check and enhanced GOES imagery
        main_window.combined_tab = CombinedIntegrityAndImageryTab(
            view_model=main_window.integrity_check_vm, parent=main_window
        )
        # Reference the integrity check tab from within the combined tab for backward compatibility
        main_window.integrity_check_tab = main_window.combined_tab.integrity_tab
