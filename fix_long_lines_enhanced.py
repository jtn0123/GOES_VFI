#!/usr/bin/env python3
"""
Fix B950 errors (lines too long) by splitting them into multiple lines.

This script identifies and fixes lines that exceed the maximum line length (88 characters)
by applying appropriate line splitting strategies based on the content type:
- For f-strings and strings: Split into multiple concatenated strings
- For function calls with many arguments: Format arguments on separate lines
- For assignments with long expressions: Break after operators

Script features:
- Creates backups before any modifications
- Uses different strategies for different types of long lines
- Handles f-strings, logging, and function calls intelligently
- Provides dry-run mode to preview changes
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Tuple

# ANSI color constants
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Maximum line length (matches Black's default)
MAX_LINE_LENGTH = 88


def print_colored(message: str, color: str = RESET, bold: bool = False) -> None:
    """Print a message with color."""
    if bold:
        print(f"{BOLD}{color}{message}{RESET}")
    else:
        print(f"{color}{message}{RESET}")


def get_long_lines(file_path: str) -> List[Tuple[int, str]]:
    """
    Find B950 issues in a file using flake8.
    Returns list of (line_number, error_message) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=B950", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: B950 line too long", line)
            if match:
                line_num = int(match.group(1))
                issues.append((line_num, "line too long"))
        
        return issues
    
    except Exception as e:
        print_colored(f"Error running flake8: {e}", RED)
        return []


def create_backup(file_path: str) -> str:
    """
    Create a backup of the file before modification.
    Returns the backup path.
    """
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".linelength.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_fstring_line(line: str, indent: str) -> str:
    """Fix a long f-string line by splitting it into multiple concatenated strings."""
    # If it's an f-string
    if 'f"' in line or "f'" in line:
        # Determine the main string delimiter used
        delimiter = '"' if 'f"' in line else "'"
        
        # Try to find a good breaking point (prefer spaces)
        max_segment_length = MAX_LINE_LENGTH - len(indent) - 3  # Account for f", continuation char and indentation
        
        # Extract the string part from the f-string
        string_start = line.index(f'f{delimiter}') + 2
        string_end = line.rindex(delimiter)
        
        # Get the prefix before the f-string
        prefix = line[:string_start - 2]
        
        # Get the suffix after the f-string
        suffix = line[string_end + 1:]
        
        # Extract the string content
        content = line[string_start:string_end]
        
        # Find good break points (prefer after punctuation and spaces)
        break_points = []
        for i in range(min(max_segment_length, len(content) - 1), 0, -1):
            if content[i] in ' .,;:)]}':
                break_points.append(i + 1)
        
        # If no good break points found, just break at the maximum length
        if not break_points:
            break_points = [min(max_segment_length, len(content))]
        
        break_point = break_points[0]
        
        # Split the string
        first_part = content[:break_point]
        second_part = content[break_point:]
        
        # Create the split line with proper continuation
        # Make sure to use both f-strings for both parts to handle variables correctly
        # We need to check for edge cases where placeholders would be split
        if '{' in first_part and '}' not in first_part:
            # Search for the nearest closing brace in the second part
            brace_pos = second_part.find('}')
            if brace_pos >= 0:
                # Move the variable placeholder to the first part
                brace_pos += 1  # Include the closing brace
                first_part += second_part[:brace_pos]
                second_part = second_part[brace_pos:]
        
        result = f"{prefix}f{delimiter}{first_part}{delimiter} \\\n{indent}f{delimiter}{second_part}{delimiter}{suffix}"
        
        # If the result is still too long, we might need to recursively split again
        if len(result.split('\n')[-1]) > MAX_LINE_LENGTH:
            # Process the newly created line (split again if needed)
            split_lines = result.split('\n')
            last_line = split_lines[-1]
            fixed_last_line = fix_fstring_line(last_line, indent)
            
            if '\n' in fixed_last_line:
                # Return all previous lines plus the newly split lines
                return '\n'.join(split_lines[:-1] + fixed_last_line.split('\n'))
            else:
                # Just replace the last line
                split_lines[-1] = fixed_last_line
                return '\n'.join(split_lines)
        
        return result
    
    return line


