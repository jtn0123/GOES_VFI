#!/usr/bin/env python3
"""
Script to reorganize example scripts from the root directory to appropriate example subdirectories.
"""
import os
import shutil


def ensure_directory(directory):
    """Ensure the directory exists."""
os.makedirs(directory, exist_ok=True)


def move_file(source, destination):
    """Move a file from source to destination."""
# Create parent directory if it doesn't exist
ensure_directory(os.path.dirname(destination))

# Check if the file exists at the destination
if os.path.exists(destination):
     pass
print(f"Warning: {destination} already exists. Skipping...")
return False

# Check if the source file exists
if not os.path.exists(source):
     pass
print(f"Error: Source file {source} does not exist. Skipping...")
return False

# Move the file
try:
     shutil.copy2(source, destination)
print(f"Moved: {source} -> {destination}")
return True
except Exception as e:
     pass
print(f"Error moving {source} to {destination}: {e}")
return False


def main():
    """Main function to reorganize example files."""
# Define the mapping of example files to their destinations
example_mapping = {
# Download category
"download_and_process_cmip.py": "examples / download / download_and_process_cmip.py",
"download_goes_data.py": "examples / download / download_goes_data.py",
"download_goes_jpeg.py": "examples / download / download_goes_jpeg.py",
"download_goes_l2_data.py": "examples / download / download_goes_l2_data.py",
"download_ir_sanchez.py": "examples / download / download_ir_sanchez.py",
"download_ir_simple.py": "examples / download / download_ir_simple.py",
"download_l1b_test.py": "examples / download / download_l1b_test.py",
"download_mesoscale_l2.py": "examples / download / download_mesoscale_l2.py",
"download_quicklook_images.py": "examples / download / download_quicklook_images.py",
"download_true_color.py": "examples / download / download_true_color.py",
"download_water_vapor.py": "examples / download / download_water_vapor.py",
"list_and_download.py": "examples / download / list_and_download.py",
# Imagery category
"enhanced_true_color.py": "examples / imagery / enhanced_true_color.py",
"extract_cmip_truecolor.py": "examples / imagery / extract_cmip_truecolor.py",
"goes_satpy_processor.py": "examples / imagery / goes_satpy_processor.py",
"improved_cmip_processor.py": "examples / imagery / improved_cmip_processor.py",
"improved_goes_processor.py": "examples / imagery / improved_goes_processor.py",
"improved_true_color.py": "examples / imagery / improved_true_color.py",
"natural_earth_color.py": "examples / imagery / natural_earth_color.py",
# Processing category
"analyze_cmip_structure.py": "examples / processing / analyze_cmip_structure.py",
"create_rgb_composites.py": "examples / processing / create_rgb_composites.py",
"discover_goes_channels.py": "examples / processing / discover_goes_channels.py",
"signal_test.py": "examples / processing / signal_test.py",
"time_index_updated.py": "examples / processing / time_index_updated.py",
"update_time_index.py": "examples / processing / update_time_index.py",
"verify_cmip_path.py": "examples / processing / verify_cmip_path.py",
# S3 Access category
"check_aws_credentials.py": "examples / s3_access / check_aws_credentials.py",
"check_recent_goes.py": "examples / s3_access / check_recent_goes.py",
"check_s3_paths.py": "examples / s3_access / check_s3_paths.py",
"find_actual_files.py": "examples / s3_access / find_actual_files.py",
"list_s3_contents.py": "examples / s3_access / list_s3_contents.py",
"list_specific_paths.py": "examples / s3_access / list_specific_paths.py",
"scan_goes_dates.py": "examples / s3_access / scan_goes_dates.py",
"scan_goes_hours.py": "examples / s3_access / scan_goes_hours.py",
"scan_mesoscale.py": "examples / s3_access / scan_mesoscale.py",
# Visualization category (new)
"visualize_all_channels.py": "examples / visualization / visualize_all_channels.py",
# Debugging category (new)
"debug_integrity_browse.py": "examples / debugging / debug_integrity_browse.py",
"debug_integrity_crash.py": "examples / debugging / debug_integrity_crash.py",
"debug_integrity_scan.py": "examples / debugging / debug_integrity_scan.py",
"debug_integrity_tab.py": "examples / debugging / debug_integrity_tab.py",
"debug_run.py": "examples / debugging / debug_run.py",
"debug_without_integrity.py": "examples / debugging / debug_without_integrity.py",
# Utilities category (new)
"add_type_annotations.py": "examples / utilities / add_type_annotations.py",
"cleanup.py": "examples / utilities / cleanup.py",
"fix_syntax.py": "examples / utilities / fix_syntax.py",
"mypy_analyzer.py": "examples / utilities / mypy_analyzer.py",
}

# Create new directories for new categories
new_dirs = ["examples / visualization", "examples / debugging", "examples / utilities"]
for directory in new_dirs:
     ensure_directory(directory)
# Create __init__.py for each new directory
with open(os.path.join(directory, "__init__.py"), "w") as f:
     f.write("# This file is required to make the directory a Python package\n")
print(f"Created directory and __init__.py: {directory}")

# Move the files
for source, destination in example_mapping.items():
     move_file(source, destination)

print("Example reorganization complete.")

