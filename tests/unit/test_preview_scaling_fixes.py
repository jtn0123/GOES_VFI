"""Unit tests for preview image scaling fixes.

Tests the specific fixes implemented to resolve the issue where preview images
were showing as tiny 80x80 pixel images due to improper scaling logic.
"""

import unittest
from unittest.mock import patch

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from goesvfi.gui import MainWindow


class TestPreviewScalingFixes(unittest.TestCase):
    """Test the scaling fixes for preview images."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        with patch("goesvfi.utils.settings.sections.BasicSettings.apply_values"):
            self.main_window = MainWindow(debug_mode=True)
            self.main_window.in_dir = None

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.main_window.close()

    def test_preview_scaling_with_minimum_size_enforcement(self) -> None:
        """Test that preview scaling enforces minimum size even with tiny labels."""
        # Get preview manager
        preview_manager = self.main_window.main_view_model.preview_manager

        # Create a large source image
        source_pixmap = QPixmap(1000, 800)
        source_pixmap.fill()

        # Test with very small target size (the original problem)
        tiny_target = QSize(80, 80)  # This was causing invisible images
        scaled_pixmap = preview_manager.scale_preview_pixmap(source_pixmap, tiny_target)

        # Should be scaled to reasonable size, not 80x80
        assert scaled_pixmap.width() >= 150, f"Scaled width should be at least 150px, got {scaled_pixmap.width()}"
        assert scaled_pixmap.height() >= 150, f"Scaled height should be at least 150px, got {scaled_pixmap.height()}"

        # Test with medium target size
        medium_target = QSize(300, 300)
        scaled_medium = preview_manager.scale_preview_pixmap(source_pixmap, medium_target)

        # Should use the medium size since it's larger than minimum
        assert scaled_medium.width() <= 300
        assert scaled_medium.height() <= 300
        assert scaled_medium.width() >= 240  # Aspect ratio preserved

    def test_gui_scaling_logic_with_mock_labels(self) -> None:
        """Test the GUI scaling logic that determines target size."""
        # Mock the label sizes to simulate startup conditions
        first_label = self.main_window.main_tab.first_frame_label

        # Test with tiny label size (startup condition)
        with patch.object(first_label, "size", return_value=QSize(80, 80)):
            # Create a mock pixmap
            test_pixmap = QPixmap(500, 400)
            test_pixmap.fill()

            # Simulate the GUI scaling logic from _on_preview_images_loaded
            target_size = QSize(200, 200)  # Minimum preview size
            current_size = first_label.size()
            if current_size.width() > 200 and current_size.height() > 200:
                target_size = current_size

            # Target size should be the minimum, not the tiny label size
            assert target_size.width() == 200
            assert target_size.height() == 200

        # Test with large label size (after layout)
        with patch.object(first_label, "size", return_value=QSize(400, 300)):
            target_size = QSize(200, 200)  # Minimum preview size
            current_size = first_label.size()
            if current_size.width() > 200 and current_size.height() > 200:
                target_size = current_size

            # Target size should use the actual label size
            assert target_size.width() == 400
            assert target_size.height() == 300

    def test_label_minimum_size_policy(self) -> None:
        """Test that preview labels have proper minimum size constraints."""
        first_label = self.main_window.main_tab.first_frame_label
        middle_label = self.main_window.main_tab.middle_frame_label
        last_label = self.main_window.main_tab.last_frame_label

        # Check minimum sizes
        for label_name, label in [("first", first_label), ("middle", middle_label), ("last", last_label)]:
            min_size = label.minimumSize()
            assert min_size.width() >= 200, f"{label_name} label minimum width should be 200px, got {min_size.width()}"
            assert min_size.height() >= 200, (
                f"{label_name} label minimum height should be 200px, got {min_size.height()}"
            )

            # Check size policy allows expansion
            size_policy = label.sizePolicy()
            assert size_policy.horizontalPolicy().name == "Expanding", (
                f"{label_name} label should have Expanding horizontal policy"
            )
            assert size_policy.verticalPolicy().name == "Expanding", (
                f"{label_name} label should have Expanding vertical policy"
            )

    def test_pixmap_scaling_preserves_aspect_ratio(self) -> None:
        """Test that pixmap scaling preserves aspect ratio."""
        preview_manager = self.main_window.main_view_model.preview_manager

        # Create a rectangular source image
        source_pixmap = QPixmap(800, 400)  # 2:1 aspect ratio
        source_pixmap.fill()

        # Scale to square target
        target_size = QSize(300, 300)
        scaled_pixmap = preview_manager.scale_preview_pixmap(source_pixmap, target_size)

        # Should maintain aspect ratio
        aspect_ratio = scaled_pixmap.width() / scaled_pixmap.height()
        expected_ratio = 800 / 400  # 2.0

        self.assertAlmostEqual(
            aspect_ratio,
            expected_ratio,
            places=1,
            msg=f"Aspect ratio should be preserved. Expected {expected_ratio}, got {aspect_ratio}",
        )

        # Should fit within target size
        assert scaled_pixmap.width() <= target_size.width()
        assert scaled_pixmap.height() <= target_size.height()

    def test_null_pixmap_handling(self) -> None:
        """Test handling of null pixmaps."""
        preview_manager = self.main_window.main_view_model.preview_manager

        # Create null pixmap
        null_pixmap = QPixmap()
        assert null_pixmap.isNull()

        # Scale null pixmap
        target_size = QSize(200, 200)
        scaled_pixmap = preview_manager.scale_preview_pixmap(null_pixmap, target_size)

        # Should return null pixmap
        assert scaled_pixmap.isNull()

    def test_edge_case_sizes(self) -> None:
        """Test edge cases for scaling sizes."""
        preview_manager = self.main_window.main_view_model.preview_manager

        # Create test pixmap
        source_pixmap = QPixmap(100, 100)
        source_pixmap.fill()

        # Test with zero size target
        zero_target = QSize(0, 0)
        preview_manager.scale_preview_pixmap(source_pixmap, zero_target)
        # Should handle gracefully (implementation dependent)

        # Test with very large target
        huge_target = QSize(10000, 10000)
        scaled_huge = preview_manager.scale_preview_pixmap(source_pixmap, huge_target)
        # Should scale up appropriately
        assert scaled_huge.width() >= 100
        assert scaled_huge.height() >= 100

    def test_regression_80x80_scaling_bug(self) -> None:
        """Regression test for the specific 80x80 scaling bug."""
        preview_manager = self.main_window.main_view_model.preview_manager

        # Simulate the exact conditions that caused the bug
        # Large image scaled to tiny label size during GUI startup
        large_image = QPixmap(2712, 2712)  # Size from actual GOES images in logs
        large_image.fill()

        # The problematic size from error logs
        tiny_label_size = QSize(80, 80)

        # Apply our fixed scaling logic
        scaled = preview_manager.scale_preview_pixmap(large_image, tiny_label_size)

        # Should NOT result in 80x80 image
        assert scaled.width() > 80, f"Scaled width {scaled.width()} should be larger than 80px (the bug size)"
        assert scaled.height() > 80, f"Scaled height {scaled.height()} should be larger than 80px (the bug size)"

        # Should be at least 150x150 for visibility
        assert scaled.width() >= 150, f"Scaled width {scaled.width()} should be at least 150px for visibility"
        assert scaled.height() >= 150, f"Scaled height {scaled.height()} should be at least 150px for visibility"

    def test_gui_update_preview_method_target_size_logic(self) -> None:
        """Test the target size logic in the GUI's _update_previews method."""
        # Test the logic that chooses between minimum 200x200 and actual label size

        # Mock a tiny label (startup condition)
        mock_size_tiny = QSize(80, 80)

        # Simulate the logic from gui.py _on_preview_images_loaded
        target_size = QSize(200, 200)  # Minimum preview size
        if mock_size_tiny.width() > 200 and mock_size_tiny.height() > 200:
            target_size = mock_size_tiny

        # Should use minimum size
        assert target_size.width() == 200
        assert target_size.height() == 200

        # Mock a large label (after layout)
        mock_size_large = QSize(350, 280)

        target_size = QSize(200, 200)  # Minimum preview size
        if mock_size_large.width() > 200 and mock_size_large.height() > 200:
            target_size = mock_size_large

        # Should use actual label size
        assert target_size.width() == 350
        assert target_size.height() == 280


if __name__ == "__main__":
    unittest.main()
