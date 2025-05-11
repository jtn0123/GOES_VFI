#!/usr/bin/env python3
"""
Script to fix Qt translation string issues (QTR).

This script adds self.tr() calls to user-visible strings in Qt widgets.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Patterns for Qt widgets that commonly need translation
QT_WIDGET_PATTERNS = [
    # QLabel constructor
    r'QLabel\(\s*(["\'].*?["\'])\s*\)',
    # QPushButton constructor
    r'QPushButton\(\s*(["\'].*?["\'])\s*\)',
    # QCheckBox constructor
    r'QCheckBox\(\s*(["\'].*?["\'])\s*\)',
    # QGroupBox constructor
    r'QGroupBox\(\s*(["\'].*?["\'])\s*\)',
    # setWindowTitle method
    r'setWindowTitle\(\s*(["\'].*?["\'])\s*\)',
    # setText method
    r'setText\(\s*(["\'].*?["\'])\s*\)',
    # setToolTip method
    r'setToolTip\(\s*(["\'].*?["\'])\s*\)',
    # addItem/addItems for combo boxes
    r'addItem\(\s*(["\'].*?["\'])\s*\)',
    # String keys in QComboBox.addItems method
    r'addItems\(\s*\[\s*((?:["\'].*?["\'](?:\s*,\s*)?)+)\s*\]\s*\)',
]

# Patterns to ignore (already translated or shouldn't be translated)
IGNORE_PATTERNS = [
    # Already translated 
    r'self\.tr\(',
    # Empty strings
    r'["\']\s*["\']',
    # Format strings (these need special handling)
    r'f["\']',
    # Variable names or typical non-translatable strings
    r'["\'](placeholder|name|value|key|id|class|style|icon|src|href|width|height|top|left|bottom|right|margin|padding)["\']',
]


def find_untranslated_strings(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Find untranslated strings in a file.
    
    Args:
        file_path: Path to the file to check.
        
    Returns:
        List of tuples (line_number, line, match) of untranslated strings.
    """
    untranslated = []
    ignore_pattern = '|'.join(IGNORE_PATTERNS)
    ignore_regex = re.compile(ignore_pattern)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        # Skip lines with ignore patterns
        if ignore_regex.search(line):
            continue
            
        # Check for Qt widget patterns
        for pattern in QT_WIDGET_PATTERNS:
            matches = re.findall(pattern, line)
            if matches:
                for match in matches:
                    # If it's a list of strings (from addItems pattern)
                    if isinstance(match, tuple) or (pattern == QT_WIDGET_PATTERNS[-1] and ',' in match):
                        if isinstance(match, str):
                            # Split the comma-separated string list
                            items = re.findall(r'["\'](.*?)["\']', match)
                            for item in items:
                                if item and not re.search(r'^\s*$', item):  # Skip empty strings
                                    untranslated.append((i+1, line, f'"{item}"'))
                        else:
                            for item in match:
                                if item and not re.search(r'^\s*$', item):  # Skip empty strings
                                    untranslated.append((i+1, line, item))
                    else:
                        # Simple string
                        if match and not re.search(r'^\s*$', match):  # Skip empty strings
                            untranslated.append((i+1, line, match))
    
    return untranslated


def fix_file(file_path: Path, dry_run: bool = True) -> Dict[str, int]:
    """
    Fix Qt translation issues in a file.
    
    Args:
        file_path: Path to the file to fix.
        dry_run: If True, don't modify the file, just return stats.
        
    Returns:
        Dictionary with stats about fixes.
    """
    stats = {'untranslated': 0, 'fixed': 0}
    
    untranslated = find_untranslated_strings(file_path)
    stats['untranslated'] = len(untranslated)
    
    if not untranslated:
        return stats
        
    if dry_run:
        print(f"Found {len(untranslated)} untranslated strings in {file_path}:")
        for line_num, line, match in untranslated:
            print(f"  Line {line_num}: {match}")
        return stats
        
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create a backup
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Replace untranslated strings
    for pattern in QT_WIDGET_PATTERNS:
        def replacement_func(match):
            # Extract the string from the match
            if pattern == QT_WIDGET_PATTERNS[-1] and ',' in match.group(1):
                # Handle addItems with list of strings
                items = re.findall(r'["\'](.*?)["\']', match.group(1))
                translated_items = [f'self.tr("{item}")' for item in items]
                return f'addItems([{", ".join(translated_items)}])'
            else:
                # Handle simple string
                string = match.group(1)
                # Extract the actual string content without quotes
                string_content = string[1:-1] if string else ""
                return match.group(0).replace(string, f'self.tr("{string_content}")')
                
        # Apply the replacement
        content = re.sub(pattern, replacement_func, content)
        
    # Write modified content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Count fixes (approximate)
    stats['fixed'] = stats['untranslated']
    
    return stats


def scan_directory(directory: Path, extensions: List[str] = None, dry_run: bool = True) -> Dict[str, int]:
    """
    Recursively scan a directory for Qt translation issues.
    
    Args:
        directory: Path to the directory to scan.
        extensions: List of file extensions to scan (default: ['.py'])
        dry_run: If True, don't modify files.
        
    Returns:
        Dictionary with stats about fixes.
    """
    if extensions is None:
        extensions = ['.py']
        
    stats = {'files_scanned': 0, 'files_with_issues': 0, 'untranslated': 0, 'fixed': 0}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = Path(root) / file
                file_stats = fix_file(file_path, dry_run)
                
                stats['files_scanned'] += 1
                if file_stats['untranslated'] > 0:
                    stats['files_with_issues'] += 1
                    stats['untranslated'] += file_stats['untranslated']
                    stats['fixed'] += file_stats['fixed']
    
    return stats


def main():
    """Run the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix Qt translation string issues')
    parser.add_argument('--directory', '-d', type=str, default='goesvfi', 
                        help='Directory to scan (default: goesvfi)')
    parser.add_argument('--extensions', '-e', type=str, default='.py', 
                        help='Comma-separated list of file extensions to scan (default: .py)')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Don\'t modify files, just show issues')
    parser.add_argument('--file', '-f', type=str, 
                        help='Single file to fix')
                        
    args = parser.parse_args()
    
    # Process a single file
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            stats = fix_file(file_path, args.dry_run)
            print(f"Results for {file_path}:")
            print(f"  Untranslated strings: {stats['untranslated']}")
            if not args.dry_run:
                print(f"  Fixed strings: {stats['fixed']}")
        else:
            print(f"Error: File {file_path} does not exist!")
        return
        
    # Process a directory
    directory = Path(args.directory)
    if not directory.exists() or not directory.is_dir():
        print(f"Error: Directory {directory} does not exist!")
        return
    
    extensions = args.extensions.split(',')
    
    print(f"Scanning directory: {directory}")
    print(f"File extensions: {extensions}")
    print(f"Dry run: {args.dry_run}")
    
    stats = scan_directory(directory, extensions, args.dry_run)
    
    print("\nResults:")
    print(f"  Files scanned: {stats['files_scanned']}")
    print(f"  Files with issues: {stats['files_with_issues']}")
    print(f"  Untranslated strings: {stats['untranslated']}")
    if not args.dry_run:
        print(f"  Fixed strings: {stats['fixed']}")


if __name__ == '__main__':
    main()