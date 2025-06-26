import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import pytest

from goesvfi.file_sorter.sorter_refactored import (
    DuplicateMode,
    FileSorter,
)

# --- Fixtures ---


@pytest.fixture
def sorter():
    """Returns a simple FileSorter instance with default settings."""
    return FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)


@pytest.fixture
def sorter_dirs(tmp_path):
    """Creates temporary source directory."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    return source_dir


@pytest.fixture
def create_files(sorter_dirs):
    """Creates date-named folders with PNG files inside.

    Returns:
        Tuple containing:
        - source_dir: Path object for the source directory.
        - files_details: Dict mapping *expected output filename* to its original source Path.
        - expected_structure: Dict mapping base filename to list of expected output filenames.
        - expected_copied_count: Integer count of files expected to be copied initially.
    """
    source_dir = sorter_dirs
    files_details_by_output: Dict[str, Dict[str, Any]] = {}
    expected_structure: Dict[str, List[str]] = {}
    # Structure: {folder_name: [file_base_name1, file_base_name2], ...}
    folder_files = {
        "2023-01-15_10-00-00": ["imageA", "imageB"],
        "2023-01-15_10-00-10": ["imageA"],  # Duplicate base name, different time
        "2024-05-20_12-30-00": ["imageC"],
        "invalid-date-folder": ["imageD"],  # Folder to be ignored
        "2023-01-15_10-00-00_extra": ["imageE"],  # Folder to be ignored (invalid format)
    }
    expected_copied_count = 0
    for folder_name, base_names in folder_files.items():
        folder_path = source_dir / folder_name
        folder_path.mkdir(exist_ok=True)
        # Check if folder name is valid according to sorter logic
        is_valid_folder = bool(re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", folder_name))
        folder_datetime_str = ""
        if is_valid_folder:
            try:
                # Validate and format date for expected output name
                dt_obj = datetime.strptime(folder_name, "%Y-%m-%d_%H-%M-%S")
                folder_datetime_str = dt_obj.strftime("%Y%m%dT%H%M%SZ")
            except ValueError:
                is_valid_folder = False

        for i, base_name in enumerate(base_names):
            source_file_name = f"{base_name}.png"
            source_file_path = folder_path / source_file_name
            source_file_path.write_text(f"Content of {folder_name}/{source_file_name}")
            timestamp = time.time()
            os.utime(source_file_path, (timestamp - i * 10, timestamp - i * 10))  # Ensure slightly different mtimes

            if is_valid_folder:
                expected_copied_count += 1
                expected_output_filename = f"{base_name}_{folder_datetime_str}.png"
                files_details_by_output[expected_output_filename] = {"path": source_file_path}
                if base_name not in expected_structure:
                    expected_structure[base_name] = []
                expected_structure[base_name].append(expected_output_filename)
            # else: File details are not stored if the folder is invalid

    # Add a non-png file to be ignored
    (source_dir / "2023-01-15_10-00-00" / "ignored.txt").write_text("ignore me")

    # Add an empty valid date folder
    (source_dir / "2022-12-31_23-59-59").mkdir(exist_ok=True)

    return (
        source_dir,
        files_details_by_output,
        expected_structure,
        expected_copied_count,
    )


# --- Test Class for Helper Functions ---


class TestFileSorterHelpers:
    """Test cases for the refactored FileSorter helper functions."""

    def test_validate_directories_existing(self, sorter, tmp_path):
        """Test validating existing directories."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        result_source, result_dest = sorter._validate_directories(str(source_dir), str(dest_dir))

        assert result_source == source_dir
        assert result_dest == dest_dir

    def test_validate_directories_nonexistent_source(self, sorter, tmp_path):
        """Test validating with non-existent source directory."""
        source_dir = tmp_path / "nonexistent"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            sorter._validate_directories(str(source_dir), str(dest_dir))

    def test_validate_directories_create_dest(self, sorter, tmp_path):
        """Test that destination directory is created if it doesn't exist."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        result_source, result_dest = sorter._validate_directories(str(source_dir), str(dest_dir))

        assert result_source == source_dir
        assert result_dest == dest_dir
        assert dest_dir.exists()

    def test_validate_directories_dest_not_dir(self, sorter, tmp_path):
        """Test validating when destination exists but is not a directory."""
        source_dir = tmp_path / "source"
        dest_file = tmp_path / "dest_file"
        source_dir.mkdir()
        dest_file.write_text("not a directory")

        with pytest.raises(NotADirectoryError):
            sorter._validate_directories(str(source_dir), str(dest_file))

    def test_check_for_cancellation_false(self, sorter):
        """Test cancellation check when no cancellation is requested."""
        # No cancellation callback set
        assert not sorter._check_for_cancellation()

        # Cancellation callback returns False
        sorter._should_cancel = lambda: False
        assert not sorter._check_for_cancellation()

    def test_check_for_cancellation_true(self, sorter):
        """Test cancellation check when cancellation is requested."""
        sorter._should_cancel = lambda: True
        assert sorter._check_for_cancellation()

    def test_update_progress_no_callback(self, sorter):
        """Test progress update with no callback set."""
        # This shouldn't raise any errors
        sorter._update_progress(5, 10)

    def test_update_progress_with_callback(self, sorter):
        """Test progress update with callback set."""
        mock_callback = mock.Mock()
        sorter._progress_callback = mock_callback

        sorter._update_progress(5, 10)

        mock_callback.assert_called_once_with(5, 10)

    def test_is_valid_date_folder_valid(self, sorter):
        """Test folder name validation with valid date folders."""
        valid_folders = [
            "2023-01-15_10-00-00",
            "2024-05-20_12-30-00",
            "2022-12-31_23-59-59",
        ]

        for folder in valid_folders:
            assert sorter._is_valid_date_folder(folder)

    def test_is_valid_date_folder_invalid(self, sorter):
        """Test folder name validation with invalid date folders."""
        invalid_folders = [
            "invalid-date-folder",
            "2023-01-15_10-00-00_extra",
            "2023-13-15_10-00-00",  # Invalid month
            "2023-01-32_10-00-00",  # Invalid day
            "2023-01-15_24-00-00",  # Invalid hour
            "2023-01-15_10-60-00",  # Invalid minute
            "2023-01-15_10-00-60",  # Invalid second
            "2023-01-15-10-00-00",  # Wrong separator
            "20230115_100000",  # Wrong format
            "2023-01-15_10:00:00",  # Wrong separator
            "",  # Empty string
        ]

        for folder in invalid_folders:
            assert not sorter._is_valid_date_folder(folder)

    def test_collect_date_folders(self, sorter, create_files):
        """Test collecting date folders from source directory."""
        source_dir, _, _, _ = create_files

        date_folders = sorter._collect_date_folders(source_dir)

        # Should find all 5 folders + the empty one we added
        assert len(date_folders) == 6

        # Check that all the expected folders are in the result
        folder_names = {folder.name for folder in date_folders}
        expected_folder_names = {
            "2023-01-15_10-00-00",
            "2023-01-15_10-00-10",
            "2024-05-20_12-30-00",
            "invalid-date-folder",
            "2023-01-15_10-00-00_extra",
            "2022-12-31_23-59-59",
        }
        assert folder_names == expected_folder_names

    def test_get_folder_datetime_valid(self, sorter):
        """Test extracting datetime string from valid folder names."""
        test_cases = [
            ("2023-01-15_10-00-00", "20230115T100000"),
            ("2022-12-31_23-59-59", "20221231T235959"),
            ("2024-05-20_12-30-00", "20240520T123000"),
        ]

        for folder_name, expected_dt in test_cases:
            folder = mock.Mock()
            folder.name = folder_name
            result = sorter._get_folder_datetime(folder)
            assert result == expected_dt

    def test_get_folder_datetime_invalid(self, sorter):
        """Test extracting datetime string from invalid folder names."""
        invalid_folders = [
            "invalid-date-folder",
            "2023-01-15_10-00-00_extra",
            "short",
            "",
        ]

        for folder_name in invalid_folders:
            folder = mock.Mock()
            folder.name = folder_name
            result = sorter._get_folder_datetime(folder)
            assert result is None

    def test_collect_files_to_process(self, sorter, create_files):
        """Test collecting files to process from date folders."""
        source_dir, _, _, expected_copied_count = create_files

        date_folders = sorter._collect_date_folders(source_dir)
        files_to_process = sorter._collect_files_to_process(date_folders)

        # Should find files only from valid date folders (3 folders, 4 files total)
        assert len(files_to_process) == expected_copied_count

        # Check format of returned data
        for file_path, folder_datetime in files_to_process:
            assert isinstance(file_path, Path)
            assert file_path.suffix == ".png"
            assert isinstance(folder_datetime, str)
            assert len(folder_datetime) == 15  # Format: "YYYYMMDDThhmmss"

    def test_collect_files_with_cancellation(self, sorter, create_files):
        """Test file collection with cancellation."""
        source_dir, _, _, _ = create_files

        # Set up cancellation after first folder
        cancel_called = [False]

        def should_cancel():
            if not cancel_called[0]:
                cancel_called[0] = True
                return False
            return True

        sorter._should_cancel = should_cancel
        date_folders = sorter._collect_date_folders(source_dir)
        files_to_process = sorter._collect_files_to_process(date_folders)

        # Should return empty list on cancellation
        assert files_to_process == []

    def test_prepare_target_path_normal(self, sorter, tmp_path):
        """Test preparing target path for a normal file."""
        source_file = Path("imageA.png")
        folder_datetime = "20230115T100000"
        dest_dir = tmp_path / "dest"

        target_folder, new_file_path, base_name = sorter._prepare_target_path(source_file, folder_datetime, dest_dir)

        assert target_folder == dest_dir / "imageA"
        assert new_file_path == dest_dir / "imageA" / "imageA_20230115T100000Z.png"
        assert base_name == "imageA"

    def test_prepare_target_path_already_formatted(self, sorter, tmp_path):
        """Test preparing target path for a file that already has datetime suffix."""
        source_file = Path("imageA_20230115T100000Z.png")
        folder_datetime = "20230115T100000"
        dest_dir = tmp_path / "dest"

        target_folder, new_file_path, base_name = sorter._prepare_target_path(source_file, folder_datetime, dest_dir)

        assert target_folder == dest_dir / "imageA"
        assert new_file_path == dest_dir / "imageA" / "imageA_20230115T100000Z.png"
        assert base_name == "imageA"

    def test_check_files_identical_nonexistent(self, sorter, tmp_path):
        """Test checking for identical files when destination doesn't exist."""
        source_file = tmp_path / "source.png"
        source_file.write_text("source content")
        source_mtime = time.time()
        os.utime(source_file, (source_mtime, source_mtime))

        dest_file = tmp_path / "dest.png"  # Does not exist

        identical, size, mtime = sorter._check_files_identical(source_file, dest_file)

        assert not identical
        assert size == len("source content")
        assert abs(mtime - source_mtime) < 0.1
        assert sorter.files_skipped == 0  # Should not increment the skipped counter

    def test_check_files_identical_same(self, sorter, tmp_path):
        """Test checking for identical files when they are the same size and mtime."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("same content")
        dest_file.write_text("same content")

        source_mtime = time.time()
        os.utime(source_file, (source_mtime, source_mtime))
        os.utime(dest_file, (source_mtime, source_mtime))

        identical, size, mtime = sorter._check_files_identical(source_file, dest_file)

        assert identical
        assert size == len("same content")
        assert abs(mtime - source_mtime) < 0.1
        assert sorter.files_skipped == 1  # Should increment the skipped counter

    def test_check_files_identical_different_size(self, sorter, tmp_path):
        """Test checking for identical files when they have different sizes."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("source content")
        dest_file.write_text("different destination content")

        source_mtime = time.time()
        os.utime(source_file, (source_mtime, source_mtime))
        os.utime(dest_file, (source_mtime, source_mtime))

        identical, size, mtime = sorter._check_files_identical(source_file, dest_file)

        assert not identical
        assert size == len("source content")
        assert abs(mtime - source_mtime) < 0.1
        assert sorter.files_skipped == 0  # Should not increment the skipped counter

    def test_check_files_identical_different_mtime(self, sorter, tmp_path):
        """Test checking for identical files when they have same size but different mtime."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("same content")
        dest_file.write_text("same content")

        source_mtime = time.time()
        dest_mtime = source_mtime - 10  # 10 seconds difference, beyond tolerance

        os.utime(source_file, (source_mtime, source_mtime))
        os.utime(dest_file, (dest_mtime, dest_mtime))

        identical, size, mtime = sorter._check_files_identical(source_file, dest_file)

        assert not identical
        assert size == len("same content")
        assert abs(mtime - source_mtime) < 0.1
        assert sorter.files_skipped == 0  # Should not increment the skipped counter

    def test_check_files_identical_custom_tolerance(self, sorter, tmp_path):
        """Test checking for identical files with custom mtime tolerance."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("same content")
        dest_file.write_text("same content")

        source_mtime = time.time()
        dest_mtime = source_mtime - 5  # 5 seconds difference

        os.utime(source_file, (source_mtime, source_mtime))
        os.utime(dest_file, (dest_mtime, dest_mtime))

        # With default tolerance (1 second), should not be identical
        identical, _, _ = sorter._check_files_identical(source_file, dest_file)
        assert not identical

        # With custom tolerance (10 seconds), should be identical
        identical, _, _ = sorter._check_files_identical(source_file, dest_file, 10.0)
        assert identical


