#!/usr/bin/env python3

import os
import re
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Constants
DEFAULT_TIME_TOLERANCE_SECONDS = (
    1.0  # Tolerance for "last modified" comparison, in seconds
)
DEFAULT_BUFFER_SIZE = 1048576  # 1MB buffer for file copying


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
        buffer_size: int = DEFAULT_BUFFER_SIZE,
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

    def _validate_directories(self, source: str, destination: str) -> Tuple[Path, Path]:
        """
        Validates the source and destination directories.

        Args:
            source: The source directory path
            destination: The destination directory path

        Returns:
            Tuple of (source_dir, destination_dir) as Path objects

        Raises:
            FileNotFoundError: If source directory doesn't exist
            NotADirectoryError: If destination is not a directory
        """
        source_dir = Path(source)
        destination_dir = Path(destination)

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source}")

        if not destination_dir.exists():
            destination_dir.mkdir(parents=True, exist_ok=True)

        if not destination_dir.is_dir():
            raise NotADirectoryError(f"Destination is not a directory: {destination}")

        return source_dir, destination_dir

    def _check_for_cancellation(self) -> bool:
        """
        Checks if cancellation has been requested.

        Returns:
            True if cancellation was requested, False otherwise
        """
        if self._should_cancel and self._should_cancel():
            print("Cancellation requested.")
            return True
        return False

    def _update_progress(self, current: int, total: int) -> None:
        """
        Updates progress using the callback if provided.

        Args:
            current: Current progress value
            total: Total items to process
        """
        if self._progress_callback:
            self._progress_callback(current, total)

    def _is_valid_date_folder(self, folder_name: str) -> bool:
        """
        Validate if folder name contains valid date and time components.

        Args:
            folder_name: The folder name to validate

        Returns:
            True if folder name contains valid date and time, False otherwise
        """
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

    def _collect_date_folders(self, source_dir: Path) -> List[Path]:
        """
        Finds all date/time folders in the source directory.

        Args:
            source_dir: The source directory to scan

        Returns:
            List of valid date folder paths

        Raises:
            Exception: If there's an error accessing the source directory
        """
        try:
            # Get all folders in the source directory
            date_folders: List[Path] = [f for f in source_dir.iterdir() if f.is_dir()]
            total_folders = len(date_folders)
            print(f"Found {total_folders} date folders in source directory.")
            return date_folders
        except Exception as e:
            print(f"Error retrieving date folders from source directory: {e}")
            raise

    def _get_folder_datetime(self, folder: Path) -> Optional[str]:
        """
        Extracts a formatted datetime string from a folder name.

        Args:
            folder: Path object representing the folder

        Returns:
            Formatted datetime string or None if invalid
        """
        if not self._is_valid_date_folder(folder.name):
            return None

        # Remove '-' and '_' from folder name: e.g., 2023-05-01_07-32-20 -> 20230501T073220
        folder_datetime_raw = folder.name.replace("-", "").replace("_", "")
        if len(folder_datetime_raw) < 14:
            # Just a safety check, skip if not long enough
            return None

        # Insert 'T' between the date part (8 digits) and time part (6 digits)
        folder_datetime = folder_datetime_raw[:8] + "T" + folder_datetime_raw[8:]
        return folder_datetime

    def _collect_files_to_process(
        self, date_folders: List[Path]
    ) -> List[Tuple[Path, str]]:
        """
        Collects all files to process from date folders.

        Args:
            date_folders: List of date folder paths

        Returns:
            List of tuples containing (file_path, folder_datetime)
        """
        files_to_process: List[Tuple[Path, str]] = []
        total_folders = len(date_folders)
        folder_counter = 0

        for folder in date_folders:
            if self._check_for_cancellation():
                return []  # Empty list indicates cancellation

            folder_counter += 1
            self._update_progress(folder_counter, total_folders)

            # Skip null or unexpected format
            if folder is None:
                print("Encountered a null folder entry. Skipping...")
                continue

            folder_datetime = self._get_folder_datetime(folder)
            if folder_datetime is None:
                continue

            # Gather all PNG files
            try:
                png_files: List[Path] = list(folder.glob("*.png"))
            except Exception as e:
                print(f"Error retrieving files in folder {folder.name!r}: {e}")
                continue

            for file_path in png_files:
                files_to_process.append((file_path, folder_datetime))

        total_files = len(files_to_process)
        print(f"Total files to process: {total_files}")
        return files_to_process

    def _prepare_target_path(
        self, file_path: Path, folder_datetime: str, destination_dir: Path
    ) -> Tuple[Path, Path, str]:
        """
        Prepares the target path for copying.

        Args:
            file_path: Source file path
            folder_datetime: Formatted datetime string
            destination_dir: Base destination directory

        Returns:
            Tuple of (target_folder, new_file_path, base_name)
        """
        file_name: str = file_path.name

        # Extract base name from file name
        base_name: str = file_name
        # If it matches "_YYYYMMDDThhmmssZ.png" (20 chars from end), strip that part:
        if re.search(r"_\d{8}T\d{6}Z\.png$", file_name):
            base_name = file_name[:-20]  # remove the date/time portion + extension
        elif file_name.endswith(".png"):
            base_name = file_name[:-4]

        # Create sub-folder in 'destination' for this base_name if it doesn't exist
        target_folder: Path = destination_dir / base_name
        if not target_folder.exists() and not self.dry_run:
            try:
                target_folder.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating folder {target_folder!r}: {e}")
                raise

        # Construct new file name with date/time suffix if needed
        if not re.search(r"_\d{8}T\d{6}Z\.png$", file_name):
            new_file_name: str = f"{base_name}_{folder_datetime}Z.png"
        else:
            # Already has date/time suffix, keep it
            new_file_name = file_name

        new_file_path: Path = target_folder / new_file_name
        return target_folder, new_file_path, base_name

    def _check_files_identical(
        self,
        file_path: Path,
        new_file_path: Path,
        time_tolerance_seconds: float = DEFAULT_TIME_TOLERANCE_SECONDS,
    ) -> Tuple[bool, int, float]:
        """
        Checks if source and destination files are identical.

        Args:
            file_path: Source file path
            new_file_path: Destination file path
            time_tolerance_seconds: Tolerance for mtime comparison

        Returns:
            Tuple of (files_are_identical, source_size, source_mtime_utc)
        """
        source_size: int = file_path.stat().st_size
        source_mtime_utc: float = file_path.stat().st_mtime
        files_are_identical: bool = False

        if new_file_path.exists():
            dest_size: int = new_file_path.stat().st_size
            dest_mtime_utc: float = new_file_path.stat().st_mtime
            if source_size == dest_size:
                time_diff: float = abs(source_mtime_utc - dest_mtime_utc)
                if time_diff <= time_tolerance_seconds:
                    # Consider the files identical
                    self.files_skipped += 1
                    files_are_identical = True

        return files_are_identical, source_size, source_mtime_utc

    def _handle_duplicate(self, new_file_path: Path) -> Tuple[Optional[Path], str]:
        """
        Handles duplicate files based on the configured duplicate mode.

        Args:
            new_file_path: The destination file path

        Returns:
            Tuple of (updated_path, action_message)
        """
        action_msg: str = ""

        if self.duplicate_mode == DuplicateMode.SKIP:
            self.files_skipped += 1
            action_msg = "SKIPPED (Duplicate)"
            return None, action_msg

        elif self.duplicate_mode == DuplicateMode.RENAME:
            # Generate a new unique name
            rename_counter = 1
            original_stem = new_file_path.stem
            original_suffix = new_file_path.suffix
            while new_file_path.exists():
                new_file_name = f"{original_stem}_{rename_counter}{original_suffix}"
                new_file_path = new_file_path.parent / new_file_name
                rename_counter += 1
            action_msg = f"RENAMED to {new_file_path.name}"
            return new_file_path, action_msg

        else:  # Overwrite mode
            action_msg = f"OVERWRITING {new_file_path.name}"
            return new_file_path, action_msg

    def _process_single_file(
        self,
        file_path: Path,
        new_file_path: Path,
        source_mtime_utc: float,
        source_size: int,
        files_are_identical: bool,
    ) -> str:
        """
        Processes a single file by copying or skipping it.

        Args:
            file_path: Source file path
            new_file_path: Destination file path
            source_mtime_utc: Source file's mtime
            source_size: Source file's size
            files_are_identical: Whether files are identical

        Returns:
            Action message describing what was done
        """
        action_msg: str = ""

        if not files_are_identical:
            if new_file_path.exists():
                # Handle duplicate based on mode
                updated_path, action_msg = self._handle_duplicate(new_file_path)
                if updated_path is None:
                    return action_msg  # Skip to next file
                new_file_path = updated_path

            if self.dry_run:
                action_msg = f"DRY RUN: Would copy to {new_file_path.name}"
            else:
                # Perform the actual copy only if not dry run
                self.copy_file_with_buffer(file_path, new_file_path, source_mtime_utc)
                self.files_copied += 1
                self.total_bytes_copied += source_size
                # action_msg should be set above based on Rename/Overwrite or be empty
                if not action_msg:
                    action_msg = f"COPIED to {new_file_path.name}"
        else:
            # Files are identical, log as skipped
            action_msg = "SKIPPED (Identical)"

        return action_msg

    def _process_files(
        self, files_to_process: List[Tuple[Path, str]], destination_dir: Path
    ) -> None:
        """
        Processes all files by copying or skipping them.

        Args:
            files_to_process: List of tuples containing (file_path, folder_datetime)
            destination_dir: Destination directory
        """
        total_files = len(files_to_process)
        counter = 0

        for file_path, folder_datetime in files_to_process:
            if self._check_for_cancellation():
                return

            counter += 1
            self._update_progress(counter, total_files)

            try:
                # Prepare target path
                _, new_file_path, _ = self._prepare_target_path(
                    file_path, folder_datetime, destination_dir
                )

                # Check if files are identical
                (
                    files_are_identical,
                    source_size,
                    source_mtime_utc,
                ) = self._check_files_identical(file_path, new_file_path)

                # Process the file
                self._process_single_file(
                    file_path,
                    new_file_path,
                    source_mtime_utc,
                    source_size,
                    files_are_identical,
                )

            except Exception as e:
                print(
                    f"\nError processing file {file_path.name!r}: {e}"
                )  # Print error on new line

    def _generate_stats(self, script_start_time: datetime) -> Dict[str, Any]:
        """
        Generates statistics of the file sorting operation.

        Args:
            script_start_time: The time when the script started

        Returns:
            Dictionary containing sorting statistics
        """
        script_end_time = datetime.now()
        total_duration = script_end_time - script_start_time

        print("Script execution completed.")
        print(f"Total execution time: {total_duration}")
        print(f"Files copied: {self.files_copied}")
        print(f"Files skipped: {self.files_skipped}")

        size_in_mb = round(self.total_bytes_copied / (1024 * 1024), 2)
        print(f"Total data copied: {size_in_mb} MB")

        total_files = self.files_copied + self.files_skipped
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
            "duration": str(
                datetime.now() - script_start_time
            ),  # Convert timedelta to string
            "status": "completed",
        }

        print("Returning stats:", final_stats)
        print("\nAnalysis complete!")

        return final_stats

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
        script_start_time = datetime.now()

        # Reset counters
        self.files_copied = 0
        self.files_skipped = 0
        self.total_bytes_copied = 0

        # Store callbacks
        self._progress_callback = progress_callback
        self._should_cancel = should_cancel

        try:
            # 1. Validate directories
            source_dir, destination_dir = self._validate_directories(
                source, destination
            )

            # 2. Get all date/time folders in the source directory
            date_folders = self._collect_date_folders(source_dir)

            # 3. Build a list of files to process along with the extracted date/time
            files_to_process = self._collect_files_to_process(date_folders)
            if not files_to_process and self._check_for_cancellation():
                return {"status": "cancelled"}

            # 4. Process files (copy, rename, skip if identical, track stats)
            self._process_files(files_to_process, destination_dir)
            if self._check_for_cancellation():
                return {"status": "cancelled"}

            # 5. Generate statistics
            return self._generate_stats(script_start_time)

        except Exception as e:
            print(f"Error during file sorting: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "files_copied": self.files_copied,
                "files_skipped": self.files_skipped,
                "total_bytes": self.total_bytes_copied,
            }


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
        help="Show what would be done without actually copying files.",
    )
    parser.add_argument(
        "--duplicate-mode",
        choices=["overwrite", "skip", "rename"],
        default="overwrite",
        help="How to handle duplicate files: 'overwrite', 'skip', or 'rename'. Default is 'overwrite'.",
    )
    parser.add_argument(
        "--destination",
        default=None,
        help="Destination directory. Defaults to a 'sorted' subdirectory in the root directory.",
    )

    args = parser.parse_args()

    # Use current directory if none specified
    root_dir = args.root_dir or os.getcwd()
    root_dir = os.path.abspath(root_dir)  # Convert to absolute path

    print(f"Source directory: {root_dir}")

    # If no destination specified, use 'sorted' subdirectory in the source
    dest_dir = args.destination or os.path.join(root_dir, "sorted")
    print(f"Destination directory: {dest_dir}")

    # Convert duplicate mode string to enum
    mode_map = {
        "overwrite": DuplicateMode.OVERWRITE,
        "skip": DuplicateMode.SKIP,
        "rename": DuplicateMode.RENAME,
    }
    duplicate_mode = mode_map[args.duplicate_mode]

    sorter = FileSorter(dry_run=args.dry_run, duplicate_mode=duplicate_mode)
    sorter.sort_files(root_dir, dest_dir)


if __name__ == "__main__":
    main()
