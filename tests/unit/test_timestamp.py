#!/usr/bin/env python3
"""Test script for the timestamped output path generation functionality."""

import re
import os
import sys
from pathlib import Path
from datetime import datetime

def generate_timestamped_output_path(base_dir=None, base_name=None):
    """Generate a fresh timestamped output path for uniqueness across runs."""
    # Use current directory and generic name if not set
    if not base_dir:
        base_dir = Path(os.getcwd())
    if not base_name:
        base_name = "output"
        
    # Generate timestamp and create path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"{base_name}_output_{timestamp}.mp4"

def extract_base_name(path):
    """Extract the base name from a timestamped path."""
    if not path:
        return None, None
        
    # Extract directory and basename
    base_dir = path.parent
    
    # Try to extract the original name before the timestamp
    filename = path.stem  # Get filename without extension
    # Check if it matches pattern like "name_output_20230405_123456"
    match = re.match(r"(.+?)_output_\d{8}_\d{6}", filename)
    if match:
        # Extract the original name
        base_name = match.group(1)
    else:
        # If no timestamp found, try to remove _output suffix
        if "_output" in filename:
            base_name = filename.split("_output")[0]
        else:
            # Just use the whole name as base
            base_name = filename
            
    return base_dir, base_name

def main():
    # Test case 1: Generate a fresh output path with defaults
    print("Test 1: Generate with defaults")
    path1 = generate_timestamped_output_path()
    print(f"Generated path: {path1}")
    
    # Test case 2: Generate with custom base dir and name
    print("\nTest 2: Generate with custom base")
    custom_dir = Path("/tmp")
    custom_name = "test_video"
    path2 = generate_timestamped_output_path(custom_dir, custom_name)
    print(f"Generated path: {path2}")
    
    # Test case 3: Extract base from existing path and regenerate
    print("\nTest 3: Extract base from existing path and regenerate")
    # Let's use path2 as our "existing" path
    base_dir, base_name = extract_base_name(path2)
    print(f"Extracted base directory: {base_dir}")
    print(f"Extracted base name: {base_name}")
    
    # Generate a new path with the extracted base
    path3 = generate_timestamped_output_path(base_dir, base_name)
    print(f"Regenerated path: {path3}")
    
    # Test case 4: Multiple paths with same base should have different timestamps
    print("\nTest 4: Multiple paths with same base")
    print(f"First:  {generate_timestamped_output_path(base_dir, base_name)}")
    import time
    time.sleep(1)  # Wait to ensure timestamps are different
    print(f"Second: {generate_timestamped_output_path(base_dir, base_name)}")
    time.sleep(1)
    print(f"Third:  {generate_timestamped_output_path(base_dir, base_name)}")
    
    # Test case 5: Test with non-standard filename
    print("\nTest 5: Non-standard filename")
    complex_path = Path("/tmp/my.complex-name_with_20230101_stuff.mp4")
    base_dir, base_name = extract_base_name(complex_path)
    print(f"Extracted base directory: {base_dir}")
    print(f"Extracted base name: {base_name}")
    print(f"New path: {generate_timestamped_output_path(base_dir, base_name)}")

if __name__ == "__main__":
    main()