@pytest.mark.parametrize(
    "mode,precreate,expected,expected_msg,skipped",
    [
        (DuplicateMode.SKIP, [], None, "SKIPPED (Duplicate)", 1),
        (DuplicateMode.OVERWRITE, [], "file.png", "OVERWRITING file.png", 0),
        (DuplicateMode.RENAME, [], "file_1.png", "RENAMED to file_1.png", 0),
        (
            DuplicateMode.RENAME,
            ["file_1.png", "file_2.png"],
            "file_3.png",
            "RENAMED to file_3.png",
            0,
        ),
    ],
)
def test_handle_duplicate_modes(sorter, tmp_path, mode, precreate, expected, expected_msg, skipped):
    sorter.duplicate_mode = mode
    file_path = tmp_path / "file.png"
    file_path.touch()
    for name in precreate:
        (tmp_path / name).touch()
    result_path, message = sorter._handle_duplicate(file_path)
    if expected is None:
        assert result_path is None
    else:
        assert result_path == tmp_path / expected
    assert message == expected_msg
    assert sorter.files_skipped == skipped

    def test_process_single_file_identical(self, sorter, tmp_path):
        """Test processing a single file when files are identical."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("content")
        source_mtime = time.time()
        source_size = len("content")

        message = sorter._process_single_file(
            source_file,
            dest_file,
            source_mtime,
            source_size,
            True,  # files_are_identical=True
        )

        assert message == "SKIPPED (Identical)"
        assert sorter.files_copied == 0

    def test_process_single_file_new(self, sorter, tmp_path):
        """Test processing a new file (no duplicate)."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("content")
        source_mtime = time.time()
        source_size = len("content")

        # Create directory for dest_file
        dest_file.parent.mkdir(exist_ok=True)

        # Mock the copy function to avoid actual copying
        with mock.patch.object(sorter, "copy_file_with_buffer") as mock_copy:
            message = sorter._process_single_file(
                source_file,
                dest_file,
                source_mtime,
                source_size,
                False,  # files_are_identical=False
            )

            mock_copy.assert_called_once_with(source_file, dest_file, source_mtime)

        assert message == "COPIED to dest.png"
        assert sorter.files_copied == 1
        assert sorter.total_bytes_copied == source_size

    def test_process_single_file_dry_run(self, sorter, tmp_path):
        """Test processing a file in dry run mode."""
        sorter.dry_run = True
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("content")
        source_mtime = time.time()
        source_size = len("content")

        # Mock the copy function to ensure it's not called
        with mock.patch.object(sorter, "copy_file_with_buffer") as mock_copy:
            message = sorter._process_single_file(
                source_file,
                dest_file,
                source_mtime,
                source_size,
                False,  # files_are_identical=False
            )

            mock_copy.assert_not_called()

        assert message == "DRY RUN: Would copy to dest.png"
        assert sorter.files_copied == 0
        assert sorter.total_bytes_copied == 0

    def test_process_single_file_duplicate_skip(self, sorter, tmp_path):
        """Test processing a file with duplicate in SKIP mode."""
        sorter.duplicate_mode = DuplicateMode.SKIP
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        source_file.write_text("content")
        dest_file.parent.mkdir(exist_ok=True)
        dest_file.touch()  # Create the destination file

        source_mtime = time.time()
        source_size = len("content")

        # Mock the handle_duplicate function to control its behavior
        with mock.patch.object(sorter, "_handle_duplicate") as mock_handle:
            mock_handle.return_value = (None, "SKIPPED (Duplicate)")

            message = sorter._process_single_file(
                source_file,
                dest_file,
                source_mtime,
                source_size,
                False,  # files_are_identical=False
            )

            mock_handle.assert_called_once_with(dest_file)

        assert message == "SKIPPED (Duplicate)"

    def test_generate_stats(self, sorter):
        """Test generating statistics for the sorting operation."""
        sorter.files_copied = 5
        sorter.files_skipped = 3
        sorter.total_bytes_copied = 1024 * 1024  # 1 MB

        start_time = datetime.now()
        stats = sorter._generate_stats(start_time)

        assert stats["files_copied"] == 5
        assert stats["files_skipped"] == 3
        assert stats["total_bytes"] == 1024 * 1024
        assert stats["status"] == "completed"
        assert "duration" in stats