def fix_function_call(line: str, indent: str) -> str:
    """Split a long function call by putting arguments on separate lines."""
    # Check if this is a function call with arguments
    if '(' in line and ')' in line and not line.strip().startswith('#'):
        # Find the opening parenthesis position
        open_paren_pos = line.index('(')
        function_name = line[:open_paren_pos].strip()
        
        # Check if there are arguments and a closing parenthesis
        if line.count('(') == line.count(')'):
            # Extract arguments part
            args_part = line[open_paren_pos + 1:line.rindex(')')]
            
            # If there are arguments to split
            if args_part.strip():
                # Find the arguments by splitting on commas, but handle commas inside parentheses/brackets
                depth = 0
                args = []
                current_arg = ""
                
                for char in args_part:
                    if char in '([{':
                        depth += 1
                    elif char in ')]}':
                        depth -= 1
                    
                    if char == ',' and depth == 0:
                        args.append(current_arg.strip())
                        current_arg = ""
                    else:
                        current_arg += char
                
                # Add the last argument
                if current_arg.strip():
                    args.append(current_arg.strip())
                
                # Reconstruct with arguments on separate lines
                result = f"{function_name}(\n"
                for i, arg in enumerate(args):
                    if i < len(args) - 1:
                        result += f"{indent}    {arg},\n"
                    else:
                        result += f"{indent}    {arg}\n"
                result += f"{indent}){line[line.rindex(')')+1:]}"
                
                return result
    
    return line


def fix_long_assignment(line: str, indent: str) -> str:
    """Split a long assignment statement by breaking at operators."""
    # Check if this is an assignment with a long expression
    if ' = ' in line and not line.strip().startswith('#'):
        var_name, expression = line.split(' = ', 1)
        
        # Try to break after operators
        for op in [' + ', ' - ', ' * ', ' / ', ' and ', ' or ', ', ']:
            if op in expression:
                # Find the last occurrence of the operator that keeps the first line under the limit
                last_good_pos = 0
                for m in re.finditer(re.escape(op), expression):
                    if len(f"{var_name} = {expression[:m.start()]}{op.rstrip()}") <= MAX_LINE_LENGTH:
                        last_good_pos = m.start()
                
                if last_good_pos > 0:
                    # Split at this position
                    first_part = expression[:last_good_pos] + op.rstrip()
                    second_part = expression[last_good_pos + len(op.rstrip()):]
                    
                    return f"{var_name} = {first_part} \\\n{indent}    {second_part}"
    
    return line


def fix_logging_statement(line: str, indent: str) -> str:
    """Fix a long logging statement by splitting the message across multiple lines."""
    # Check if this is a logging statement
    if any(log_func in line for log_func in ['.debug(', '.info(', '.warning(', '.error(', '.critical(']):
        for log_func in ['.debug(', '.info(', '.warning(', '.error(', '.critical(']:
            if log_func in line:
                # Extract the parts
                logger_part = line[:line.index(log_func) + len(log_func)]
                message_part = line[line.index(log_func) + len(log_func):]
                
                # If the message part ends with a closing parenthesis
                if message_part.strip().endswith(')'):
                    message_content = message_part[:-1].strip()
                    
                    # Handle f-strings in the message
                    if 'f"' in message_content or "f'" in message_content:
                        # Create a temporary line with just the f-string
                        temp_line = f"{indent}temp = {message_content}"
                        fixed_temp = fix_fstring_line(temp_line, indent)
                        
                        # Extract the fixed f-string parts
                        if '\n' in fixed_temp:
                            fixed_parts = fixed_temp.strip().split('\n')
                            assignment_part = fixed_parts[0].split(' = ', 1)[1]
                            continuation_parts = [p.strip() for p in fixed_parts[1:]]
                            
                            # Reconstruct the logging statement
                            result = f"{logger_part}{assignment_part} \\\n"
                            for part in continuation_parts:
                                result += f"{indent}    {part} \\\n"
                            result = result[:-3] + ")"  # Remove the last continuation and add closing paren
                            
                            return result
                    
                    # For simple strings without formatting, just break after a reasonable length
                    if len(message_content) > MAX_LINE_LENGTH - len(logger_part) - len(indent) - 10:
                        max_first_part = MAX_LINE_LENGTH - len(logger_part) - len(indent) - 3
                        # Find a good break point
                        break_points = []
                        for i in range(min(max_first_part, len(message_content) - 1), 0, -1):
                            if message_content[i] in ' .,;:)]}':
                                break_points.append(i + 1)
                        
                        if break_points:
                            break_point = break_points[0]
                            first_part = message_content[:break_point]
                            second_part = message_content[break_point:]
                            
                            return f"{logger_part}{first_part} \\\n{indent}    {second_part})"
    
    return line


