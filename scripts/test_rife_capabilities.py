#!/usr/bin/env python3
"""
Test script for RIFE CLI capability detection.

This script finds the RIFE CLI executable, analyzes its capabilities,
and prints a report. It's useful for debugging and for users to check
if their RIFE CLI executable supports the features they need.

Usage:
    python test_rife_capabilities.py [model_key]
"""

import argparse
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from goesvfi.utils.config import find_rife_executable
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Test RIFE CLI capability detection")
    parser.add_argument(
        "model_key",
        nargs="?",
        default="rife-v4.6",
        help="Model key to use (default: rife-v4.6)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        # Find the RIFE executable
        logger.info("Finding RIFE executable for model key: %s", args.model_key)
        exe_path = find_rife_executable(args.model_key)
        logger.info("Found RIFE executable: %s", exe_path)

        # Create a capability detector
        logger.info("Analyzing RIFE capabilities...")
        detector = RifeCapabilityDetector(exe_path)

        # Print the results
        print("\n" + "=" * 60)
        print(f"RIFE CLI Capability Report for: {exe_path}")
        print("=" * 60)

        # Version
        print(f"Version: {detector.version or 'Unknown'}")
        print()

        # Capabilities
        print("Capabilities:")
        capabilities = {
            "tiling": detector.supports_tiling(),
            "uhd": detector.supports_uhd(),
            "tta_spatial": detector.supports_tta_spatial(),
            "tta_temporal": detector.supports_tta_temporal(),
            "thread_spec": detector.supports_thread_spec(),
            "batch_processing": detector.supports_batch_processing(),
            "timestep": detector.supports_timestep(),
            "model_path": detector.supports_model_path(),
            "gpu_id": detector.supports_gpu_id(),
        }

        for capability, supported in capabilities.items():
            status = "✅ Supported" if supported else "❌ Not supported"
            print(f"  {capability.ljust(15)}: {status}")
        print()

        # Supported arguments
        print("Supported Arguments:")
        args_list = detector.supported_args
        if args_list:
            print(f"  {', '.join(sorted(args_list))}")
        else:
            print("  None detected")
        print()

        # Help text (if verbose)
        if args.verbose and detector.help_text:
            print("Help Text:")
            print("-" * 60)
            print(detector.help_text)
            print("-" * 60)

        print("\nSummary:")
        supported_count = sum(1 for v in capabilities.values() if v)
        total_count = len(capabilities)
        print(f"  {supported_count}/{total_count} features supported")

        # Recommendation
        if supported_count < 5:
            print("\nRecommendation:")
            print("  This RIFE CLI executable has limited capabilities.")
            print("  Consider using a newer version with more features.")

        print("\n" + "=" * 60)

    except Exception as e:
        logger.exception("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