# --- Main Test Class for sort_files ---


class TestFileSorterRefactored:
    """Test cases for the refactored FileSorter.sort_files function."""

    def test_basic_sort(self, sorter_dirs, create_files):
        """Test basic file sorting into base name folders."""
        source_dir, _, expected_structure, expected_copied = create_files

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        converted_dir = source_dir / "converted"
        assert converted_dir.exists()
        assert sorter.files_copied == expected_copied
        assert sorter.files_skipped == 0

        # Check expected structure in converted dir
        total_files_found = 0
        for base_name, expected_files in expected_structure.items():
            base_dir = converted_dir / base_name
            assert base_dir.exists()
            actual_files = {f.name for f in base_dir.iterdir()}
            assert actual_files == set(expected_files)
            total_files_found += len(actual_files)

        assert total_files_found == expected_copied

        # Check invalid folders were not processed
        assert not (converted_dir / "imageD").exists()
        assert not (converted_dir / "imageE").exists()
        # Check non-png was ignored
        assert not (converted_dir / "ignored.txt").exists()  # Ensure it's not in the root converted dir
        for base_name in expected_structure:
            assert not (converted_dir / base_name / "ignored.txt").exists()  # Ensure it's not in any sub-dir

    def test_sort_with_progress_callback(self, sorter_dirs, create_files):
        """Test sort_files with progress callback."""
        source_dir, _, _, _ = create_files

        progress_callback = mock.Mock()

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)
        sorter.sort_files(
            source=str(source_dir),
            destination=str(source_dir / "converted"),
            progress_callback=progress_callback,
        )

        # Check that progress callback was called multiple times
        assert progress_callback.call_count > 0

    def test_sort_with_cancellation(self, sorter_dirs, create_files):
        """Test sort_files with cancellation callback."""
        source_dir, _, _, _ = create_files

        # Cancel after the first directory scan
        cancel_called = [False]

        def should_cancel():
            if not cancel_called[0]:
                cancel_called[0] = True
                return False
            return True

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)
        result = sorter.sort_files(
            source=str(source_dir),
            destination=str(source_dir / "converted"),
            should_cancel=should_cancel,
        )

        # Check result indicates cancellation
        assert result["status"] == "cancelled"

    def test_sort_with_error(self, sorter_dirs):
        """Test sort_files when an error occurs."""
        source_dir = sorter_dirs

        # Create a mock to throw an exception during processing
        with mock.patch.object(FileSorter, "_collect_date_folders", side_effect=Exception("Test error")):
            sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)
            result = sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

            # Check result indicates error
            assert result["status"] == "error"
            assert result["error_message"] == "Test error"

    def test_copy_file_with_buffer(self, sorter, tmp_path):
        """Test the buffered file copy functionality."""
        source_file = tmp_path / "source.png"
        dest_file = tmp_path / "dest.png"

        # Create source file with some content
        test_content = "Test content" * 100  # Make it large enough to test buffering
        source_file.write_text(test_content)

        # Set a specific mtime
        source_mtime = time.time()
        os.utime(source_file, (source_mtime, source_mtime))

        # Ensure dest parent directory exists
        dest_file.parent.mkdir(exist_ok=True)

        # Copy the file
        sorter.copy_file_with_buffer(source_file, dest_file, source_mtime)

        # Verify the copy succeeded
        assert dest_file.exists()
        assert dest_file.read_text() == test_content

        # Verify the mtime was preserved
        assert abs(dest_file.stat().st_mtime - source_mtime) < 0.1
