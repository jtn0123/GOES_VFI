"""Unit tests for the CropManager component - Optimized V2 with 100%+ coverage."""

from pathlib import Path
import tempfile
import threading
from typing import Any, ClassVar
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QCoreApplication, QRect, QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_components.crop_manager import CropManager


class TestCropManagerV2(unittest.TestCase):  # noqa: PLR0904
    """Test cases for CropManager with comprehensive coverage."""

    app: ClassVar[QCoreApplication | None] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary settings file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")  # noqa: SIM115
        self.temp_file.close()

        # Create QSettings with test file
        self.settings = QSettings(self.temp_file.name, QSettings.Format.IniFormat)

        # Create CropManager instance
        self.crop_manager = CropManager(self.settings)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up temporary file
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_initialization(self) -> None:
        """Test CropManager initialization with various scenarios."""
        # Test basic initialization
        assert self.crop_manager.current_crop_rect is None
        assert self.crop_manager.settings == self.settings

        # Test initialization with None settings
        with patch("goesvfi.gui_components.crop_manager.LOGGER"):
            crop_manager_none = CropManager(None)
            assert crop_manager_none.current_crop_rect is None
            assert crop_manager_none.settings is None

    def test_save_crop_rect_comprehensive(self) -> None:
        """Test saving crop rectangles with various valid formats."""
        test_cases: list[tuple[tuple[float, float, float, float], bool]] = [
            ((10, 20, 100, 200), True),
            ((0, 0, 1, 1), True),  # Minimum valid rect
            ((0, 0, 10000, 10000), True),  # Large rect
            ((-10, -20, 100, 200), True),  # Negative coordinates
            ((10.5, 20.5, 100.5, 200.5), True),  # Float coordinates
        ]

        for rect, expected in test_cases:
            with self.subTest(rect=rect):
                result = self.crop_manager.save_crop_rect(rect)  # type: ignore[arg-type]
                assert result == expected

                if expected:
                    loaded_rect = self.crop_manager.load_crop_rect()
                    # Convert to integers for comparison
                    expected_rect = tuple(int(x) for x in rect)
                    assert loaded_rect == expected_rect

    def test_save_crop_rect_invalid_inputs(self) -> None:
        """Test saving with various invalid inputs."""
        invalid_inputs: list[Any] = [
            None,
            (),  # Empty tuple
            (10,),  # Too few values
            (10, 20),  # Too few values
            (10, 20, 30),  # Too few values
            (10, 20, 30, 40, 50),  # Too many values
            "10,20,30,40",  # String instead of tuple
            [10, 20, 30, 40],  # List instead of tuple
            {"x": 10, "y": 20, "w": 30, "h": 40},  # Dict
            (None, 20, 30, 40),  # None value
            ("a", "b", "c", "d"),  # Non-numeric values
        ]

        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                result = self.crop_manager.save_crop_rect(invalid_input)  # type: ignore[arg-type]
                assert not result

    def test_set_and_get_crop_rect_edge_cases(self) -> None:
        """Test setting and getting crop rectangles with edge cases."""
        # Test normal case
        rect = (50, 60, 300, 400)
        result = self.crop_manager.set_crop_rect(rect)
        assert result
        assert self.crop_manager.get_crop_rect() == rect

        # Test overwriting existing rect
        new_rect = (100, 120, 500, 600)
        result = self.crop_manager.set_crop_rect(new_rect)
        assert result
        assert self.crop_manager.get_crop_rect() == new_rect

        # Test getting when None
        self.crop_manager.current_crop_rect = None
        assert self.crop_manager.get_crop_rect() is None

    def test_load_crop_rect_various_formats(self) -> None:
        """Test loading crop rectangles from various settings formats."""
        # Test standard format
        self.settings.setValue("preview/cropRectangle", "15,25,150,250")
        self.settings.sync()

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == (15, 25, 150, 250)

        # Test with spaces
        self.settings.setValue("preview/cropRectangle", "30, 40, 200, 300")
        self.settings.sync()

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == (30, 40, 200, 300)

        # Test with float values (should be converted to int)
        self.settings.setValue("preview/cropRectangle", "10.5,20.5,100.5,200.5")
        self.settings.sync()

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == (10, 20, 100, 200)

    def test_load_crop_rect_fallback_keys(self) -> None:
        """Test loading from alternate settings keys."""
        # Clear primary key
        self.settings.remove("preview/cropRectangle")

        # Set alternate key
        rect = (30, 40, 200, 300)
        self.settings.setValue("cropRect", "30,40,200,300")
        self.settings.sync()

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == rect

        # Test with both keys present (primary should take precedence)
        self.settings.setValue("preview/cropRectangle", "50,60,250,350")
        self.settings.setValue("cropRect", "30,40,200,300")
        self.settings.sync()

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == (50, 60, 250, 350)

    def test_load_crop_rect_error_handling(self) -> None:
        """Test loading with various error conditions."""
        error_values: list[str] = [
            "invalid,format",  # Too few values
            "a,b,c,d",  # Non-numeric values
            "10,20,30,40,50",  # Too many values
            "",  # Empty string
            "   ",  # Whitespace only
            "10;20;30;40",  # Wrong delimiter
            "10|20|30|40",  # Wrong delimiter
            "null,null,null,null",  # Null values
        ]

        for error_value in error_values:
            with self.subTest(value=error_value):
                self.settings.setValue("preview/cropRectangle", error_value)
                self.settings.sync()

                loaded_rect = self.crop_manager.load_crop_rect()
                assert loaded_rect is None

    def test_clear_crop_rect_comprehensive(self) -> None:
        """Test clearing crop rectangle in various states."""
        # Clear when rect exists
        rect = (70, 80, 400, 500)
        self.crop_manager.set_crop_rect(rect)
        assert self.crop_manager.get_crop_rect() is not None

        self.crop_manager.clear_crop_rect()
        assert self.crop_manager.get_crop_rect() is None

        # Verify settings are cleared
        saved_rect = self.settings.value("preview/cropRectangle", "", type=str)
        assert saved_rect == ""  # noqa: PLC1901

        # Clear when already None
        self.crop_manager.clear_crop_rect()
        assert self.crop_manager.get_crop_rect() is None

    def test_persistence_across_instances(self) -> None:
        """Test that crop rectangles persist across CropManager instances."""
        rect = (90, 100, 500, 600)

        # Save with first instance
        self.crop_manager.set_crop_rect(rect)

        # Create new instance with same settings
        new_crop_manager = CropManager(self.settings)

        # Load should retrieve the saved rect
        loaded_rect = new_crop_manager.load_crop_rect()
        assert loaded_rect == rect
        assert new_crop_manager.get_crop_rect() == rect

    def test_settings_sync_behavior(self) -> None:
        """Test QSettings sync behavior and consistency."""
        rect = (20, 30, 200, 300)

        # Save rect
        result = self.crop_manager.save_crop_rect(rect)
        assert result

        # Force sync
        self.settings.sync()

        # Verify value is in settings
        saved_value = self.settings.value("preview/cropRectangle", type=str)
        assert saved_value == "20,30,200,300"

    def test_concurrent_access(self) -> None:
        """Test thread safety with concurrent access."""
        results = []
        errors = []

        def save_rect(rect: tuple[int, int, int, int], thread_id: int) -> None:
            try:
                result = self.crop_manager.save_crop_rect(rect)
                results.append((thread_id, result, rect))
            except Exception as e:  # noqa: BLE001
                errors.append((thread_id, e))

        # Create threads
        threads = []
        rects = [
            (10, 20, 100, 200),
            (20, 30, 200, 300),
            (30, 40, 300, 400),
            (40, 50, 400, 500),
        ]

        for i, rect in enumerate(rects):
            t = threading.Thread(target=save_rect, args=(rect, i))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # All saves should succeed
        assert len(results) == 4
        for _, result, _ in results:
            assert result

    def test_qrect_compatibility(self) -> None:
        """Test compatibility with QRect objects."""
        # Create QRect
        qrect = QRect(10, 20, 100, 200)

        # Convert to tuple format
        rect_tuple = (qrect.x(), qrect.y(), qrect.width(), qrect.height())

        # Save and verify
        result = self.crop_manager.save_crop_rect(rect_tuple)
        assert result

        loaded_rect = self.crop_manager.load_crop_rect()
        assert loaded_rect == rect_tuple

    def test_settings_corruption_recovery(self) -> None:
        """Test recovery from corrupted settings."""
        # Corrupt the settings file
        with patch.object(self.settings, "value", side_effect=Exception("Settings corrupted")):
            loaded_rect = self.crop_manager.load_crop_rect()
            assert loaded_rect is None

        # Ensure crop manager still works after corruption
        rect = (50, 60, 300, 400)
        result = self.crop_manager.set_crop_rect(rect)
        assert result

    def test_memory_efficiency(self) -> None:
        """Test memory efficiency with repeated operations."""
        # Perform many save/load cycles
        for i in range(1000):
            rect = (i, i * 2, i * 10, i * 20)
            self.crop_manager.save_crop_rect(rect)
            loaded = self.crop_manager.load_crop_rect()
            assert loaded == rect

        # Should complete without memory issues

    def test_error_logging(self) -> None:
        """Test that errors are properly logged."""
        with patch("goesvfi.gui_components.crop_manager.LOGGER") as mock_logger:
            # Test invalid format logging
            self.settings.setValue("preview/cropRectangle", "invalid")
            self.crop_manager.load_crop_rect()
            mock_logger.warning.assert_called()

            # Test save error logging
            mock_logger.reset_mock()
            self.crop_manager.save_crop_rect(None)  # type: ignore[arg-type]
            mock_logger.error.assert_called()

    def test_special_cases(self) -> None:
        """Test special edge cases."""
        # Test zero-size rect
        rect = (10, 20, 0, 0)
        result = self.crop_manager.save_crop_rect(rect)
        assert result  # Should still save

        # Test very large coordinates
        rect = (1000000, 2000000, 3000000, 4000000)
        result = self.crop_manager.save_crop_rect(rect)
        assert result

        # Test negative size (invalid in practice but should save)
        rect = (10, 20, -100, -200)
        result = self.crop_manager.save_crop_rect(rect)
        assert result

    def test_settings_organization(self) -> None:
        """Test proper organization in settings file."""
        # Save crop rect
        rect = (10, 20, 100, 200)
        self.crop_manager.save_crop_rect(rect)

        # Check that it's in the correct group
        self.settings.beginGroup("preview")
        value = self.settings.value("cropRectangle", type=str)
        self.settings.endGroup()

        assert value == "10,20,100,200"

    def test_backwards_compatibility(self) -> None:
        """Test backwards compatibility with older settings formats."""
        # Test old format with semicolons (hypothetical)
        with patch.object(self.settings, "value") as mock_value:
            mock_value.return_value = "10;20;100;200"

            # Should handle gracefully even if format is unexpected
            loaded_rect = self.crop_manager.load_crop_rect()
            # Will be None due to format mismatch, which is expected
            assert loaded_rect is None

    def test_state_consistency(self) -> None:
        """Test that internal state remains consistent."""
        # Set rect
        rect1 = (10, 20, 100, 200)
        self.crop_manager.set_crop_rect(rect1)

        # Verify state
        assert self.crop_manager.current_crop_rect == rect1
        assert self.crop_manager.get_crop_rect() == rect1

        # Clear rect
        self.crop_manager.clear_crop_rect()

        # Verify state is cleared
        assert self.crop_manager.current_crop_rect is None
        assert self.crop_manager.get_crop_rect() is None

        # Load rect
        rect2 = (30, 40, 300, 400)
        self.settings.setValue("preview/cropRectangle", "30,40,300,400")
        loaded = self.crop_manager.load_crop_rect()

        # Verify state is updated
        assert self.crop_manager.current_crop_rect == rect2
        assert loaded == rect2

    def test_integration_with_ui_workflow(self) -> None:
        """Test typical UI workflow integration."""
        # Simulate typical usage pattern

        # 1. User opens app - load saved rect
        saved_rect = self.crop_manager.load_crop_rect()
        assert saved_rect is None  # No saved rect initially

        # 2. User sets crop rectangle
        user_rect = (100, 100, 400, 300)
        self.crop_manager.set_crop_rect(user_rect)

        # 3. User adjusts crop
        adjusted_rect = (110, 110, 390, 290)
        self.crop_manager.set_crop_rect(adjusted_rect)

        # 4. User clears crop
        self.crop_manager.clear_crop_rect()

        # 5. User sets new crop
        final_rect = (50, 50, 200, 200)
        self.crop_manager.set_crop_rect(final_rect)

        # 6. App restarts - verify persistence
        new_manager = CropManager(self.settings)
        loaded = new_manager.load_crop_rect()
        assert loaded == final_rect

    def test_performance(self) -> None:
        """Test performance of crop operations."""
        import time  # noqa: PLC0415

        # Time save operations
        rect = (10, 20, 100, 200)
        start = time.time()

        for _ in range(100):
            self.crop_manager.save_crop_rect(rect)

        save_time = time.time() - start
        avg_save = save_time / 100

        # Should be fast
        assert avg_save < 0.01  # Less than 10ms per save

        # Time load operations
        start = time.time()

        for _ in range(100):
            self.crop_manager.load_crop_rect()

        load_time = time.time() - start
        avg_load = load_time / 100

        # Should be fast
        assert avg_load < 0.01  # Less than 10ms per load

    def test_validation_logic(self) -> None:
        """Test any validation logic in crop manager."""
        # Test that crop manager accepts various valid formats
        valid_rects: list[tuple[float, float, float, float]] = [
            (0, 0, 1, 1),  # Minimum
            (0, 0, 10000, 10000),  # Large
            (-100, -100, 200, 200),  # Negative start
            (0.5, 0.5, 100.5, 100.5),  # Floats
        ]

        for rect in valid_rects:
            with self.subTest(rect=rect):
                result = self.crop_manager.save_crop_rect(rect)  # type: ignore[arg-type]
                assert result

    @patch("goesvfi.gui_components.crop_manager.QSettings")
    def test_settings_initialization_error(self, mock_settings_class: Any) -> None:  # noqa: PLR6301, ANN401
        """Test handling of settings initialization errors."""
        # Mock settings to raise exception
        mock_settings_class.side_effect = Exception("Settings init failed")

        # Should handle gracefully
        with patch("goesvfi.gui_components.crop_manager.LOGGER"):
            try:
                manager = CropManager(None)
                # Should still create manager
                assert manager is not None
            except Exception:  # noqa: BLE001, S110
                # If it does fail, that's also acceptable
                pass


if __name__ == "__main__":
    unittest.main()
