#!/usr/bin/env python3
"""
Script to fix f-string formatting issues in goesvfi/gui.py
"""
import re
from pathlib import Path

def fix_fstring_quotes(file_path):
    """Fix f-string quotes by using !r conversion flag instead of manual quotes."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Regular expression to find f-strings with manual quotes
    # Pattern: f"...'{variable}'..." -> f"...{variable!r}..."
    pattern = r"f\"([^\"]*)'([^']+)'([^\"]*)\""
    
    # Function to replace matched patterns
    def replace_quotes(match):
        prefix = match.group(1)
        var_name = match.group(2)
        suffix = match.group(3)
        
        # Check if the variable is a simple identifier
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_\.]*$', var_name):
            return f'f"{prefix}{{{var_name}!r}}{suffix}"'
        else:
            # If it's a complex expression, leave it as is
            return match.group(0)
    
    # Apply the replacement
    fixed_content = re.sub(pattern, replace_quotes, content)
    
    # Write back the fixed content
    with open(file_path, 'w') as f:
        f.write(fixed_content)
    
    print(f"Fixed f-string quotes in {file_path}")

if __name__ == "__main__":
    # Fix gui.py
    gui_path = Path("goesvfi/gui.py")
    if gui_path.exists():
        # Create a backup
        backup_dir = Path("linting_backups/goesvfi")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / "gui.py.fstring_fix.bak"
        import shutil
        shutil.copy2(gui_path, backup_path)
        print(f"Created backup: {backup_path}")
        
        # Fix the file
        fix_fstring_quotes(gui_path)
    else:
        print(f"File not found: {gui_path}")