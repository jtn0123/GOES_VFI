"""Initialization management for MainWindow components."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import numpy as np

from goesvfi.date_sorter.sorter import DateSorter
from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.gui_components.crop_handler import CropHandler
from goesvfi.gui_components.file_picker_manager import FilePickerManager
from goesvfi.gui_components.model_selector_manager import ModelSelectorManager
from goesvfi.gui_components.preview_manager import PreviewManager
from goesvfi.gui_components.processing_callbacks import ProcessingCallbacks
from goesvfi.gui_components.processing_manager import ProcessingManager
from goesvfi.gui_components.rife_ui_manager import RifeUIManager
from goesvfi.gui_components.signal_broker import SignalBroker
from goesvfi.gui_components.state_manager import StateManager
from goesvfi.gui_components.ui_setup_manager import UISetupManager
from goesvfi.gui_components.zoom_manager import ZoomManager
from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.utils import log
from goesvfi.utils.image_processing.refactored_preview import RefactoredPreviewProcessor
from goesvfi.view_models.main_window_view_model import MainWindowViewModel

LOGGER = log.get_logger(__name__)


class InitializationManager:
    """Manages initialization of MainWindow components."""

    def initialize_models(self, main_window: Any) -> None:
        """Initialize data models and view models.

        Args:
            main_window: The MainWindow instance
        """
        # Instantiate Models needed by ViewModels
        file_sorter_model = FileSorter()
        date_sorter_model = DateSorter()
        LOGGER.info("Models instantiated.")

        # Instantiate helper managers for the ProcessingViewModel
        preview_manager = PreviewManager()
        processing_manager = ProcessingManager()

        # Instantiate ViewModels here, passing required models and managers
        main_window.main_view_model = MainWindowViewModel(
            file_sorter_model=file_sorter_model,
            date_sorter_model=date_sorter_model,
            preview_manager=preview_manager,
            processing_manager=processing_manager,
        )
        main_window.processing_view_model = main_window.main_view_model.processing_vm
        LOGGER.info("ViewModels instantiated.")

    def initialize_processors(self, main_window: Any) -> None:
        """Initialize image processors.

        Args:
            main_window: The MainWindow instance
        """
        # Instantiate processors to be reused for previews
        main_window.image_loader = ImageLoader()

        # SanchezProcessor needs a temp directory, create one for the GUI lifetime
        main_window._sanchez_gui_temp_dir = (
            Path(tempfile.gettempdir()) / f"goes_vfi_sanchez_gui_{os.getpid()}"
        )
        os.makedirs(main_window._sanchez_gui_temp_dir, exist_ok=True)
        main_window.sanchez_processor = SanchezProcessor(
            main_window._sanchez_gui_temp_dir
        )
        main_window.image_cropper = ImageCropper()
        LOGGER.info("GUI Image processors instantiated.")

    def initialize_state(self, main_window: Any) -> None:
        """Initialize state variables and component managers.

        Args:
            main_window: The MainWindow instance
        """
        # Initialize state variables
        main_window.sanchez_preview_cache: Dict[Path, np.ndarray[Any, Any]] = {}
        main_window.in_dir = None
        main_window.out_file_path = None
        main_window.current_crop_rect = None
        main_window.vfi_worker = None
        main_window.is_processing = False
        # current_encoder and current_model_key are properties that come from main_tab,
        # no need to initialize them here

        # Create preview processor
        main_window.preview_processor = RefactoredPreviewProcessor(
            main_window.sanchez_preview_cache
        )

        # Create all component managers
        self._create_component_managers(main_window)

    def _create_component_managers(self, main_window: Any) -> None:
        """Create all component managers.

        Args:
            main_window: The MainWindow instance
        """
        main_window.signal_broker = SignalBroker()
        main_window.rife_ui_manager = RifeUIManager()
        main_window.zoom_manager = ZoomManager()
        main_window.state_manager = StateManager(main_window)
        main_window.ui_setup_manager = UISetupManager()
        main_window.processing_callbacks = ProcessingCallbacks()
        main_window.crop_handler = CropHandler()
        main_window.file_picker_manager = FilePickerManager()
        main_window.model_selector_manager = ModelSelectorManager()
