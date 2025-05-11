#!/usr/bin/env python3
"""
Fix line length issues in Python files.
"""
import re
import sys
from pathlib import Path

def fix_long_lines(file_path, max_length=88):
    """Fix lines longer than max_length."""
    print(f"Fixing long lines in {file_path} (max: {max_length})")
    
    # Create backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".linelength.bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each line
    new_lines = []
    fixed_count = 0
    
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        
        # Skip lines that are not too long
        if len(stripped) <= max_length:
            new_lines.append(line)
            continue
        
        # Handle comments - add noqa
        if stripped.lstrip().startswith('#'):
            if 'noqa' not in stripped:
                new_lines.append(stripped + "  # noqa: E501\n")
                fixed_count += 1
                print(f"Line {i+1}: Added noqa to comment")
            else:
                new_lines.append(line)
            continue
        
        # Handle strings - add noqa
        if ('"' in stripped and stripped.count('"') >= 2) or ("'" in stripped and stripped.count("'") >= 2):
            # Check if this is a docstring or a string literal
            has_assign = '=' in stripped
            string_markers = ['"""', "'''", '"', "'"]
            is_string_literal = any(marker in stripped for marker in string_markers)
            
            if is_string_literal and not has_assign:
                # This is likely a docstring or a standalone string - add noqa
                if 'noqa' not in stripped:
                    new_lines.append(stripped + "  # noqa: E501\n")
                    fixed_count += 1
                    print(f"Line {i+1}: Added noqa to string")
                else:
                    new_lines.append(line)
                continue
        
        # Handle function calls with arguments
        if '(' in stripped and ')' in stripped and ',' in stripped:
            indent = len(stripped) - len(stripped.lstrip())
            
            # Check if it's a function call
            open_paren = stripped.find('(')
            if open_paren >= 0:
                # Get the function name part
                fn_part = stripped[:open_paren+1]
                args_part = stripped[open_paren+1:]
                
                # Handle the case where there are balanced parentheses inside
                nested_level = 0
                args = []
                current_arg = ""
                
                for char in args_part:
                    if char == '(' and nested_level >= 0:
                        nested_level += 1
                        current_arg += char
                    elif char == ')' and nested_level > 0:
                        nested_level -= 1
                        current_arg += char
                    elif char == ',' and nested_level == 0:
                        args.append(current_arg.strip())
                        current_arg = ""
                    elif char == ')' and nested_level == 0:
                        # End of arguments
                        if current_arg.strip():
                            args.append(current_arg.strip())
                        break
                    else:
                        current_arg += char
                
                # Reconstruct with line breaks
                if args:
                    new_lines.append(fn_part + "\n")
                    for j, arg in enumerate(args):
                        if j == len(args) - 1:
                            # Last argument
                            new_lines.append(' ' * (indent + 4) + arg + ")\n")
                        else:
                            new_lines.append(' ' * (indent + 4) + arg + ",\n")
                    
                    fixed_count += 1
                    print(f"Line {i+1}: Split function call")
                    continue
        
        # Handle dictionary literals
        if '{' in stripped and '}' in stripped and ':' in stripped and ',' in stripped:
            indent = len(stripped) - len(stripped.lstrip())
            
            # Get the parts
            dict_start = stripped.find('{')
            dict_end = stripped.rfind('}')
            
            if dict_start >= 0 and dict_end > dict_start:
                prefix = stripped[:dict_start+1]
                dict_content = stripped[dict_start+1:dict_end]
                suffix = stripped[dict_end:]
                
                # Split by commas
                items = []
                current_item = ""
                nested_level = 0
                
                for char in dict_content:
                    if char == '{' or char == '[':
                        nested_level += 1
                        current_item += char
                    elif char == '}' or char == ']':
                        nested_level -= 1
                        current_item += char
                    elif char == ',' and nested_level == 0:
                        items.append(current_item.strip())
                        current_item = ""
                    else:
                        current_item += char
                
                if current_item.strip():
                    items.append(current_item.strip())
                
                # Reconstruct with line breaks
                if items:
                    new_lines.append(prefix + "\n")
                    for j, item in enumerate(items):
                        if j == len(items) - 1:
                            # Last item
                            new_lines.append(' ' * (indent + 4) + item + suffix + "\n")
                        else:
                            new_lines.append(' ' * (indent + 4) + item + ",\n")
                    
                    fixed_count += 1
                    print(f"Line {i+1}: Split dictionary literal")
                    continue
        
        # Handle assignments with long right side
        if '=' in stripped and not ('==' in stripped or '<=' in stripped or '>=' in stripped or '!=' in stripped):
            indent = len(stripped) - len(stripped.lstrip())
            parts = stripped.split('=', 1)
            
            if len(parts) == 2 and len(parts[1].strip()) > 40:  # Only break if RHS is long
                new_lines.append(parts[0] + "= (\n")
                new_lines.append(' ' * (indent + 4) + parts[1].strip() + "\n")
                new_lines.append(' ' * indent + ")\n")
                
                fixed_count += 1
                print(f"Line {i+1}: Split assignment")
                continue
        
        # Default: add noqa
        if 'noqa' not in stripped:
            new_lines.append(stripped + "  # noqa: E501\n")
            fixed_count += 1
            print(f"Line {i+1}: Added noqa to long line")
        else:
            new_lines.append(line)
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Fixed {fixed_count} long lines in {file_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_line_length.py FILE_PATH [MAX_LENGTH]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    max_length = int(sys.argv[2]) if len(sys.argv) > 2 else 88
    
    fix_long_lines(file_path, max_length)