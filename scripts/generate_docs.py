#!/usr/bin/env python3
"""Generate comprehensive API documentation for GOES_VFI.

This script automatically generates RST files for all modules in the codebase,
creates cross-references, and builds the complete documentation.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add the repository root to the Python path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))


def get_python_modules(package_path: Path) -> List[str]:
    """Get all Python modules in a package.

    Args:
        package_path: Path to the package directory

    Returns:
        List of module names (dot notation)
    """
    modules = []
    package_name = package_path.name

    for py_file in package_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if "__pycache__" in str(py_file):
            continue

        # Convert file path to module path
        relative_path = py_file.relative_to(package_path.parent)
        module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
        module_name = ".".join(module_parts)
        modules.append(module_name)

    return sorted(modules)


def generate_module_rst(module_name: str, output_dir: Path) -> None:
    """Generate RST file for a specific module.

    Args:
        module_name: Full module name (e.g., 'goesvfi.utils.config')
        output_dir: Directory to write RST files
    """
    module_parts = module_name.split(".")
    filename = "_".join(module_parts[1:]) + ".rst"  # Skip 'goesvfi' prefix
    output_file = output_dir / filename

    # Create title
    title = " ".join(word.title() for word in module_parts[-1].split("_"))
    title_line = "=" * len(title)

    content = f"""{title}
{title_line}

.. automodule:: {module_name}
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:

"""

    # Add special sections for certain modules
    if "exceptions" in module_name:
        content += """
Exception Hierarchy
-------------------

.. inheritance-diagram:: {module_name}
   :parts: 1

"""

    if "gui" in module_name and "tab" in module_name:
        content += """
Widget Hierarchy
----------------

This module provides GUI components for the main application interface.

"""

    if "pipeline" in module_name:
        content += """
Processing Flow
---------------

This module is part of the core processing pipeline for video frame interpolation.

"""

    output_file.write_text(content)
    print(f"Generated {output_file}")


def create_api_index(modules: List[str], output_dir: Path) -> None:
    """Create the main API index file.

    Args:
        modules: List of all module names
        output_dir: Directory to write the index file
    """
    # Group modules by category
    categories = {
        "Pipeline": [],
        "Integrity Check": [],
        "GUI Components": [],
        "Utilities": [],
        "Sanchez Integration": [],
        "Exceptions": [],
        "Other": [],
    }

    for module in modules:
        if module.startswith("goesvfi.pipeline"):
            categories["Pipeline"].append(module)
        elif module.startswith("goesvfi.integrity_check"):
            categories["Integrity Check"].append(module)
        elif module.startswith("goesvfi.gui"):
            categories["GUI Components"].append(module)
        elif module.startswith("goesvfi.utils"):
            categories["Utilities"].append(module)
        elif module.startswith("goesvfi.sanchez"):
            categories["Sanchez Integration"].append(module)
        elif "exception" in module:
            categories["Exceptions"].append(module)
        else:
            categories["Other"].append(module)

    content = """API Reference
=============

Complete API documentation for all GOES_VFI modules.

.. toctree::
   :maxdepth: 2
   :caption: API Documentation

"""

    for category, module_list in categories.items():
        if not module_list:
            continue

        content += (
            f"\n{category}\n{'-' * len(category)}\n\n.. toctree::\n   :maxdepth: 1\n\n"
        )

        for module in module_list:
            # Convert module name to filename
            module_parts = module.split(".")[1:]  # Skip 'goesvfi'
            filename = "_".join(module_parts)
            content += f"   {filename}\n"

        content += "\n"

    # Add indices
    content += """
Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

"""

    index_file = output_dir / "api_generated.rst"
    index_file.write_text(content)
    print(f"Generated {index_file}")


def create_class_hierarchy(modules: List[str], output_dir: Path) -> None:
    """Create class hierarchy documentation.

    Args:
        modules: List of all module names
        output_dir: Directory to write hierarchy files
    """
    content = """Class Hierarchy
===============

This page shows the inheritance relationships between classes in GOES_VFI.

Core Classes
------------

.. inheritance-diagram:: goesvfi.pipeline.run_vfi.VfiWorker goesvfi.pipeline.image_processing_interfaces.ImageProcessor
   :parts: 2

GUI Classes
-----------

.. inheritance-diagram:: goesvfi.gui.MainWindow goesvfi.gui_tabs.main_tab.MainTab
   :parts: 2

Exception Classes
-----------------

.. inheritance-diagram:: goesvfi.exceptions
   :parts: 2

"""

    hierarchy_file = output_dir / "class_hierarchy.rst"
    hierarchy_file.write_text(content)
    print(f"Generated {hierarchy_file}")


def generate_changelog(output_dir: Path) -> None:
    """Generate changelog from git history.

    Args:
        output_dir: Directory to write changelog
    """
    try:
        # Get git log
        result = subprocess.run(
            ["git", "log", "--oneline", "--no-merges", "-n", "50"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        if result.returncode == 0:
            content = """Changelog
=========

Recent Changes
--------------

.. code-block:: text

"""
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    content += f"   {line}\n"

            content += """

For complete history, see the `GitHub repository <https://github.com/username/GOES_VFI/commits/main>`_.

"""

            changelog_file = output_dir / "changelog.rst"
            changelog_file.write_text(content)
            print(f"Generated {changelog_file}")

    except Exception as e:
        print(f"Could not generate changelog: {e}")


def create_license_doc(output_dir: Path) -> None:
    """Create license documentation.

    Args:
        output_dir: Directory to write license file
    """
    license_content = """License
