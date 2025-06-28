#!/usr/bin/env python3
"""
RIFE CLI Analyzer Script

This script analyzes a RIFE CLI executable and reports its capabilities.
It's useful for debugging and for users to check if their RIFE CLI executable
supports the features they need.

Usage:
    python analyze_rife_cli.py <path_to_rife_executable>
"""

import argparse
import json
import os
import pathlib
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from goesvfi.utils.rife_analyzer import analyze_rife_executable


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Analyze RIFE CLI executable capabilities"
    )
    parser.add_argument("executable", type=str, help="Path to the RIFE CLI executable")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output including help text",
    )
    args = parser.parse_args()

    # Convert the executable path to a pathlib.Path
    exe_path = pathlib.Path(args.executable)

    # Check if the executable exists
    if not exe_path.exists():
        print(f"Error: File not found: {exe_path}")
        sys.exit(1)

    try:
        # Analyze the executable
        result = analyze_rife_executable(exe_path)

        # Output the results
        if args.json:
            # Output in JSON format
            if not args.verbose:
                # Remove help text from JSON output unless verbose is specified
                result.pop("help_text", None)
            print(json.dumps(result, indent=2))
        else:
            # Output in human-readable format
            print(f"\nRIFE CLI Analyzer Results for: {exe_path}")
            print("=" * 80)

            # Version
            print(f"Version: {result.get('version', 'Unknown')}")
            print()

            # Capabilities
            print("Capabilities:")
            capabilities = result.get("capabilities", {})
            for capability, supported in capabilities.items():
                status = "✅ Supported" if supported else "❌ Not supported"
                print(f"  {capability.ljust(15)}: {status}")
            print()

            # Supported arguments
            print("Supported Arguments:")
            args_list = result.get("supported_args", [])
            if args_list:
                print(f"  {', '.join(sorted(args_list))}")
            else:
                print("  None detected")
            print()

            # Help text (if verbose)
            if args.verbose and "help_text" in result:
                print("Help Text:")
                print("-" * 80)
                print(result["help_text"])
                print("-" * 80)

    except Exception as e:
        print(f"Error analyzing RIFE executable: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