# Create README files for each category
readme_contents = {
"examples / download / README.md": "# GOES Download Examples\n\nThis directory contains examples for downloading various GOES satellite data products.\n\n## Scripts\n\n- `download_and_process_cmip.py` - Download and process CMIP (Cloud and Moisture Imagery Products)\n- `download_goes_data.py` - General GOES data downloader\n- `download_goes_jpeg.py` - Download GOES data in JPEG format\n- `download_goes_l2_data.py` - Download GOES Level 2 data products\n- `download_ir_sanchez.py` - Download IR data and process with Sanchez algorithm\n- `download_ir_simple.py` - Simple IR data downloader\n- `download_l1b_test.py` - Test script for L1b data downloads\n- `download_mesoscale_l2.py` - Download mesoscale L2 data\n- `download_quicklook_images.py` - Download quicklook preview images\n- `download_true_color.py` - Download data for true color composites\n- `download_water_vapor.py` - Download water vapor channel data\n- `list_and_download.py` - List available data and download selected items\n",
"examples / imagery / README.md": "# GOES Imagery Examples\n\nThis directory contains examples for processing and rendering GOES satellite imagery.\n\n## Scripts\n\n- `enhanced_true_color.py` - Create enhanced true color images\n- `extract_cmip_truecolor.py` - Extract and process true color from CMIP\n- `goes_satpy_processor.py` - Process GOES data using satpy\n- `improved_cmip_processor.py` - Improved CMIP processing algorithms\n- `improved_goes_processor.py` - Improved general GOES data processor\n- `improved_true_color.py` - Improved true color rendering\n- `natural_earth_color.py` - Create natural Earth color composites\n",
"examples / processing / README.md": "# GOES Data Processing Examples\n\nThis directory contains examples for processing GOES satellite data.\n\n## Scripts\n\n- `analyze_cmip_structure.py` - Analyze CMIP file structure\n- `create_rgb_composites.py` - Create RGB composite images from multiple channels\n- `discover_goes_channels.py` - Discover available channels in GOES data\n- `signal_test.py` - Test signal processing functionality\n- `time_index_updated.py` - Updated time indexing code\n- `update_time_index.py` - Update time index for data organization\n- `verify_cmip_path.py` - Verify CMIP file paths and structure\n",
"examples / s3_access / README.md": "# AWS S3 Access Examples\n\nThis directory contains examples for accessing GOES data from AWS S3 buckets.\n\n## Scripts\n\n- `check_aws_credentials.py` - Check AWS credentials configuration\n- `check_recent_goes.py` - Check for recent GOES data updates\n- `check_s3_paths.py` - Verify S3 path structures\n- `find_actual_files.py` - Find actual files matching patterns in S3\n- `list_s3_contents.py` - List contents of S3 buckets\n- `list_specific_paths.py` - List specific path patterns in S3\n- `scan_goes_dates.py` - Scan for available GOES data dates\n- `scan_goes_hours.py` - Scan for available GOES data hours\n- `scan_mesoscale.py` - Scan for mesoscale data availability\n",
"examples / visualization / README.md": "# GOES Data Visualization Examples\n\nThis directory contains examples for visualizing GOES satellite data.\n\n## Scripts\n\n- `visualize_all_channels.py` - Visualize all available GOES channels\n",
"examples / debugging / README.md": "# Debugging Examples\n\nThis directory contains scripts used for debugging specific functionality in the GOES VFI application.\n\n## Scripts\n\n- `debug_integrity_browse.py` - Debug integrity check browse functionality\n- `debug_integrity_crash.py` - Debug integrity check crash issues\n- `debug_integrity_scan.py` - Debug integrity check scanning functionality\n- `debug_integrity_tab.py` - Debug integrity check tab UI\n- `debug_run.py` - General debug runner\n- `debug_without_integrity.py` - Debug application without integrity checks\n",
"examples / utilities / README.md": "# Utility Scripts\n\nThis directory contains utility scripts for code maintenance and quality.\n\n## Scripts\n\n- `add_type_annotations.py` - Add type annotations to Python code\n- `cleanup.py` - Clean up temporary files and directories\n- `fix_syntax.py` - Fix syntax issues in code\n- `mypy_analyzer.py` - Analyze code with mypy for type checking\n",
}

# Write README files
for readme_path, content in readme_contents.items():
     with open(readme_path, "w") as f:
         pass
     f.write(content)
print(f"Created README: {readme_path}")

# Update main examples README
main_readme = "examples / README.md"
with open(main_readme, "w") as f:
     f.write(
"# GOES VFI Examples\n\n"
"This directory contains example scripts for various aspects of the GOES VFI project.\n\n"
"## Categories\n\n"
"- **[download](download/)** - Scripts for downloading GOES satellite data\n"
"- **[imagery](imagery/)** - Scripts for image processing and rendering\n"
"- **[processing](processing/)** - Scripts for data processing\n"
"- **[s3_access](s3_access/)** - Scripts for AWS S3 access\n"
"- **[visualization](visualization/)** - Scripts for data visualization\n"
"- **[debugging](debugging/)** - Scripts for debugging functionality\n"
"- **[utilities](utilities/)** - Utility scripts for code maintenance\n"
)
print(f"Updated main README: {main_readme}")


if __name__ == "__main__":
    pass
main()
