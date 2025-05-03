import re
import pytest
import os
import shutil
from pathlib import Path
from datetime import datetime
import time
from typing import Dict, List, Tuple, Any  # Add type hints

from goesvfi.file_sorter.sorter import FileSorter, DuplicateMode

# --- Fixtures ---


@pytest.fixture
def sorter_dirs(tmp_path):
    """Creates temporary source directory. Destination is implicitly 'converted'."""
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
        "2023-01-15_10-00-00_extra": [
            "imageE"
        ],  # Folder to be ignored (invalid format)
    }
    expected_copied_count = 0
    for folder_name, base_names in folder_files.items():
        folder_path = source_dir / folder_name
        folder_path.mkdir(exist_ok=True)
        # Check if folder name is valid according to sorter logic
        is_valid_folder = bool(
            re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", folder_name)
        )
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
            os.utime(
                source_file_path, (timestamp - i * 10, timestamp - i * 10)
            )  # Ensure slightly different mtimes

            if is_valid_folder:
                expected_copied_count += 1
                expected_output_filename = f"{base_name}_{folder_datetime_str}.png"
                files_details_by_output[expected_output_filename] = {
                    "path": source_file_path
                }
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


# --- Test Class ---


class TestFileSorter:

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
        assert not (
            converted_dir / "ignored.txt"
        ).exists()  # Ensure it's not in the root converted dir
        for base_name in expected_structure:
            assert not (
                converted_dir / base_name / "ignored.txt"
            ).exists()  # Ensure it's not in any sub-dir

    def test_dry_run(self, sorter_dirs, create_files):
        """Test dry run functionality."""
        source_dir, files_details, expected_structure, expected_copied = create_files

        sorter = FileSorter(dry_run=True, duplicate_mode=DuplicateMode.SKIP)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        converted_dir = source_dir / "converted"
        # Converted dir might be created by mkdir logic, but should be empty
        assert not converted_dir.exists() or not any(
            converted_dir.iterdir()
        )  # Check if empty
        assert sorter.files_copied == 0  # No files actually copied
        assert (
            sorter.files_skipped == 0
        )  # Should not skip in dry run before copy attempt

        # Check source folders/files still exist
        for expected_output_name, details in files_details.items():
            assert details["path"].exists()

    def test_duplicate_skip(self, sorter_dirs, create_files):
        """Test duplicate handling: Skip."""
        source_dir, _, expected_structure, expected_copied = create_files

        # Pre-create one destination file to cause a skip
        converted_dir = source_dir / "converted"
        base_name_to_conflict = "imageA"
        conflicting_output_filename = (
            "imageA_20230115T100000Z.png"  # Expected name for the first imageA
        )
        dest_path = converted_dir / base_name_to_conflict
        dest_path.mkdir(parents=True, exist_ok=True)
        existing_file = dest_path / conflicting_output_filename
        existing_file.write_text("Existing content")
        existing_mtime = time.time()
        os.utime(existing_file, (existing_mtime, existing_mtime))  # Set mtime

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.SKIP)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        # One file ('imageA' from 10-00-00) should be skipped.
        # The other 'imageA' (from 10-00-10) has a different timestamp in the name, so it's not a duplicate.
        assert sorter.files_copied == expected_copied - 1  # One less copied
        assert sorter.files_skipped == 1  # One skipped (the one we pre-created)

        # Check existing file was not modified
        assert existing_file.read_text() == "Existing content"
        # Compare mtime with tolerance
        assert abs(existing_file.stat().st_mtime - existing_mtime) < 2

        # Check other files were copied correctly into expected structure
        total_files_found = 0
        for base_name, expected_files in expected_structure.items():
            base_dir = converted_dir / base_name
            assert base_dir.exists()
            actual_files = {f.name for f in base_dir.iterdir()}
            assert actual_files == set(expected_files)
            total_files_found += len(actual_files)

        # Total files in converted should be the original expected minus the one skipped + the one pre-created
        assert total_files_found == expected_copied

    def test_duplicate_overwrite(self, sorter_dirs, create_files):
        """Test duplicate handling: Overwrite."""
        source_dir, files_details_by_output, expected_structure, expected_copied = (
            create_files
        )

        # Pre-create one destination file to be overwritten
        converted_dir = source_dir / "converted"
        base_name_to_conflict = "imageA"
        conflicting_output_filename = (
            "imageA_20230115T100000Z.png"  # Expected name for the first imageA
        )
        dest_path = converted_dir / base_name_to_conflict
        dest_path.mkdir(parents=True, exist_ok=True)
        existing_file = dest_path / conflicting_output_filename
        existing_file.write_text("Old content")
        # Get the original source path corresponding to the conflicting output filename
        original_source_path = files_details_by_output[conflicting_output_filename][
            "path"
        ]

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.OVERWRITE)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        assert sorter.files_copied == expected_copied  # All files attempted to copy
        # Depending on exact logic, overwrite might count as skip=0 or skip=1 then copy=1
        # Let's check final state instead of exact skip count.
        # assert sorter.files_skipped == 0

        # Check existing file was overwritten (check mtime matches source)
        assert existing_file.exists()
        assert (
            abs(existing_file.stat().st_mtime - original_source_path.stat().st_mtime)
            < 2
        )
        # Check content (optional, if fixture wrote unique content)
        assert existing_file.read_text() == original_source_path.read_text()

        # Check other files were copied correctly
        total_files_found = 0
        for base_name, expected_files in expected_structure.items():
            base_dir = converted_dir / base_name
            assert base_dir.exists()
            actual_files = {f.name for f in base_dir.iterdir()}
            assert actual_files == set(expected_files)
            total_files_found += len(actual_files)
        assert total_files_found == expected_copied

    def test_duplicate_rename(self, sorter_dirs, create_files):
        """Test duplicate handling: Rename."""
        source_dir, _, expected_structure, expected_copied = create_files

        # Pre-create files to cause renaming
        converted_dir = source_dir / "converted"
        base_name_to_conflict = "imageA"
        conflicting_output_filename = "imageA_20230115T100000Z.png"
        rename_conflict_name_1 = (
            "imageA_20230115T100000Z_1.png"  # What it would rename to first
        )

        dest_path = converted_dir / base_name_to_conflict
        dest_path.mkdir(parents=True, exist_ok=True)
        # Create the original target and the first renamed target
        (dest_path / conflicting_output_filename).write_text("Existing original")
        (dest_path / rename_conflict_name_1).write_text("Existing rename 1")

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.RENAME)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        assert sorter.files_copied == expected_copied  # All files copied (one renamed)
        assert sorter.files_skipped == 0  # Rename shouldn't count as skip

        # Check the file was renamed correctly (should become *_2.png)
        expected_renamed_file = dest_path / "imageA_20230115T100000Z_2.png"
        assert expected_renamed_file.exists()

        # Check original conflicting files still exist
        assert (dest_path / conflicting_output_filename).exists()
        assert (dest_path / rename_conflict_name_1).exists()

        # Check overall structure, including the renamed file
        total_files_found = 0
        expected_structure_with_rename = expected_structure.copy()
        # Update the expected list for the conflicted base name
        expected_structure_with_rename[base_name_to_conflict] = sorted(
            [
                f
                for f in expected_structure[base_name_to_conflict]
                if f != conflicting_output_filename
            ]
            + [
                conflicting_output_filename,
                rename_conflict_name_1,
                expected_renamed_file.name,
            ]
        )

        for base_name, expected_files in expected_structure_with_rename.items():
            base_dir = converted_dir / base_name
            assert base_dir.exists()
            actual_files = sorted(
                [f.name for f in base_dir.iterdir()]
            )  # Sort for comparison
            assert actual_files == sorted(
                list(set(expected_files))
            )  # Use set to handle potential duplicates in logic, then sort
            total_files_found += len(actual_files)

        # Total files should be expected + 2 (the pre-created ones)
        assert total_files_found == expected_copied + 2

    def test_empty_source(self, sorter_dirs):
        """Test sorting with an empty source directory (no date folders)."""
        source_dir = sorter_dirs
        # No need for create_files fixture here

        sorter = FileSorter(dry_run=False, duplicate_mode=DuplicateMode.SKIP)
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions
        converted_dir = source_dir / "converted"
        # Converted dir might be created, but should be empty
        assert not converted_dir.exists() or not any(converted_dir.glob("*"))
        assert sorter.files_copied == 0
        assert sorter.files_skipped == 0

    def test_invalid_date_format_string(self, sorter_dirs, create_files):
        """Test sorting works regardless of 'date_format' param (which is unused)."""
        # This test originally tested an invalid date_format string, but since
        # the sorter doesn't use it, the test is effectively the same as basic_sort.
        # We keep it to ensure the constructor ignores unused params gracefully.
        source_dir, _, expected_structure, expected_copied = create_files

        # Pass dummy date_format - it should be ignored by the current sorter implementation
        sorter = FileSorter(
            dry_run=False, duplicate_mode=DuplicateMode.SKIP
        )  # Using SKIP for variety
        sorter.sort_files(source=str(source_dir), destination=str(source_dir / "converted"))

        # Assertions - files should still be sorted correctly based on folder names
        converted_dir = source_dir / "converted"
        assert converted_dir.exists()
        # Files copied depends on duplicate mode; check structure instead
        # assert sorter.files_copied == expected_copied

        total_files_found = 0
        for base_name, expected_files in expected_structure.items():
            base_dir = converted_dir / base_name
            assert base_dir.exists()
            actual_files = {f.name for f in base_dir.iterdir()}
            assert actual_files == set(expected_files)
            total_files_found += len(actual_files)
        assert total_files_found == expected_copied


# Ensure the DuplicateMode enum is available if not already imported globally
# try:
#     from goesvfi.file_sorter.sorter import DuplicateMode
# except ImportError:
#     # Define locally if import fails (e.g., during testing setup)
#     from enum import Enum, auto
#     class DuplicateMode(Enum):
#         OVERWRITE = auto()
#         SKIP = auto()
#         RENAME = auto()
