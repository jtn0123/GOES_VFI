"""
Unit tests for loader functionality - Optimized v2.

Optimizations applied:
- Shared expensive file system setup operations
- Parameterized test methods for comprehensive coverage
- Combined related test scenarios
- Reduced redundant directory and file creation
- Enhanced fixture reuse
- Performance testing with larger datasets
"""

from pathlib import Path

import pytest

from goesvfi.pipeline import loader


class TestLoaderV2:
    """Optimized test class for loader functionality."""

    @pytest.fixture(scope="class")
    def shared_file_data(self) -> dict[str, list[str]]:  # noqa: PLR6301
        """Create shared file data for all test methods.

        Returns:
            dict[str, list[str]]: Test file data organized by category.
        """
        return {
            "supported_extensions": [".png", ".jpg", ".jpeg"],
            "unsupported_extensions": [".bmp", ".gif", ".txt", ".zip", ".nc"],
            "supported_files": ["frame1.png", "frame2.jpg", "frame3.jpeg"],
            "unsupported_files": ["frame4.bmp", "frame5.gif", "frame6.txt"],
            "case_variations": ["frame1.PNG", "frame2.JpG", "frame3.JPEG"],
            "timestamp_files": ["20230101_0000.png", "20230101_0001.png", "20230101_0002.png"],
            "complex_names": [
                "goes16_20230615_123000_band13.png",
                "satellite_data_2023_06_15.jpg",
                "frame_001_processed.jpeg",
                "final_output_v2.png",
            ],
        }

    @pytest.fixture()
    def temp_dir_with_files(self, tmp_path: Path, shared_file_data: dict[str, list[str]]) -> Path:  # noqa: PLR6301
        """Create temporary directory with various file types.

        Returns:
            Path: Temporary directory path with test files.
        """
        # Create all test files efficiently
        all_files = (
            shared_file_data["supported_files"]
            + shared_file_data["unsupported_files"]
            + shared_file_data["case_variations"]
            + shared_file_data["timestamp_files"]
            + shared_file_data["complex_names"]
        )

        for filename in all_files:
            (tmp_path / filename).write_text("dummy content")

        return tmp_path

    @pytest.mark.parametrize(
        "file_group,should_be_included",
        [
            ("supported_files", True),
            ("unsupported_files", False),
            ("case_variations", True),  # Should handle case insensitive
        ],
    )
    def test_discover_frames_extension_filtering(
        self, tmp_path: Path, shared_file_data: dict[str, list[str]], file_group: str, *, should_be_included: bool
    ) -> None:
        """Test that only supported extensions are returned."""
        # Create only the files for this specific test to avoid conflicts
        test_files = shared_file_data[file_group]
        
        for filename in test_files:
            (tmp_path / filename).write_text("dummy content")
        
        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        for filename in test_files:
            if should_be_included:
                assert filename in result_filenames, f"Supported file {filename} should be included. Found: {result_filenames}"
            else:
                assert filename not in result_filenames, f"Unsupported file {filename} should be excluded"

    def test_discover_frames_sorted_order_comprehensive(
        self, tmp_path: Path, shared_file_data: dict[str, list[str]]
    ) -> None:
        """Test that files are returned in sorted lexicographic order."""
        # Create files in random order but expect sorted output
        unsorted_files = [
            "20230101_0002.png",
            "20230101_0000.png",
            "20230101_0001.png",
            "20230102_0000.png",
            "20221231_2359.png",
        ]

        for filename in unsorted_files:
            (tmp_path / filename).write_text("dummy content")

        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        # Should be sorted lexicographically
        expected_order = sorted(unsorted_files)
        assert result_filenames == expected_order

    @pytest.mark.parametrize("directory_scenario", ["empty", "only_directories", "mixed_content"])
    def test_discover_frames_edge_cases(self, tmp_path: Path, directory_scenario: str) -> None:  # noqa: PLR6301
        """Test edge cases for frame discovery."""
        if directory_scenario == "empty":
            # Directory is already empty
            pass
        elif directory_scenario == "only_directories":
            # Create subdirectories but no files
            (tmp_path / "subdir1").mkdir()
            (tmp_path / "subdir2").mkdir()
        elif directory_scenario == "mixed_content":
            # Mix of files and directories
            (tmp_path / "valid_frame.png").write_text("content")
            (tmp_path / "subdir").mkdir()
            (tmp_path / "invalid_file.txt").write_text("content")

        result = loader.discover_frames(tmp_path)

        if directory_scenario in {"empty", "only_directories"}:
            assert result == [], f"Should return empty list for {directory_scenario}"
        elif directory_scenario == "mixed_content":
            assert len(result) == 1
            assert result[0].name == "valid_frame.png"

    def test_discover_frames_case_insensitive_comprehensive(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test comprehensive case insensitive extension handling."""
        case_variations = [
            "frame1.PNG",
            "frame2.Png",
            "frame3.pNg",
            "frame4.JPG",
            "frame5.jPeG",
            "frame6.Jpg",
            "invalid.BMP",  # Unsupported even with case variation
            "invalid.TXT",  # Unsupported even with case variation
        ]

        for filename in case_variations:
            (tmp_path / filename).write_text("dummy content")

        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        # Should include all supported extensions regardless of case
        expected_supported = ["frame1.PNG", "frame2.Png", "frame3.pNg", "frame4.JPG", "frame5.jPeG", "frame6.Jpg"]

        for filename in expected_supported:
            assert filename in result_filenames

        # Should exclude unsupported extensions
        assert "invalid.BMP" not in result_filenames
        assert "invalid.TXT" not in result_filenames

    def test_discover_frames_performance_large_dataset(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test performance with larger dataset."""
        # Create larger dataset (100 files)
        supported_files = []
        unsupported_files = []

        for i in range(50):
            # Supported files
            png_file = f"frame_{i:03d}.png"
            jpg_file = f"image_{i:03d}.jpg"
            supported_files.extend([png_file, jpg_file])

            # Unsupported files
            txt_file = f"data_{i:03d}.txt"
            bmp_file = f"bitmap_{i:03d}.bmp"
            unsupported_files.extend([txt_file, bmp_file])

        # Create all files
        all_files = supported_files + unsupported_files
        for filename in all_files:
            (tmp_path / filename).write_text("content")

        # Test discovery
        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        # Should only include supported files
        assert len(result_filenames) == len(supported_files)

        for filename in supported_files:
            assert filename in result_filenames

        for filename in unsupported_files:
            assert filename not in result_filenames

        # Should be sorted
        assert result_filenames == sorted(supported_files)

    @pytest.mark.parametrize(
        "special_characters,should_work",
        [
            ("frame with spaces.png", True),
            ("frame-with-dashes.jpg", True),
            ("frame_with_underscores.jpeg", True),
            ("frame.with.dots.png", True),
            ("frame(with)parentheses.jpg", True),
            ("frame[with]brackets.png", True),
        ],
    )
    def test_discover_frames_special_filenames(
        self, tmp_path: Path, special_characters: str, should_work: bool
    ) -> None:
        """Test handling of filenames with special characters."""
        # Create file with special characters
        (tmp_path / special_characters).write_text("content")

        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        if should_work:
            assert special_characters in result_filenames
        else:
            assert special_characters not in result_filenames

    def test_discover_frames_subdirectory_exclusion(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test that files in subdirectories are not included."""
        # Create files in main directory
        (tmp_path / "main_frame.png").write_text("content")
        (tmp_path / "main_image.jpg").write_text("content")

        # Create subdirectory with files
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "sub_frame.png").write_text("content")
        (subdir / "sub_image.jpg").write_text("content")

        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        # Should only include files from main directory
        assert "main_frame.png" in result_filenames
        assert "main_image.jpg" in result_filenames
        assert "sub_frame.png" not in result_filenames
        assert "sub_image.jpg" not in result_filenames
        assert len(result_filenames) == 2

    def test_discover_frames_error_handling(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test error handling with various edge cases."""
        # Test with non-existent directory
        non_existent = tmp_path / "does_not_exist"

        try:
            result = loader.discover_frames(non_existent)
            # If no exception, should return empty list
            assert result == []
        except (FileNotFoundError, OSError):
            # Expected behavior for non-existent directory
            pass

        # Test with file instead of directory
        test_file = tmp_path / "not_a_directory.txt"
        test_file.write_text("content")

        try:
            result = loader.discover_frames(test_file)
            # Should handle gracefully
            assert isinstance(result, list)
        except (NotADirectoryError, OSError):
            # Expected behavior when path is not a directory
            pass

    def test_discover_frames_return_type_consistency(
        self, tmp_path: Path, shared_file_data: dict[str, list[str]]
    ) -> None:
        """Test that return type is always consistent."""
        # Test with empty directory
        result_empty = loader.discover_frames(tmp_path)
        assert isinstance(result_empty, list)
        assert all(isinstance(item, Path) for item in result_empty)

        # Create some files
        for filename in shared_file_data["supported_files"]:
            (tmp_path / filename).write_text("content")

        # Test with files
        result_with_files = loader.discover_frames(tmp_path)
        assert isinstance(result_with_files, list)
        assert all(isinstance(item, Path) for item in result_with_files)
        assert len(result_with_files) > 0

    def test_discover_frames_path_object_handling(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test that function handles both string and Path objects."""
        # Create test files
        test_files = ["test1.png", "test2.jpg"]
        for filename in test_files:
            (tmp_path / filename).write_text("content")

        # Test with Path object
        result_path = loader.discover_frames(tmp_path)

        # Test with string path
        result_str = loader.discover_frames(str(tmp_path))

        # Results should be equivalent
        assert len(result_path) == len(result_str)

        result_path_names = [p.name for p in result_path]
        result_str_names = [p.name for p in result_str]

        assert result_path_names == result_str_names

    def test_discover_frames_hidden_files(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test handling of hidden files (starting with .)."""
        # Create visible and hidden files
        (tmp_path / "visible.png").write_text("content")
        (tmp_path / ".hidden.png").write_text("content")
        (tmp_path / "..double_hidden.jpg").write_text("content")

        result = loader.discover_frames(tmp_path)
        result_filenames = [p.name for p in result]

        # Implementation dependent - document current behavior
        # Most implementations include hidden files, but this may vary
        visible_count = sum(1 for name in result_filenames if not name.startswith("."))
        assert visible_count >= 1  # At least the visible file should be included

    def test_discover_frames_duplicate_handling(self, tmp_path: Path) -> None:  # noqa: PLR6301
        """Test that no duplicates are returned."""
        # Create files
        test_files = ["frame1.png", "frame2.jpg", "frame3.png"]
        for filename in test_files:
            (tmp_path / filename).write_text("content")

        # Call discover_frames multiple times
        result1 = loader.discover_frames(tmp_path)
        result2 = loader.discover_frames(tmp_path)

        # Results should be identical
        assert len(result1) == len(result2)
        assert [p.name for p in result1] == [p.name for p in result2]

        # No duplicates within a single result
        result_names = [p.name for p in result1]
        assert len(result_names) == len(set(result_names))

    @pytest.mark.parametrize(
        "extension_case,expected_count",
        [
            ([".png", ".jpg"], 2),
            ([".PNG", ".JPG"], 2),  # Should work with uppercase
            ([".pNg", ".JpG"], 2),  # Should work with mixed case
        ],
    )
    def test_discover_frames_extension_case_matrix(
        self, tmp_path: Path, extension_case: list[str], expected_count: int
    ) -> None:
        """Test extension matching with various case combinations."""
        # Create files with specific extensions
        base_name = "test"
        for i, ext in enumerate(extension_case):
            filename = f"{base_name}_{i}{ext}"
            (tmp_path / filename).write_text("content")

        result = loader.discover_frames(tmp_path)
        assert len(result) == expected_count


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