def fix_file_long_lines(file_path: str, dry_run: bool = False) -> int:
    """
    Fix B950 issues in a single file.
    Returns the number of lines fixed.
    """
    print_colored(f"\nChecking for long lines in {file_path}", BLUE, bold=True)
    
    # Get long lines
    issues = get_long_lines(file_path)
    
    if not issues:
        print_colored("No long lines found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} long lines:", YELLOW)
    for line_num, _ in issues:
        print(f"  Line {line_num}: line too long")
    
    if dry_run:
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(issues)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Read the file as lines
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each issue
    fixed_count = 0
    line_offset = 0  # Track line offset due to multi-line replacements
    
    for line_num, _ in sorted(issues):
        adjusted_idx = line_num - 1 + line_offset
        
        if adjusted_idx < 0 or adjusted_idx >= len(lines):
            print_colored(f"Warning: Invalid line number {line_num + line_offset}", RED)
            continue
        
        original_line = lines[adjusted_idx]
        indent = re.match(r'^(\s*)', original_line).group(1)
        
        # Apply different fixing strategies based on line content
        fixed_line = original_line
        
        # Try each fixing strategy until one works or all fail
        if 'f"' in original_line or "f'" in original_line:
            fixed_line = fix_fstring_line(original_line, indent)
        elif any(log_func in original_line for log_func in ['.debug(', '.info(', '.warning(', '.error(', '.critical(']):
            fixed_line = fix_logging_statement(original_line, indent)
        elif '(' in original_line and ')' in original_line:
            fixed_line = fix_function_call(original_line, indent)
        elif ' = ' in original_line:
            fixed_line = fix_long_assignment(original_line, indent)
        
        # Check if the line was fixed (i.e., split into multiple lines)
        if fixed_line != original_line:
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {original_line.strip()}")
            print(f"  Fixed: {fixed_line.replace('\\n', '\\n  ')}")
            
            # Replace the original line with the fixed lines
            lines[adjusted_idx] = fixed_line
            
            # Update line offset if we added new lines
            line_offset += fixed_line.count('\n') - original_line.count('\n')
            fixed_count += 1
        else:
            print_colored(f"Could not automatically fix line {line_num} - manual review required", YELLOW)
            print(f"  {original_line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} long lines in {file_path}", GREEN, bold=True)
    else:
        print_colored("No changes needed or lines couldn't be automatically fixed", YELLOW)
    
    return fixed_count


def process_directory(directory_path: str, dry_run: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of fixed lines.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_long_lines(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_long_lines_enhanced.py [--dry-run] path/to/file.py")
        print("python fix_long_lines_enhanced.py [--dry-run] path/to/directory")
        return 1
    
    args = sys.argv[1:]
    dry_run = False
    
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    
    if not args:
        print_colored("Error: No path specified", RED)
        return 1
    
    path = args[0]
    
    if os.path.isfile(path):
        fix_file_long_lines(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal long lines fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())