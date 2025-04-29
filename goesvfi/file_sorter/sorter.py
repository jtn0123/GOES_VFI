#!/usr/bin/env python3

import os
import re
import shutil
import sys
import time
import math
from enum import Enum, auto
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Tuple, List, Dict, Any

class DuplicateMode(Enum):
    OVERWRITE = auto()
    SKIP = auto()
    RENAME = auto()

class FileSorter:
    def __init__(self, dry_run: bool = False, duplicate_mode: DuplicateMode = DuplicateMode.OVERWRITE):
        self.files_copied = 0
        self.files_skipped = 0
        self.total_bytes_copied = 0
        self.progress_callback: Optional[Callable[[int, str], None]] = None
        self.dry_run = dry_run
        self.duplicate_mode = duplicate_mode

    def set_progress_callback(self, callback: Callable[[int, str], None]) -> None:
        self.progress_callback = callback

    def update_progress(self, percent: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(percent, message)
        else:
            print(f"[{percent}%] {message}", end="\\r")

    def copy_file_with_buffer(self, source_path: Path, dest_path: Path, source_mtime_utc: float, buffer_size: int = 1048576) -> None:
        """
        Copies a file in chunks (buffered) and preserves its last modified time (UTC).
        :param source_path: The full path to the source file.
        :param dest_path: The full path to the destination file.
        :param source_mtime_utc: The source file's mtime in epoch seconds (UTC).
        :param buffer_size: The size of the read/write buffer in bytes (default is 1 MB).
        """
        try:
            with open(source_path, 'rb') as sf, open(dest_path, 'wb') as df:
                while True:
                    buffer = sf.read(buffer_size)
                    if not buffer:
                        break
                    df.write(buffer)
        except Exception as e:
            print(f"Error copying file '{source_path}' to '{dest_path}': {e}")
            raise

        # Preserve the source file's modification time (in UTC).
        # os.utime expects (atime, mtime) in *epoch seconds*.
        os.utime(dest_path, (source_mtime_utc, source_mtime_utc))

    def sort_files(self, root_dir: Optional[str] = None) -> Dict[str, Any]:
        current_dir: Path
        if root_dir is None:
            current_dir = Path.cwd()
        else:
            current_dir = Path(root_dir)

        script_start_time = datetime.now()
        
        # Reset counters
        self.files_copied = 0
        self.files_skipped = 0
        self.total_bytes_copied = 0

        # Setup directories
        converted_folder_name = "converted"
        converted_folder_path = current_dir / converted_folder_name

        if not converted_folder_path.exists():
            converted_folder_path.mkdir()

        # --------------------------------------------------------------------------------
        # 3. Get all date/time folders in the current directory, excluding the "converted" folder
        # --------------------------------------------------------------------------------
        try:
            date_folders: List[Path] = [
                f for f in current_dir.iterdir()
                if f.is_dir() and f.name != converted_folder_name
            ]
        except Exception as e:
            print(f"Error retrieving date folders: {e}")
            raise

        total_folders = len(date_folders)
        print(f"Found {total_folders} date folders.")

        # --------------------------------------------------------------------------------
        # 4. Build a list of files to process along with the extracted date/time
        # --------------------------------------------------------------------------------
        files_to_process: List[Tuple[Path, str]] = []

        folder_counter = 0
        folder_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$')

        def is_valid_date_folder(folder_name: str) -> bool:
            """Validate if folder name contains valid date and time components"""
            if not folder_pattern.match(folder_name):
                return False
            
            try:
                # Extract date and time components
                date_part, time_part = folder_name.split('_')
                year, month, day = map(int, date_part.split('-'))
                hour, minute, second = map(int, time_part.split('-'))
                
                # Validate components
                if not (1 <= month <= 12 and
                        1 <= day <= 31 and
                        0 <= hour <= 23 and
                        0 <= minute <= 59 and
                        0 <= second <= 59):
                    return False
                
                # Additional validation using datetime
                datetime(year, month, day, hour, minute, second)
                return True
            except (ValueError, TypeError):
                return False

        for folder in date_folders:
            folder_counter += 1
            percent_complete = int((folder_counter / total_folders) * 100)
            self.update_progress(percent_complete, f"Collecting files: processing folder {folder_counter} of {total_folders} ({percent_complete}%) - '{folder.name}'")

            # Skip null or unexpected format
            if folder is None:
                print("Encountered a null folder entry. Skipping...")
                continue

            if not is_valid_date_folder(folder.name):
                # Not a valid date format, skip
                continue

            # Remove '-' and '_' from folder name: e.g., 2023-05-01_07-32-20 -> 20230501T073220
            folder_datetime_raw = folder.name.replace("-", "").replace("_", "")
            if len(folder_datetime_raw) < 14:
                # Just a safety check, skip if not long enough
                continue

            # Insert 'T' between the date part (8 digits) and time part (6 digits)
            folder_datetime = folder_datetime_raw[:8] + 'T' + folder_datetime_raw[8:]

            # Gather all PNG files
            try:
                png_files: List[Path] = list(folder.glob("*.png"))
            except Exception as e:
                print(f"Error retrieving files in folder '{folder.name}': {e}")
                continue

            for file_path in png_files:
                files_to_process.append((file_path, folder_datetime))

        total_files = len(files_to_process)
        print(f"Total files to process: {total_files}")

        # --------------------------------------------------------------------------------
        # 5. Process files (copy, rename, skip if identical, track stats)
        # --------------------------------------------------------------------------------
        time_tolerance_seconds: float = 1.0  # Tolerance for "last modified" comparison, in seconds

        counter = 0
        start_time = time.time()

        for (file_path, folder_datetime) in files_to_process:
            counter += 1
            file_name: str = file_path.name

            # --- Calculate progress and display info early --- #
            percent_complete = int((counter / total_files) * 100) if total_files > 0 else 0
            max_file_name_length: int = 50
            display_file_name: str = (file_name[:max_file_name_length] + "...") if len(file_name) > max_file_name_length else file_name
            # --- End progress info --- #

            try:
                # We will check whether the file_name ends with _YYYYMMDDThhmmssZ.png or just .png
                base_name: str = file_name
                # If it matches "_YYYYMMDDThhmmssZ.png" (20 chars from end), strip that part:
                if re.search(r'_\d{8}T\d{6}Z\.png$', file_name):
                    base_name = file_name[:-20]  # remove the date/time portion + extension
                elif file_name.endswith(".png"):
                    base_name = file_name[:-4]

                # Create sub-folder in 'converted' for this base_name if it doesn't exist
                target_folder: Path = converted_folder_path / base_name
                if not target_folder.exists() and not self.dry_run:
                    try:
                        target_folder.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        print(f"Error creating folder '{target_folder}': {e}")
                        raise

                # Construct new file name, if it doesn't already have the date/time suffix
                if not re.search(r'_\d{8}T\d{6}Z\.png$', file_name):
                    new_file_name: str = f"{base_name}_{folder_datetime}Z.png"
                else:
                    # Already has date/time suffix, keep it
                    new_file_name = file_name

                new_file_path: Path = target_folder / new_file_name

                # Check if the destination file exists and is identical in size & mtime (within tolerance)
                source_size: int = file_path.stat().st_size
                source_mtime_utc: float = file_path.stat().st_mtime  # seconds since epoch (UTC-based)
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

                # -- Prepare base status message --
                elapsed_time: float = time.time() - start_time
                if elapsed_time > 0 and counter > 0:
                    files_per_minute: float = round((counter / elapsed_time) * 60, 2)
                    estimated_total_time: float = (elapsed_time / counter) * total_files
                    eta_seconds: float = max(0, estimated_total_time - elapsed_time)
                    eta_str: str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
                else:
                    files_per_minute = 0
                    eta_str = "Calculating..."

                base_status_msg: str = (
                    f"{counter}/{total_files} ({percent_complete}%) "
                    f"Skipped: {self.files_skipped} | "
                    f"Speed: {files_per_minute} files/min | "
                    f"ETA: {eta_str}"
                )
                # -- End base status message --

                # If not identical, proceed based on duplicate mode
                if not files_are_identical:
                    action_msg: str = ""
                    if new_file_path.exists():
                        if self.duplicate_mode == DuplicateMode.SKIP:
                            self.files_skipped += 1
                            action_msg = "SKIPPED (Duplicate)"
                            self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")
                            continue # Skip to next file
                        elif self.duplicate_mode == DuplicateMode.RENAME:
                            # Generate a new unique name
                            rename_counter = 1
                            original_stem = new_file_path.stem
                            original_suffix = new_file_path.suffix
                            temp_new_name = new_file_name # Store original target name for message
                            while new_file_path.exists():
                                new_file_name = f"{original_stem}_{rename_counter}{original_suffix}"
                                new_file_path = target_folder / new_file_name
                                rename_counter += 1
                            action_msg = f"RENAMED to {new_file_name}"
                            # Update progress *before* copy/move
                            self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")
                        else: # Overwrite mode
                             action_msg = f"OVERWRITING {new_file_name}"
                             self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")
                        # If mode is 'Overwrite', no extra action needed before copy

                    if self.dry_run:
                        action_msg = f"DRY RUN: Would copy to {new_file_path.name}"
                        self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")
                    else:
                        # Perform the actual copy only if not dry run
                        self.copy_file_with_buffer(file_path, new_file_path, source_mtime_utc)
                        self.files_copied += 1
                        self.total_bytes_copied += source_size
                        # action_msg should be set above based on Rename/Overwrite or be empty
                        if not action_msg: action_msg = f"COPIED to {new_file_path.name}"
                        # Update progress *after* successful copy
                        self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")
                else:
                    # Files are identical, log as skipped
                    action_msg = "SKIPPED (Identical)"
                    self.update_progress(percent_complete, f"{base_status_msg} | File: {display_file_name} | {action_msg}")

            except Exception as e:
                print(f"\nError processing file '{file_path.name}': {e}") # Print error on new line

        # --------------------------------------------------------------------------------
        # 6. Final Stats and Cleanup
        # --------------------------------------------------------------------------------
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
            average_time_per_file = round(total_duration.total_seconds() / total_files, 2)
        else:
            average_time_per_file = 0
        print(f"Average time per file: {average_time_per_file} seconds")

        # Remove the input() call and just return stats
        final_stats = {
            'files_copied': self.files_copied,
            'files_skipped': self.files_skipped,
            'total_bytes': self.total_bytes_copied,
            'duration': str(datetime.now() - script_start_time)  # Convert timedelta to string
        }
        
        print("Returning stats:", final_stats)  # Debug print
        print("\nAnalysis complete!")

        return final_stats

def main() -> None:
    # The GUI is not included in this integration, so we only keep the CLI logic.
    # The original code had an if/else for GUI vs CLI, we remove the GUI part.
    import argparse

    parser = argparse.ArgumentParser(description="Sorts image files into folders based on date/time.")
    parser.add_argument("root_dir", nargs="?", default=None,
                        help="Root directory to process. Defaults to the current directory.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Perform a dry run without actually copying or modifying files.")
    parser.add_argument("--duplicate-mode", choices=["overwrite", "skip", "rename"],
                        default="overwrite", help="Action to take when a duplicate file is found. Options: overwrite, skip, rename. Defaults to overwrite.")

    args = parser.parse_args()

    duplicate_mode = DuplicateMode[args.duplicate_mode.upper()]

    sorter = FileSorter(dry_run=args.dry_run, duplicate_mode=duplicate_mode)
    sorter.sort_files(root_dir=args.root_dir)

if __name__ == "__main__":
    main()
