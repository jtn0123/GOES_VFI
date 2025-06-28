"""Enhanced integration test for preview functionality with detailed validation."""

from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from goesvfi.gui import MainWindow
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class TestEnhancedPreviewValidation(unittest.TestCase):
    """Enhanced test for preview images with detailed validation and logging."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary directory with test images
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Create test images with different colors for validation
        self.image1_path = self._create_test_image("001_frame.png", color=(255, 0, 0), size=(300, 200))  # Red
        self.image2_path = self._create_test_image("002_frame.png", color=(0, 255, 0), size=(300, 200))  # Green
        self.image3_path = self._create_test_image("003_frame.png", color=(0, 0, 255), size=(300, 200))  # Blue

        # Create MainWindow
        self.main_window = MainWindow(debug_mode=True)

        # Track issues found
        self.issues_found = []

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
        self.main_window.close()

        # Report any issues found
        if self.issues_found:
            LOGGER.warning("Issues found during test: %s", self.issues_found)

    def _create_test_image(self, name: str, size: tuple = (100, 100), color: tuple = (255, 0, 0)) -> Path:
        """Create a test image file with specific characteristics."""
        img = Image.new("RGB", size, color)
        path = self.test_dir / name
        img.save(path, "PNG")
        LOGGER.debug("Created test image: %s (size: %s, color: %s)", path, size, color)
        return path

    def test_preview_images_display_validation(self) -> None:
        """Test preview images display with comprehensive validation."""
        LOGGER.info("=== STARTING ENHANCED PREVIEW VALIDATION TEST ===")

        # Clear any existing directory first (may be persisted from settings)
        self.main_window.set_in_dir(None)
        self._wait_for_preview_processing()

        # Verify initial state
        if self.main_window.in_dir is not None:
            LOGGER.warning(
                "MainWindow already had directory set: %s - this is expected due to settings persistence",
                self.main_window.in_dir,
            )

        self._validate_preview_labels_exist()

        # Set the input directory
        LOGGER.info("Setting input directory: %s", self.test_dir)
        self.main_window.set_in_dir(self.test_dir)

        # Allow time for processing with multiple event loops
        self._wait_for_preview_processing()

        # Validate preview manager state
        self._validate_preview_manager_state()

        # Validate GUI display state
        self._validate_gui_display_state()

        # Validate image data integrity
        self._validate_image_data_integrity()

        # Test error conditions
        self._test_error_conditions()

        LOGGER.info("=== ENHANCED PREVIEW VALIDATION TEST COMPLETED ===")

        # Fail test if any issues were found
        if self.issues_found:
            self.fail(f"Preview validation found {len(self.issues_found)} issues: {self.issues_found}")

    def _validate_preview_labels_exist(self) -> None:
        """Validate that preview labels exist and are properly initialized."""
        LOGGER.debug("Validating preview labels exist...")

        required_labels = ["first_frame_label", "last_frame_label"]
        optional_labels = ["middle_frame_label"]

        for label_name in required_labels:
            if not hasattr(self.main_tab, label_name):
                issue = f"CRITICAL: Missing required label: {label_name}"
                LOGGER.error(issue)
                self.issues_found.append(issue)
            else:
                label = getattr(self.main_tab, label_name)
                if label is None:
                    issue = f"CRITICAL: Label {label_name} is None"
                    LOGGER.error(issue)
                    self.issues_found.append(issue)
                else:
                    LOGGER.debug("Label %s exists and is not None", label_name)

        for label_name in optional_labels:
            if hasattr(self.main_tab, label_name):
                LOGGER.debug("Optional label %s exists", label_name)
            else:
                LOGGER.debug("Optional label %s does not exist", label_name)

    def _wait_for_preview_processing(self) -> None:
        """Wait for preview processing with multiple event processing rounds."""
        LOGGER.debug("Waiting for preview processing...")

        # Initial event processing
        QTimer.singleShot(50, lambda: None)
        self.app.processEvents()

        # Multiple rounds of waiting and processing
        for i in range(5):
            time.sleep(0.1)
            self.app.processEvents()
            LOGGER.debug("Processing round %d completed", i + 1)

        # Final processing
        time.sleep(0.2)
        self.app.processEvents()
        LOGGER.debug("Preview processing wait completed")

    def _validate_preview_manager_state(self) -> None:
        """Validate that preview manager loaded images correctly."""
        LOGGER.debug("Validating preview manager state...")

        preview_manager = self.main_window.main_view_model.preview_manager

        # Check that manager has current directory set
        if preview_manager.current_input_dir != self.test_dir:
            issue = (
                f"Preview manager input dir mismatch: expected {self.test_dir}, got {preview_manager.current_input_dir}"
            )
            LOGGER.error(issue)
            self.issues_found.append(issue)

        # Check frame data
        first_data, middle_data, last_data = preview_manager.get_current_frame_data()

        if first_data is None:
            issue = "CRITICAL: first_frame_data is None"
            LOGGER.error(issue)
            self.issues_found.append(issue)
        else:
            LOGGER.debug("First frame data exists: %s", type(first_data))

        if last_data is None:
            issue = "CRITICAL: last_frame_data is None"
            LOGGER.error(issue)
            self.issues_found.append(issue)
        else:
            LOGGER.debug("Last frame data exists: %s", type(last_data))

        # Middle data can be None if only 2 images
        if middle_data is not None:
            LOGGER.debug("Middle frame data exists: %s", type(middle_data))
        else:
            LOGGER.debug("Middle frame data is None (expected for 3 images)")

    def _validate_gui_display_state(self) -> None:
        """Validate that GUI labels are displaying images correctly."""
        LOGGER.debug("Validating GUI display state...")

        main_tab = self.main_window.main_tab

        # Check first frame label
        if hasattr(main_tab, "first_frame_label"):
            first_pixmap = main_tab.first_frame_label.pixmap()
            if first_pixmap is None:
                issue = "CRITICAL: first_frame_label.pixmap() is None"
                LOGGER.error(issue)
                self.issues_found.append(issue)
            elif first_pixmap.isNull():
                issue = "CRITICAL: first_frame_label pixmap is null/empty"
                LOGGER.error(issue)
                self.issues_found.append(issue)
            else:
                LOGGER.info("First frame label pixmap OK: %dx%d", first_pixmap.width(), first_pixmap.height())

                # Check for processed_image attribute
                if not hasattr(main_tab.first_frame_label, "processed_image"):
                    issue = "WARNING: first_frame_label missing processed_image attribute"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                elif main_tab.first_frame_label.processed_image is None:
                    issue = "WARNING: first_frame_label.processed_image is None"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                else:
                    LOGGER.debug("First frame processed_image OK")

        # Check last frame label
        if hasattr(main_tab, "last_frame_label"):
            last_pixmap = main_tab.last_frame_label.pixmap()
            if last_pixmap is None:
                issue = "CRITICAL: last_frame_label.pixmap() is None"
                LOGGER.error(issue)
                self.issues_found.append(issue)
            elif last_pixmap.isNull():
                issue = "CRITICAL: last_frame_label pixmap is null/empty"
                LOGGER.error(issue)
                self.issues_found.append(issue)
            else:
                LOGGER.info("Last frame label pixmap OK: %dx%d", last_pixmap.width(), last_pixmap.height())

                # Check for processed_image attribute
                if not hasattr(main_tab.last_frame_label, "processed_image"):
                    issue = "WARNING: last_frame_label missing processed_image attribute"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                elif main_tab.last_frame_label.processed_image is None:
                    issue = "WARNING: last_frame_label.processed_image is None"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                else:
                    LOGGER.debug("Last frame processed_image OK")

        # Check middle frame label if it exists
        if hasattr(main_tab, "middle_frame_label"):
            middle_pixmap = main_tab.middle_frame_label.pixmap()
            if middle_pixmap is None:
                issue = "INFO: middle_frame_label.pixmap() is None (may be expected)"
                LOGGER.info(issue)
            elif middle_pixmap.isNull():
                issue = "INFO: middle_frame_label pixmap is null/empty (may be expected)"
                LOGGER.info(issue)
            else:
                LOGGER.info("Middle frame label pixmap OK: %dx%d", middle_pixmap.width(), middle_pixmap.height())

    def _validate_image_data_integrity(self) -> None:
        """Validate that image data matches expected characteristics."""
        LOGGER.debug("Validating image data integrity...")

        preview_manager = self.main_window.main_view_model.preview_manager
        first_data, _middle_data, last_data = preview_manager.get_current_frame_data()

        # Validate first frame data
        if first_data and first_data.image_data is not None:
            first_array = first_data.image_data
            if hasattr(first_array, "shape"):
                expected_shape = (200, 300, 3)  # Height, Width, Channels
                if first_array.shape != expected_shape:
                    issue = f"First frame shape mismatch: expected {expected_shape}, got {first_array.shape}"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                else:
                    LOGGER.debug("First frame shape OK: %s", first_array.shape)
            else:
                issue = "First frame data has no shape attribute"
                LOGGER.warning(issue)
                self.issues_found.append(issue)

        # Validate last frame data
        if last_data and last_data.image_data is not None:
            last_array = last_data.image_data
            if hasattr(last_array, "shape"):
                expected_shape = (200, 300, 3)  # Height, Width, Channels
                if last_array.shape != expected_shape:
                    issue = f"Last frame shape mismatch: expected {expected_shape}, got {last_array.shape}"
                    LOGGER.warning(issue)
                    self.issues_found.append(issue)
                else:
                    LOGGER.debug("Last frame shape OK: %s", last_array.shape)
            else:
                issue = "Last frame data has no shape attribute"
                LOGGER.warning(issue)
                self.issues_found.append(issue)

    def _test_error_conditions(self) -> None:
        """Test various error conditions to ensure robust error handling."""
        LOGGER.debug("Testing error conditions...")

        # Test with empty directory
        empty_dir = self.test_dir / "empty"
        empty_dir.mkdir()

        # This should not crash and should handle the error gracefully
        try:
            self.main_window.set_in_dir(empty_dir)
            self._wait_for_preview_processing()
            LOGGER.debug("Empty directory handling completed without crash")
        except Exception as e:
            issue = f"Exception when handling empty directory: {e}"
            LOGGER.exception(issue)
            self.issues_found.append(issue)

        # Test with non-existent directory
        non_existent_dir = self.test_dir / "does_not_exist"

        try:
            self.main_window.set_in_dir(non_existent_dir)
            self._wait_for_preview_processing()
            LOGGER.debug("Non-existent directory handling completed without crash")
        except Exception as e:
            issue = f"Exception when handling non-existent directory: {e}"
            LOGGER.exception(issue)
            self.issues_found.append(issue)

    @property
    def main_tab(self):
        """Get the main tab for convenience."""
        return self.main_window.main_tab

    def test_preview_display_with_sanchez_processing(self) -> None:
        """Test preview display when Sanchez processing is enabled."""
        LOGGER.info("=== TESTING PREVIEW WITH SANCHEZ PROCESSING ===")

        # Enable Sanchez processing if checkbox exists
        if hasattr(self.main_tab, "sanchez_false_colour_checkbox"):
            self.main_tab.sanchez_false_colour_checkbox.setChecked(True)
            LOGGER.info("Enabled Sanchez false colour processing")
        elif hasattr(self.main_tab, "sanchez_checkbox"):
            self.main_tab.sanchez_checkbox.setChecked(True)
            LOGGER.info("Enabled Sanchez processing")
        else:
            LOGGER.warning("No Sanchez checkbox found - skipping Sanchez test")
            return

        # Set input directory
        self.main_window.set_in_dir(self.test_dir)
        self._wait_for_preview_processing()

        # Validate that processing still works with Sanchez enabled
        self._validate_preview_manager_state()
        self._validate_gui_display_state()

        if self.issues_found:
            self.fail(f"Sanchez processing test found {len(self.issues_found)} issues: {self.issues_found}")

    def test_preview_display_with_cropping(self) -> None:
        """Test preview display when cropping is applied."""
        LOGGER.info("=== TESTING PREVIEW WITH CROPPING ===")

        # Set input directory first
        self.main_window.set_in_dir(self.test_dir)
        self._wait_for_preview_processing()

        # Apply crop rectangle
        crop_rect = (50, 50, 100, 100)  # x, y, width, height
        self.main_window.current_crop_rect = crop_rect

        # Trigger preview update with crop
        self.main_window._update_previews()
        self._wait_for_preview_processing()

        # Validate cropped preview
        self._validate_preview_manager_state()
        self._validate_gui_display_state()

        if self.issues_found:
            self.fail(f"Cropping test found {len(self.issues_found)} issues: {self.issues_found}")


if __name__ == "__main__":
    unittest.main()
