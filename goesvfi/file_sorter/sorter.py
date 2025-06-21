#!/usr/bin/env python3

import os
import re
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class DuplicateMode(Enum):
    OVERWRITE = auto()
    SKIP = auto()
    RENAME = auto()


class FileSorter:
    def __init__(
        self,
        dry_run: bool = False,
        duplicate_mode: DuplicateMode = DuplicateMode.OVERWRITE,
    ):
        self.files_copied = 0
        self.files_skipped = 0
        self.total_bytes_copied = 0
        self.dry_run = dry_run
        self.duplicate_mode = duplicate_mode
        self._progress_callback: Optional[Callable[[int, int], None]] = None
        self._should_cancel: Optional[Callable[[], bool]] = None

    def copy_file_with_buffer(
        self,
        source_path: Path,
        dest_path: Path,
        source_mtime_utc: float,
        buffer_size: int = 1048576,
    ) -> None:
        """
        Copies a file in chunks (buffered) and preserves its last modified time (UTC).
        :param source_path: The full path to the source file.
        :param dest_path: The full path to the destination file.
        :param source_mtime_utc: The source file's mtime in epoch seconds (UTC).
        :param buffer_size: The size of the read/write buffer in bytes (default is 1 MB).
        """
        try:
            with open(source_path, "rb") as sf, open(dest_path, "wb") as df:
                while True:
                    buffer = sf.read(buffer_size)
                    if not buffer:
                        break
                    df.write(buffer)
        except Exception as e:
            print(f"Error copying file {source_path!r} to {dest_path!r}: {e}")
            raise

        # Preserve the source file's modification time (in UTC).
        # os.utime expects (atime, mtime) in *epoch seconds*.
        os.utime(dest_path, (source_mtime_utc, source_mtime_utc))

    def sort_files(
        self,
        source: str,
        destination: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Sorts files from a source directory into a destination directory based on date/time.

        :param source: The source directory to read files from.
        :param destination: The destination directory to copy sorted files to.
        :param progress_callback: A function to call with current and total file counts for progress updates.
        :param should_cancel: A function that returns True if cancellation is requested.
        :return: A dictionary containing sorting statistics.
        """
        # Initialize the sorting process
        source_dir, destination_dir = self._initialize_directories(source, destination)
        script_start_time = self._reset_counters_and_callbacks(
            progress_callback, should_cancel
        )

        # Build file processing list
        files_to_process = self._build_file_processing_list(source_dir)
        if (
            isinstance(files_to_process, dict)
            and files_to_process.get("status") == "cancelled"
        ):
            return files_to_process

        # Process all files
        result = self._process_all_files(files_to_process, destination_dir)  # type: ignore
        if isinstance(result, dict) and result.get("status") == "cancelled":
            return result

        # Generate final statistics
        return self._generate_final_statistics(script_start_time, len(files_to_process))

    def _initialize_directories(
        self, source: str, destination: str
    ) -> Tuple[Path, Path]:
        """Initialize and validate source and destination directories."""
        source_dir = Path(source)
        destination_dir = Path(destination)

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source}")
        if not destination_dir.exists():
            destination_dir.mkdir(parents=True, exist_ok=True)
        if not destination_dir.is_dir():
            raise NotADirectoryError(f"Destination is not a directory: {destination}")

        return source_dir, destination_dir

    def _reset_counters_and_callbacks(
        self,
        progress_callback: Optional[Callable[[int, int], None]],
        should_cancel: Optional[Callable[[], bool]],
    ) -> datetime:
        """Reset counters and store callbacks."""
        script_start_time = datetime.now()

        # Reset counters
        self.files_copied = 0
        self.files_skipped = 0
        self.total_bytes_copied = 0

        # Store callbacks
        self._progress_callback = progress_callback
        self._should_cancel = should_cancel

        return script_start_time

    def _get_date_folders(self, source_dir: Path) -> List[Path]:
        """Get all date/time folders from source directory."""
        try:
            date_folders: List[Path] = [f for f in source_dir.iterdir() if f.is_dir()]
        except Exception as e:
            print(f"Error retrieving date folders from source directory: {e}")
            raise

        print(f"Found {len(date_folders)} date folders in source directory.")
        return date_folders

    def _is_valid_date_folder(self, folder_name: str) -> bool:
        """Validate if folder name contains valid date and time components."""
        folder_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
        if not folder_pattern.match(folder_name):
            return False

        try:
            # Extract date and time components
            date_part, time_part = folder_name.split("_")
            year, month, day = map(int, date_part.split("-"))
            hour, minute, second = map(int, time_part.split("-"))

            # Validate components
            if not (
                1 <= month <= 12
                and 1 <= day <= 31
                and 0 <= hour <= 23
                and 0 <= minute <= 59
                and 0 <= second <= 59
            ):
                return False

            # Additional validation using datetime
            datetime(year, month, day, hour, minute, second)
            return True
        except (ValueError, TypeError):
            return False

    def _extract_folder_datetime(self, folder_name: str) -> Optional[str]:
        """Extract datetime string from folder name."""
        # Remove '-' and '_' from folder name: e.g., 2023-05-01_07-32-20 -> 20230501T073220
        folder_datetime_raw = folder_name.replace("-", "").replace("_", "")
        if len(folder_datetime_raw) < 14:
            return None

        # Insert 'T' between the date part (8 digits) and time part (6 digits)
        return folder_datetime_raw[:8] + "T" + folder_datetime_raw[8:]

    def _get_png_files_from_folder(self, folder: Path) -> List[Path]:
        """Get all PNG files from a folder."""
        try:
            return list(folder.glob("*.png"))
        except Exception as e:
            print(f"Error retrieving files in folder {folder.name!r}: {e}")
            return []

    def _check_cancellation(self) -> bool:
        """Check if cancellation has been requested."""
        return bool(self._should_cancel and self._should_cancel())

    def _update_progress(self, current: int, total: int) -> None:
        """Update progress if callback is available."""
        if self._progress_callback:
            self._progress_callback(current, total)

    def _build_file_processing_list(
        self, source_dir: Path
    ) -> Union[List[Tuple[Path, str]], Dict[str, str]]:
        """Build a list of files to process with their datetime information."""
        date_folders = self._get_date_folders(source_dir)
        files_to_process: List[Tuple[Path, str]] = []
        folder_counter = 0
        total_folders = len(date_folders)

        for folder in date_folders:
            if self._check_cancellation():
                print("Cancellation requested during file collection.")
                return {"status": "cancelled"}

            folder_counter += 1
            self._update_progress(folder_counter, total_folders)

            # Skip null or invalid folders
            if folder is None:
                print("Encountered a null folder entry. Skipping...")
                continue

            if not self._is_valid_date_folder(folder.name):
                continue

            folder_datetime = self._extract_folder_datetime(folder.name)
            if folder_datetime is None:
                continue

            # Add all PNG files from this folder
            png_files = self._get_png_files_from_folder(folder)
            for file_path in png_files:
                files_to_process.append((file_path, folder_datetime))

        print(f"Total files to process: {len(files_to_process)}")
        return files_to_process

    def _extract_base_name(self, file_name: str) -> str:
        """Extract base name from file name, removing datetime suffix if present."""
        # If it matches "_YYYYMMDDThhmmssZ.png" (20 chars from end), strip that part:
        if re.search(r"_\d{8}T\d{6}Z\.png$", file_name):
            return file_name[:-20]  # remove the date/time portion + extension
        elif file_name.endswith(".png"):
            return file_name[:-4]
        return file_name

    def _create_target_folder(self, destination_dir: Path, base_name: str) -> Path:
        """Create target folder for the base name if it doesn't exist."""
        target_folder: Path = destination_dir / base_name
        if not target_folder.exists() and not self.dry_run:
            try:
                target_folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating folder {target_folder!r}: {e}")
                raise
        return target_folder

    def _generate_new_file_name(
        self, file_name: str, base_name: str, folder_datetime: str
    ) -> str:
        """Generate new file name with datetime suffix if not already present."""
        if not re.search(r"_\d{8}T\d{6}Z\.png$", file_name):
            return f"{base_name}_{folder_datetime}Z.png"
        # Already has date/time suffix, keep it
        return file_name

    def _check_files_identical(
        self, source_path: Path, dest_path: Path, time_tolerance: float = 1.0
    ) -> bool:
        """Check if source and destination files are identical."""
        if not dest_path.exists():
            return False

        source_size = source_path.stat().st_size
        source_mtime = source_path.stat().st_mtime
        dest_size = dest_path.stat().st_size
        dest_mtime = dest_path.stat().st_mtime

        if source_size != dest_size:
            return False

        time_diff = abs(source_mtime - dest_mtime)
        return time_diff <= time_tolerance

    def _handle_duplicate_file(
        self, new_file_path: Path, target_folder: Path
    ) -> Tuple[Path, str]:
        """Handle duplicate files based on duplicate mode."""
        if self.duplicate_mode == DuplicateMode.SKIP:
            self.files_skipped += 1
            return new_file_path, "SKIPPED (Duplicate)"
        elif self.duplicate_mode == DuplicateMode.RENAME:
            # Generate a new unique name
            rename_counter = 1
            original_stem = new_file_path.stem
            original_suffix = new_file_path.suffix
            while new_file_path.exists():
                new_file_name = f"{original_stem}_{rename_counter}{original_suffix}"
                new_file_path = target_folder / new_file_name
                rename_counter += 1
            return new_file_path, f"RENAMED to {new_file_path.name}"
        return new_file_path, f"OVERWRITING {new_file_path.name}"

    def _copy_file_if_needed(
        self, source_path: Path, dest_path: Path, action_msg: str
    ) -> str:
        """Copy file if not in dry run mode."""
        if self.dry_run:
            return f"DRY RUN: Would copy to {dest_path.name}"
        source_size = source_path.stat().st_size
        source_mtime = source_path.stat().st_mtime
        self.copy_file_with_buffer(source_path, dest_path, source_mtime)
        self.files_copied += 1
        self.total_bytes_copied += source_size
        return action_msg if action_msg else f"COPIED to {dest_path.name}"

    def _process_single_file(
        self, file_path: Path, folder_datetime: str, destination_dir: Path
    ) -> None:
        """Process a single file for sorting."""
        file_name = file_path.name

        # Extract base name and create target folder
        base_name = self._extract_base_name(file_name)
        target_folder = self._create_target_folder(destination_dir, base_name)

        # Generate new file name and path
        new_file_name = self._generate_new_file_name(
            file_name, base_name, folder_datetime
        )
        new_file_path = target_folder / new_file_name

        # Check if files are identical
        if self._check_files_identical(file_path, new_file_path):
            self.files_skipped += 1
            return

        # Handle file processing based on existence and duplicate mode
        action_msg = ""
        if new_file_path.exists():
            new_file_path, action_msg = self._handle_duplicate_file(
                new_file_path, target_folder
            )
            if "SKIPPED" in action_msg:
                return  # Skip to next file

        # Copy the file
        self._copy_file_if_needed(file_path, new_file_path, action_msg)

    def _process_all_files(
        self, files_to_process: List[Tuple[Path, str]], destination_dir: Path
    ) -> Optional[Dict[str, str]]:
        """Process all files in the processing list."""
        counter = 0
        total_files = len(files_to_process)

        for file_path, folder_datetime in files_to_process:
            if self._check_cancellation():
                print("Cancellation requested during file processing.")
                return {"status": "cancelled"}

            counter += 1
            self._update_progress(counter, total_files)

            try:
                self._process_single_file(file_path, folder_datetime, destination_dir)
            except Exception as e:
                print(f"\nError processing file {file_path.name!r}: {e}")

        return None

    def _generate_final_statistics(
        self, script_start_time: datetime, total_files: int
    ) -> Dict[str, Any]:
        """Generate and print final sorting statistics."""
        print()  # Move to new line after progress

        script_end_time = datetime.now()
        total_duration = script_end_time - script_start_time
        print("Script execution completed.")
        print(f"Total execution time: {total_duration}")
        print(f"Files copied: {self.files_copied}")
        print(f"Files skipped: {self.files_skipped}")

        size_in_mb = round(self.total_bytes_copied / (1024 * 1024), 2)
        print(f"Total data copied: {size_in_mb} MB")

        if total_files > 0:
            average_time_per_file = round(
                total_duration.total_seconds() / total_files, 2
            )
        else:
            average_time_per_file = 0
        print(f"Average time per file: {average_time_per_file} seconds")

        final_stats = {
            "files_copied": self.files_copied,
            "files_skipped": self.files_skipped,
            "total_bytes": self.total_bytes_copied,
            "duration": str(datetime.now() - script_start_time),
        }

        print("Returning stats:", final_stats)
        print("\nAnalysis complete!")

        return final_stats


def main() -> None:
    # The GUI is not included in this integration, so we only keep the CLI logic.
    # The original code had an if/else for GUI vs CLI, we remove the GUI part.
    import argparse

    parser = argparse.ArgumentParser(
        description="Sorts image files into folders based on date/time."
    )
    parser.add_argument(
        "root_dir",
        nargs="?",
        default=None,
        help="Root directory to process. Defaults to the current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually copying or modifying files.",
    )
    parser.add_argument(
        "--duplicate-mode",
        choices=["overwrite", "skip", "rename"],
        default="overwrite",
        help="Action to take when a duplicate file is found. "
        "Options: overwrite, skip, rename. Defaults to overwrite.",
    )

    args = parser.parse_args()

    duplicate_mode = DuplicateMode[args.duplicate_mode.upper()]

    sorter = FileSorter(dry_run=args.dry_run, duplicate_mode=duplicate_mode)
    # In CLI mode, we still use root_dir for simplicity, not source/destination
    # The GUI will use source/destination with the ViewModel
    sorter.sort_files(
        source=args.root_dir if args.root_dir else ".", destination="./converted"
    )


if __name__ == "__main__":
    main()
