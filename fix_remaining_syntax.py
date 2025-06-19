#!/usr/bin/env python
"""Fix remaining syntax errors in GOES-VFI codebase."""

import ast
import re
from pathlib import Path
from typing import List, Tuple


def fix_docstring_code_mix(content: str) -> str:
    """Fix docstrings that have code mixed in."""
    # Pattern: """docstring
    # from module import
    # Should become: """docstring"""
    #
    # from module import

    lines = content.split("\n")
    fixed_lines = []
    in_docstring = False
    docstring_start = -1

    for i, line in enumerate(lines):
        if '"""' in line:
            count = line.count('"""')
            if count == 1:
                if not in_docstring:
                    in_docstring = True
                    docstring_start = i
                else:
                    in_docstring = False
            elif count == 2:
                # Complete docstring on one line
                pass

        # If we see imports while in docstring, close the docstring
        if in_docstring and (
            line.strip().startswith("from ") or line.strip().startswith("import ")
        ):
            # Insert closing quotes before this line
            if docstring_start >= 0 and docstring_start < len(fixed_lines):
                # Find the last non-empty line before imports
                for j in range(i - 1, docstring_start, -1):
                    if fixed_lines[j].strip():
                        fixed_lines[j] = fixed_lines[j] + '"""'
                        break
                else:
                    fixed_lines[docstring_start] = fixed_lines[docstring_start] + '"""'
            in_docstring = False
            fixed_lines.append("")  # Add blank line after docstring

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_all_syntax_patterns(content: str) -> str:
    """Apply all syntax fixes."""

    # Fix __future__ imports - must be at top
    lines = content.split("\n")
    future_imports = []
    other_lines = []

    for line in lines:
        if "from __future__ import" in line:
            future_imports.append(line)
        else:
            other_lines.append(line)

    if future_imports:
        content = "\n".join(future_imports + [""] + other_lines)

    # Fix empty imports
    content = re.sub(r"from\s+[\w.]+\s+import\s+\(\s*\)\s*\n", "", content)

    # Fix split function calls - multiple patterns
    content = re.sub(r'(\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)
    content = re.sub(r'\.(\w+)\(\)\s*\n\s*(["\'])', r".\1(\2", content)
    content = re.sub(r"(raise\s+\w+)\(\)\s*\n\s*\(", r"\1(", content)
    content = re.sub(r"(return\s+\w+)\(\)\s*\n\s*\(", r"\1(", content)

    # Fix logging format strings
    content = re.sub(
        r'LOGGER\.\w+\("([^"]*%s[^"]*)", ([^:]+):\.(\d+)f\)',
        r'LOGGER.\1("\1", \2)',
        content,
    )

    # Fix unterminated strings
    lines = content.split("\n")
    fixed_lines = []
    for line in lines:
        # Count quotes
        if line.count('"') % 2 == 1 and not line.strip().endswith('"'):
            if 'f"' in line or 'r"' in line:
                line = line.rstrip() + '"'
        if line.count("'") % 2 == 1 and not line.strip().endswith("'"):
            if "f'" in line or "r'" in line:
                line = line.rstrip() + "'"
        fixed_lines.append(line)
    content = "\n".join(fixed_lines)

    # Fix unmatched closing parentheses
    lines = content.split("\n")
    fixed_lines = []
    for i, line in enumerate(lines):
        # Skip lines that are just closing parens
        if line.strip() in [")", "),", ");"]:
            # Check if we need it
            if i > 0 and fixed_lines:
                prev_line = fixed_lines[-1]
                open_count = prev_line.count("(") - prev_line.count(")")
                if open_count > 0:
                    fixed_lines[-1] = prev_line.rstrip() + line.strip()
                    continue
            # Skip the line
            continue
        fixed_lines.append(line)
    content = "\n".join(fixed_lines)

    # Fix duplicate except blocks
    content = re.sub(r"(\s*except[^:]+:\s*\n)\s*\1", r"\1", content)

    # Add pass to empty blocks
    lines = content.split("\n")
    fixed_lines = []
    for i, line in enumerate(lines):
        fixed_lines.append(line)

        # If this line ends with : and next line is dedented or another block
        if line.strip().endswith(":") and not line.strip().startswith("#"):
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                current_indent = len(line) - len(line.lstrip())
                next_indent = (
                    len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
                )

                # Check if next line is dedented or starts new block
                if next_line.strip() and (
                    next_indent <= current_indent
                    or next_line.strip().startswith(
                        ("class ", "def ", "except", "elif", "else", "finally")
                    )
                ):
                    # Add pass
                    indent = " " * (current_indent + 4)
                    fixed_lines.append(indent + "pass")

    return "\n".join(fixed_lines)


def process_file(file_path: Path) -> Tuple[bool, str]:
    """Process a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content

        # Apply fixes
        content = fix_docstring_code_mix(content)
        content = fix_all_syntax_patterns(content)

        # Try to parse it
        try:
            ast.parse(content)
            if content != original:
                file_path.write_text(content, encoding="utf-8")
                return True, "Fixed"
            return False, "No changes needed"
        except SyntaxError as e:
            # Try one more aggressive fix
            content = content.replace(":.1f)", ")")
            content = content.replace(":.0f)", ")")
            content = content.replace(":.2f)", ")")

            try:
                ast.parse(content)
                file_path.write_text(content, encoding="utf-8")
                return True, "Fixed with aggressive patterns"
            except:
                return False, f"Still has errors: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Fix all remaining syntax errors."""
    # Get list of files with errors from our diagnostic
    error_files = """
    goesvfi/date_sorter/view_model.py
    goesvfi/gui_components/preview_manager.py
    goesvfi/gui_enhancements_integration.py
    goesvfi/integrity_check/combined_tab_refactored.py
    goesvfi/integrity_check/dark_mode_style.py
    goesvfi/integrity_check/date_range_selector.py
    goesvfi/integrity_check/enhanced_gui_tab_improved.py
    goesvfi/integrity_check/enhanced_imagery_tab.py
    goesvfi/integrity_check/enhanced_timeline.py
    goesvfi/integrity_check/enhanced_view_model.py
    goesvfi/integrity_check/goes_imagery.py
    goesvfi/integrity_check/goes_imagery_tab.py
    goesvfi/integrity_check/gui_tab.py
    goesvfi/integrity_check/optimized_dark_mode.py
    goesvfi/integrity_check/optimized_timeline_tab.py
    goesvfi/integrity_check/reconcile_manager.py
    goesvfi/integrity_check/reconcile_manager_refactored.py
    goesvfi/integrity_check/reconciler.py
    goesvfi/integrity_check/remote_store.py
    goesvfi/integrity_check/results_organization.py
    goesvfi/integrity_check/sample_processor.py
    goesvfi/integrity_check/satellite_integrity_tab_group.py
    goesvfi/integrity_check/shared_components.py
    goesvfi/integrity_check/signal_manager.py
    goesvfi/integrity_check/standardized_combined_tab.py
    goesvfi/integrity_check/tasks.py
    goesvfi/integrity_check/thread_cache_db.py
    goesvfi/integrity_check/time_index.py
    goesvfi/integrity_check/time_index_refactored.py
    goesvfi/integrity_check/timeline_visualization.py
    goesvfi/integrity_check/user_feedback.py
    goesvfi/integrity_check/visual_date_picker.py
    goesvfi/integrity_check/visualization_manager.py
    goesvfi/pipeline/cache.py
    goesvfi/pipeline/encode.py
    goesvfi/pipeline/ffmpeg_builder.py
    goesvfi/pipeline/image_cropper.py
    goesvfi/pipeline/image_loader.py
    goesvfi/pipeline/image_processing_interfaces.py
    goesvfi/pipeline/image_saver.py
    goesvfi/pipeline/interpolate.py
    goesvfi/pipeline/loader.py
    goesvfi/pipeline/raw_encoder.py
    goesvfi/pipeline/run_ffmpeg.py
    goesvfi/pipeline/run_vfi.py
    goesvfi/pipeline/sanchez_processor.py
    goesvfi/pipeline/tiler.py
    goesvfi/run_vfi.py
    goesvfi/utils/date_utils.py
    goesvfi/utils/debug_mode.py
    goesvfi/utils/enhanced_log.py
    goesvfi/utils/gui_helpers.py
    goesvfi/utils/logging_integration.py
    goesvfi/utils/memory_manager.py
    goesvfi/utils/operation_history.py
    goesvfi/utils/rife_analyzer.py
    goesvfi/utils/ui_enhancements.py
    goesvfi/utils/ui_security_indicators.py
    goesvfi/view_models/main_window_view_model.py
    """.strip().split(
        "\n"
    )

    print(f"Fixing {len(error_files)} files with syntax errors...")
    print("=" * 80)

    fixed = 0
    failed = []

    for file_name in error_files:
        file_path = Path(file_name.strip())
        if file_path.exists():
            success, message = process_file(file_path)
            if success:
                fixed += 1
                print(f"✓ Fixed: {file_path}")
            else:
                failed.append((file_path, message))
                if "Still has errors" in message:
                    print(f"✗ Failed: {file_path} - {message}")

    print("=" * 80)
    print(f"Fixed {fixed} out of {len(error_files)} files")

    if failed:
        print(f"\n{len(failed)} files still have errors")


if __name__ == "__main__":
    main()