=======

MIT License
-----------

Copyright (c) 2024 GOES_VFI Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Dependencies
------------

GOES_VFI uses several open-source libraries. See the ``requirements.txt`` file
for a complete list of dependencies and their licenses.

Key Dependencies:

- **PyQt6**: GPL v3 / Commercial License
- **NumPy**: BSD License
- **Pillow**: PIL License (MIT-like)
- **OpenCV**: Apache 2.0 License
- **FFmpeg**: LGPL / GPL (depending on build)
- **Matplotlib**: Matplotlib License (BSD-like)

Contributing
------------

By contributing to GOES_VFI, you agree that your contributions will be licensed
under the same MIT License that covers the project.

"""

    license_file = output_dir / "license.rst"
    license_file.write_text(license_content)
    print(f"Generated {license_file}")


def run_sphinx_build(docs_dir: Path, format: str = "html") -> bool:
    """Run Sphinx build process.

    Args:
        docs_dir: Documentation source directory
        format: Output format (html, pdf, epub)

    Returns:
        True if build successful, False otherwise
    """
    build_dir = docs_dir / "_build" / format

    try:
        cmd = [
            "sphinx-build",
            "-b",
            format,
            "-W",  # Treat warnings as errors
            str(docs_dir),
            str(build_dir),
        ]

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Successfully built {format} documentation")
            print(f"   Output: {build_dir}")
            return True
        else:
            print(f"❌ Failed to build {format} documentation")
            print(f"   Error: {result.stderr}")
            return False

    except FileNotFoundError:
        print("❌ Sphinx not found. Install with: pip install sphinx")
        return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False


def check_doc_coverage(modules: List[str]) -> Dict[str, float]:
    """Check documentation coverage for modules.

    Args:
        modules: List of module names to check

    Returns:
        Dictionary mapping module names to coverage percentages
    """
    coverage = {}

    for module in modules:
        try:
            # Import the module
            mod = __import__(module, fromlist=[""])

            # Count functions and classes
            total_items = 0
            documented_items = 0

            for name in dir(mod):
                if name.startswith("_"):
                    continue

                item = getattr(mod, name)
                if callable(item) or isinstance(item, type):
                    total_items += 1
                    if hasattr(item, "__doc__") and item.__doc__:
                        documented_items += 1

            if total_items > 0:
                coverage[module] = (documented_items / total_items) * 100
            else:
                coverage[module] = 100.0

        except Exception as e:
            print(f"Could not check coverage for {module}: {e}")
            coverage[module] = 0.0

    return coverage


def main():
    """Main function to generate documentation."""
    parser = argparse.ArgumentParser(description="Generate GOES_VFI documentation")
    parser.add_argument(
        "--build", action="store_true", help="Build documentation after generation"
    )
    parser.add_argument(
        "--format",
        default="html",
        choices=["html", "pdf", "epub"],
        help="Output format",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Show documentation coverage"
    )
    args = parser.parse_args()

    print("🔧 Generating GOES_VFI API Documentation")
    print("=" * 50)

    # Paths
    goesvfi_path = repo_root / "goesvfi"
    docs_dir = repo_root / "docs"
    api_dir = docs_dir / "api"

    # Create API directory
    api_dir.mkdir(exist_ok=True)

    # Get all modules
    print("📦 Discovering modules...")
    modules = get_python_modules(goesvfi_path)
    print(f"   Found {len(modules)} modules")

    # Generate individual module documentation
    print("📝 Generating module documentation...")
    for module in modules:
        try:
            generate_module_rst(module, api_dir)
        except Exception as e:
            print(f"   ❌ Failed to generate docs for {module}: {e}")

    # Generate main API index
    print("📋 Creating API index...")
    create_api_index(modules, api_dir)

    # Generate class hierarchy
    print("🏗️  Creating class hierarchy...")
    create_class_hierarchy(modules, api_dir)

    # Generate additional documentation
    print("📄 Generating additional documentation...")
    generate_changelog(docs_dir)
    create_license_doc(docs_dir)

    # Check documentation coverage
    if args.coverage:
        print("📊 Checking documentation coverage...")
        coverage = check_doc_coverage(modules)

        total_coverage = sum(coverage.values()) / len(coverage) if coverage else 0
        print(f"   Overall coverage: {total_coverage:.1f}%")

        # Show modules with low coverage
        low_coverage = {k: v for k, v in coverage.items() if v < 50}
        if low_coverage:
            print("   Modules with low coverage:")
            for module, cov in sorted(low_coverage.items(), key=lambda x: x[1]):
                print(f"     {module}: {cov:.1f}%")

    # Build documentation
    if args.build:
        print(f"🔨 Building {args.format} documentation...")
        success = run_sphinx_build(docs_dir, args.format)

        if success:
            print("✅ Documentation generation complete!")
            build_path = docs_dir / "_build" / args.format
            if args.format == "html":
                print(f"   Open: {build_path / 'index.html'}")
        else:
            print("❌ Documentation build failed!")
            return 1
    else:
        print("✅ Documentation files generated!")
        print("   Run with --build to create HTML output")

    print(f"\n📁 Documentation files created in: {docs_dir}")
    print("🌐 To build and serve locally:")
    print("   cd docs && make html && make serve")

    return 0


if __name__ == "__main__":
    sys.exit(main())
