#!/usr/bin/env python3
"""
Fix unused imports in Python files.
"""
import os
import re
import sys
from pathlib import Path
import subprocess

def get_unused_imports(file_path):
    """Get unused imports using flake8."""
    result = subprocess.run(
        ["flake8", "--select=F401", file_path],
        capture_output=True,
        text=True
    )
    
    unused_imports = []
    for line in result.stdout.splitlines():
        match = re.search(r"F401 '([^']+)' imported but unused", line)
        if match:
            unused_imports.append(match.group(1))
    
    return unused_imports

def fix_unused_imports(file_path):
    """Fix unused imports in a Python file."""
    print(f"Fixing unused imports in {file_path}")
    
    # Create backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Get unused imports
    unused_imports = get_unused_imports(file_path)
    if not unused_imports:
        print("No unused imports found.")
        return
    
    print(f"Found {len(unused_imports)} unused imports: {', '.join(unused_imports)}")
    
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each line
    new_lines = []
    line_idx = 0
    
    while line_idx < len(lines):
        line = lines[line_idx]
        
        # Check if line is an import statement
        if line.strip().startswith("import ") or line.strip().startswith("from "):
            skip_line = False
            
            # Check if this import contains any unused imports
            for unused in unused_imports:
                # Check for simple imports: import foo
                if line.strip() == f"import {unused}" or line.strip() == f"import {unused}\n":
                    skip_line = True
                    print(f"Removing line: {line.strip()}")
                    break
                
                # Check for compound imports: import foo, bar
                if line.strip().startswith("import ") and ", " in line:
                    parts = line.strip().replace("import ", "").split(", ")
                    new_parts = [p for p in parts if p != unused and p != unused + "\n"]
                    
                    if len(new_parts) < len(parts):
                        # Some parts were removed
                        if new_parts:
                            new_line = "import " + ", ".join(new_parts) + "\n"
                            new_lines.append(new_line)
                        skip_line = True
                        print(f"Modified line: {line.strip()} -> {new_line.strip() if new_parts else 'REMOVED'}")
                        break
                
                # Check for from ... import ...
                if line.strip().startswith("from "):
                    if " import " in line:
                        module, imports = line.strip().split(" import ")
                        # Extract the module name
                        module = module.replace("from ", "")
                        
                        # Check if the import matches the format "module.name"
                        if unused.startswith(module + "."):
                            # Extract the imported name
                            imported_name = unused[len(module) + 1:]
                            
                            # Check if this name is in the imports
                            if imported_name in imports.split(", "):
                                new_imports = [i for i in imports.split(", ") if i != imported_name and i != imported_name + "\n"]
                                
                                if new_imports:
                                    new_line = f"from {module} import {', '.join(new_imports)}\n"
                                    new_lines.append(new_line)
                                skip_line = True
                                print(f"Modified line: {line.strip()} -> {new_line.strip() if new_imports else 'REMOVED'}")
                                break
                        
                        # Handle direct module imports like "from foo import bar" where unused is "foo.bar"
                        elif "." in unused and unused.split(".")[0] == module:
                            imported_name = unused.split(".")[-1]
                            if imported_name in imports.split(", "):
                                new_imports = [i for i in imports.split(", ") if i != imported_name and i != imported_name + "\n"]
                                
                                if new_imports:
                                    new_line = f"from {module} import {', '.join(new_imports)}\n"
                                    new_lines.append(new_line)
                                skip_line = True
                                print(f"Modified line: {line.strip()} -> {new_line.strip() if new_imports else 'REMOVED'}")
                                break
            
            # Special handling for multiline imports
            if line.strip().startswith("from ") and "(" in line and ")" not in line:
                # This is a multiline import
                from_part = line.strip()
                imports_part = []
                closing_idx = line_idx + 1
                
                # Find the closing parenthesis
                while closing_idx < len(lines) and ")" not in lines[closing_idx]:
                    imports_part.append(lines[closing_idx])
                    closing_idx += 1
                
                if closing_idx < len(lines):
                    imports_part.append(lines[closing_idx])
                    
                    # Extract module name
                    module = from_part.replace("from ", "").split(" import ")[0]
                    
                    # Process all imports
                    new_imports = []
                    modified = False
                    
                    for imp_line in imports_part:
                        imp_names = re.findall(r'([A-Za-z0-9_]+)[,\s\n]*', imp_line)
                        for name in imp_names:
                            full_name = f"{module}.{name}"
                            if full_name not in unused_imports and name not in unused_imports:
                                new_imports.append(name)
                            else:
                                modified = True
                                print(f"Removing import: {full_name}")
                    
                    if modified:
                        if new_imports:
                            # Reconstruct import statement
                            if len(new_imports) > 3:
                                new_lines.append(f"from {module} import (\n")
                                for name in new_imports[:-1]:
                                    new_lines.append(f"    {name},\n")
                                new_lines.append(f"    {new_imports[-1]},\n")
                                new_lines.append(")\n")
                            else:
                                new_lines.append(f"from {module} import {', '.join(new_imports)}\n")
                                
                        # Skip all the lines we've processed
                        line_idx = closing_idx
                        skip_line = True
            
            if not skip_line:
                new_lines.append(line)
        else:
            new_lines.append(line)
        
        line_idx += 1
    
    # Write changes back to file
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Fixed unused imports in {file_path}")
    
    # Run isort to organize imports
    subprocess.run(["isort", file_path])
    print(f"Organized imports with isort")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_imports.py FILE_PATH")
        sys.exit(1)
    
    fix_unused_imports(sys.argv[1])