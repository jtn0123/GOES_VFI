"""UI setup functionality for MainWindow."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget, QWidget

from goesvfi.date_sorter.gui_tab import DateSorterTab
from goesvfi.file_sorter.gui_tab import FileSorterTab

# Import moved to method to avoid circular imports
# from goesvfi.integrity_check.cache_db import CacheDB
# from goesvfi.integrity_check.combined_tab import CombinedIntegrityAndImageryTab
# from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
# from goesvfi.integrity_check.reconciler import Reconciler
# from goesvfi.integrity_check.remote.cdn_store import CDNStore
# from goesvfi.integrity_check.remote.s3_store import S3Store
# from goesvfi.integrity_check.time_index import TimeIndex
from goesvfi.gui_components.icon_manager import get_icon
from goesvfi.gui_components.lazy_tab_loader import LazyTabLoader
from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab

# Import moved to method to avoid circular import
# from goesvfi.gui_tabs.main_tab import MainTab
from goesvfi.gui_tabs.model_library_tab import ModelLibraryTab
from goesvfi.gui_tabs.settings_tab import SettingsTab
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
        # Make tabs movable for better user experience
        main_window.tab_widget.setMovable(True)
        # Set tab shape to rounded for better aesthetics
        main_window.tab_widget.setTabShape(QTabWidget.TabShape.Rounded)
        # Enable close buttons on tabs for enhanced UX (though we won't use them)
        main_window.tab_widget.setTabsClosable(False)
        # Tab bar width is controlled by CSS styling

        # Tab styling is now handled by qt-material theme system
        # Any custom overrides would be applied via ThemeManager's custom_overrides

    def create_all_tabs(self, main_window: Any) -> None:
        """Create and configure all application tabs with lazy loading.

        Args:
            main_window: The MainWindow instance
        """
        # Import here to avoid circular import
        from goesvfi.gui_tabs.main_tab import MainTab

        # Initialize lazy tab loader
        main_window.lazy_tab_loader = LazyTabLoader(main_window.tab_widget)

        # Create main tab immediately (always needed at startup)
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

        # Add main tab immediately
        main_window.tab_widget.addTab(main_window.main_tab, "")
        main_window.tab_widget.setTabIcon(0, get_icon("🎬"))

        # Register other tabs for lazy loading

        # FFmpeg Settings Tab (index 1)
        def create_ffmpeg_tab() -> QWidget:
            main_window.ffmpeg_settings_tab = FFmpegSettingsTab(parent=main_window)
            main_window.ffmpeg_settings_tab.set_enabled(main_window.current_encoder == "FFmpeg")
            return main_window.ffmpeg_settings_tab

        main_window.lazy_tab_loader.register_tab(1, create_ffmpeg_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(1, "FFmpeg Settings", get_icon("⚙️"))

        # Model Library Tab (index 2)
        def create_model_library_tab() -> QWidget:
            main_window.model_library_tab = ModelLibraryTab(parent=main_window)
            return main_window.model_library_tab

        main_window.lazy_tab_loader.register_tab(2, create_model_library_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(2, "Model Library", get_icon("📚"))

        # Integrity Check Tab (index 3)
        def create_integrity_tab() -> QWidget:
            self.create_integrity_check_tab(main_window)
            return main_window.combined_tab

        main_window.lazy_tab_loader.register_tab(3, create_integrity_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(3, "Satellite Integrity", get_icon("🛰️"))

        # File Sorter Tab (index 4)
        def create_file_sorter_tab() -> QWidget:
            main_window.file_sorter_tab = FileSorterTab(
                view_model=main_window.main_view_model.file_sorter_vm, parent=main_window
            )
            return main_window.file_sorter_tab

        main_window.lazy_tab_loader.register_tab(4, create_file_sorter_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(4, "File Sorter", get_icon("📁"))

        # Date Sorter Tab (index 5)
        def create_date_sorter_tab() -> QWidget:
            main_window.date_sorter_tab = DateSorterTab(
                view_model=main_window.main_view_model.date_sorter_vm, parent=main_window
            )
            return main_window.date_sorter_tab

        main_window.lazy_tab_loader.register_tab(5, create_date_sorter_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(5, "Date Sorter", get_icon("📅"))

        # Settings Tab (index 6)
        def create_settings_tab() -> QWidget:
            main_window.settings_tab = SettingsTab(parent=main_window)
            return main_window.settings_tab

        main_window.lazy_tab_loader.register_tab(6, create_settings_tab)
        main_window.lazy_tab_loader.setup_lazy_tab(6, "Settings", get_icon("⚙️"))

        # Add tooltips for all tabs
        main_window.tab_widget.setTabToolTip(0, "Main - Video generation and processing")
        main_window.tab_widget.setTabToolTip(1, "FFmpeg Settings - Video encoding options")
        main_window.tab_widget.setTabToolTip(2, "Model Library - AI model management")
        main_window.tab_widget.setTabToolTip(3, "Satellite Integrity - Data validation")
        main_window.tab_widget.setTabToolTip(4, "File Sorter - Organize files by type")
        main_window.tab_widget.setTabToolTip(5, "Date Sorter - Organize files by date")
        main_window.tab_widget.setTabToolTip(6, "Settings - Application preferences")

        LOGGER.info("Tab setup complete with lazy loading enabled for 6 tabs")

    def create_integrity_check_tab(self, main_window: Any) -> None:
        """Create and configure the integrity check tab.

        Args:
            main_window: The MainWindow instance
        """
        # Import here to avoid circular imports
        from goesvfi.integrity_check.cache_db import CacheDB
        from goesvfi.integrity_check.combined_tab import CombinedIntegrityAndImageryTab
        from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
        from goesvfi.integrity_check.reconciler import Reconciler
        from goesvfi.integrity_check.remote.cdn_store import CDNStore
        from goesvfi.integrity_check.remote.s3_store import S3Store
        from goesvfi.integrity_check.time_index import TimeIndex

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
