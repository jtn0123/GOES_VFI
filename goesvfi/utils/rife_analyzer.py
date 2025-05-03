"""
RIFE CLI Analyzer - Utility to detect RIFE CLI capabilities

This module provides functionality to analyze the capabilities of the RIFE CLI executable,
helping to bridge the gap between what the application expects and what the executable
actually supports.
"""

import pathlib
import subprocess
import re
import logging
from typing import Dict, List, Optional, Set, Tuple, Any

# Set up logging
logger = logging.getLogger(__name__)


class RifeCapabilityDetector:
    """
    Detects and reports on the capabilities of a RIFE CLI executable.

    This class runs the RIFE executable with various flags to determine
    which options are supported, allowing the application to adapt its
    behavior accordingly.
    """

    def __init__(self, exe_path: pathlib.Path):
        """
        Initialize the detector with the path to the RIFE executable.

        Args:
            exe_path: Path to the RIFE CLI executable
        """
        if not exe_path.exists():
            raise FileNotFoundError(f"RIFE executable not found at: {exe_path}")

        self.exe_path = exe_path
        self._capabilities: Dict[str, bool] = {}
        self._version: Optional[str] = None
        self._help_text: Optional[str] = None
        self._supported_args: Set[str] = set()

        # Run detection
        self._detect_capabilities()

    def _run_help_command(self) -> Tuple[str, bool]:
        """
        Run the executable with --help flag and capture output.

        Returns:
            Tuple of (help_text, success_flag)
        """
        try:
            # Try with --help first (most common)
            result = subprocess.run(
                [str(self.exe_path), "--help"],
                capture_output=True,
                text=True,
                timeout=5,  # Timeout after 5 seconds
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout, True

            # Try with -h if --help fails
            result = subprocess.run(
                [str(self.exe_path), "-h"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout, True

            # If both fail but we have stderr output, use that
            if result.stderr:
                return result.stderr, False

            # Last resort: just run the executable with no args
            result = subprocess.run(
                [str(self.exe_path)], capture_output=True, text=True, timeout=5
            )
            return result.stdout or result.stderr or "No output", False

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout while running help command for {self.exe_path}")
            return "Timeout while getting help text", False
        except Exception as e:
            logger.error(f"Error running help command: {e}")
            return f"Error: {str(e)}", False

    def _detect_capabilities(self) -> None:
        """
        Detect the capabilities of the RIFE executable by analyzing help output.
        """
        help_text, success = self._run_help_command()
        self._help_text = help_text

        # Decode help_text if it's bytes
        if isinstance(help_text, bytes):
            try:
                help_text_str = help_text.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(
                    "Could not decode help text as UTF-8, attempting latin-1"
                )
                help_text_str = help_text.decode("latin-1", errors="ignore")
        else:
            help_text_str = help_text  # Assume it's already a string

        # --- Refined Logging Logic --- #
        if not success:
            if not help_text_str:
                # Use the exact message expected by the test
                logger.error("RIFE help command failed or produced no output.")
            else:
                # Log a slightly different message when *some* error text was captured
                logger.error(
                    f"RIFE help command failed. Help text/error captured: \n{help_text_str}"
                )
        # Optional: Log a warning if command succeeded but output looks bad
        elif (
            not help_text_str
            or "Error:" in help_text_str
            or "Timeout" in help_text_str
            or "No output" in help_text_str
        ):
            logger.warning(
                f"RIFE help command succeeded but output seems problematic: \n{help_text_str}"
            )
        # --- End Refined Logging --- #

        # Store default capabilities
        self._capabilities = {
            "tiling": False,
            "uhd": False,
            "tta_spatial": False,
            "tta_temporal": False,
            "thread_spec": False,
            "batch_processing": False,
            "timestep": False,
            "model_path": False,
            "gpu_id": False,
        }

        # Extract version if available
        version_match = re.search(
            r"version[:\s]+([0-9.]+)", help_text_str, re.IGNORECASE
        )
        if version_match:
            self._version = version_match.group(1)

        # Parse help text to find supported arguments
        arg_matches = re.finditer(
            r"^\s+-([a-zA-Z0-9])\s+.*", help_text_str, re.MULTILINE
        )
        for match in arg_matches:
            # Extract all possible groups and filter out None values
            arg = match.group(1)
            if arg:
                self._supported_args.add(arg)

        # Detect specific capabilities based on supported args and help text
        help_text_lower = help_text_str.lower()
        self._capabilities["tiling"] = (
            any(arg in self._supported_args for arg in ["t", "tile"])
            or "tile" in help_text_lower
        )
        self._capabilities["uhd"] = (
            any(arg in self._supported_args for arg in ["u", "uhd"])
            or "uhd" in help_text_lower
        )
        self._capabilities["tta_spatial"] = (
            any(arg in self._supported_args for arg in ["x", "tta-spatial"])
            or "spatial" in help_text_lower
        )
        self._capabilities["tta_temporal"] = (
            any(arg in self._supported_args for arg in ["z", "tta-temporal"])
            or "temporal" in help_text_lower
        )
        self._capabilities["thread_spec"] = (
            any(arg in self._supported_args for arg in ["j", "thread"])
            or "thread" in help_text_lower
        )
        self._capabilities["batch_processing"] = (
            any(arg in self._supported_args for arg in ["i", "input-pattern"])
            or "batch" in help_text_lower
        )
        self._capabilities["timestep"] = (
            any(arg in self._supported_args for arg in ["s", "timestep"])
            or "timestep" in help_text_lower
        )
        self._capabilities["model_path"] = (
            any(arg in self._supported_args for arg in ["m", "model"])
            or "model" in help_text_lower
        )
        self._capabilities["gpu_id"] = (
            any(arg in self._supported_args for arg in ["g", "gpu"])
            or "gpu" in help_text_lower
        )

        logger.info(f"RIFE capabilities detected: {self._capabilities}")

    @property
    def version(self) -> Optional[str]:
        """Get the detected version of the RIFE executable."""
        return self._version

    @property
    def help_text(self) -> Optional[str]:
        """Get the full help text from the RIFE executable."""
        return self._help_text

    @property
    def supported_args(self) -> Set[str]:
        """Get the set of supported argument names."""
        return self._supported_args

    def supports_tiling(self) -> bool:
        """Check if tiling is supported."""
        return self._capabilities.get("tiling", False)

    def supports_uhd(self) -> bool:
        """Check if UHD mode is supported."""
        return self._capabilities.get("uhd", False)

    def supports_tta_spatial(self) -> bool:
        """Check if spatial TTA is supported."""
        return self._capabilities.get("tta_spatial", False)

    def supports_tta_temporal(self) -> bool:
        """Check if temporal TTA is supported."""
        return self._capabilities.get("tta_temporal", False)

    def supports_thread_spec(self) -> bool:
        """Check if thread specification is supported."""
        return self._capabilities.get("thread_spec", False)

    def supports_batch_processing(self) -> bool:
        """Check if batch processing is supported."""
        return self._capabilities.get("batch_processing", False)

    def supports_timestep(self) -> bool:
        """Check if timestep specification is supported."""
        return self._capabilities.get("timestep", False)

    def supports_model_path(self) -> bool:
        """Check if model path specification is supported."""
        return self._capabilities.get("model_path", False)

    def supports_gpu_id(self) -> bool:
        """Check if GPU ID specification is supported."""
        return self._capabilities.get("gpu_id", False)


class RifeCommandBuilder:
    """
    Builds RIFE CLI commands based on detected capabilities.

    This class uses the RifeCapabilityDetector to determine which options
    are supported by the RIFE executable, and builds commands accordingly.
    """

    def __init__(self, exe_path: pathlib.Path):
        """
        Initialize the command builder with the path to the RIFE executable.

        Args:
            exe_path: Path to the RIFE CLI executable
        """
        self.exe_path = exe_path
        self.detector = RifeCapabilityDetector(exe_path)

    def build_command(
        self,
        input_frame1: pathlib.Path,
        input_frame2: pathlib.Path,
        output_path: pathlib.Path,
        options: Dict[str, Any],
    ) -> List[str]:
        """
        Build a RIFE command based on detected capabilities.

        Args:
            input_frame1: Path to the first input frame
            input_frame2: Path to the second input frame
            output_path: Path to the output frame
            options: Dictionary of options

        Returns:
            List of command arguments
        """
        cmd = [str(self.exe_path)]

        # Add required arguments
        cmd.extend(["-0", str(input_frame1)])
        cmd.extend(["-1", str(input_frame2)])
        cmd.extend(["-o", str(output_path)])

        # Add optional arguments based on capabilities

        # Model path
        if self.detector.supports_model_path() and options.get("model_path"):
            cmd.extend(["-m", str(options.get("model_path"))])

        # Timestep
        if self.detector.supports_timestep() and options.get("timestep") is not None:
            cmd.extend(["-s", str(options.get("timestep"))])

        # Number of frames
        if options.get("num_frames") is not None:
            cmd.extend(["-n", str(options.get("num_frames"))])

        # Tiling
        if options.get("tile_enable", False) and self.detector.supports_tiling():
            cmd.extend(["-t", str(options.get("tile_size", 256))])

        # UHD mode
        if options.get("uhd_mode", False) and self.detector.supports_uhd():
            cmd.append("-u")

        # TTA options
        if options.get("tta_spatial", False) and self.detector.supports_tta_spatial():
            cmd.append("-x")

        if options.get("tta_temporal", False) and self.detector.supports_tta_temporal():
            cmd.append("-z")

        # Thread specification
        if self.detector.supports_thread_spec() and options.get("thread_spec"):
            thread_spec_val = options.get("thread_spec")
            if thread_spec_val is not None:
                cmd.extend(["-j", str(thread_spec_val)])

        # GPU ID
        if self.detector.supports_gpu_id() and options.get("gpu_id") is not None:
            cmd.extend(["-g", str(options.get("gpu_id"))])

        return cmd


def analyze_rife_executable(exe_path: pathlib.Path) -> Dict[str, Any]:
    """
    Analyze a RIFE executable and return its capabilities.

    Args:
        exe_path: Path to the RIFE CLI executable

    Returns:
        Dictionary with capability information
    """
    detector = RifeCapabilityDetector(exe_path)

    return {
        "version": detector.version,
        "capabilities": {
            "tiling": detector.supports_tiling(),
            "uhd": detector.supports_uhd(),
            "tta_spatial": detector.supports_tta_spatial(),
            "tta_temporal": detector.supports_tta_temporal(),
            "thread_spec": detector.supports_thread_spec(),
            "batch_processing": detector.supports_batch_processing(),
            "timestep": detector.supports_timestep(),
            "model_path": detector.supports_model_path(),
            "gpu_id": detector.supports_gpu_id(),
        },
        "supported_args": list(detector.supported_args),
        "help_text": detector.help_text,
    }


if __name__ == "__main__":
    """
    When run as a script, analyze the RIFE executable specified as an argument.
    """
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python rife_analyzer.py <path_to_rife_executable>")
        sys.exit(1)

    exe_path = pathlib.Path(sys.argv[1])
    if not exe_path.exists():
        print(f"Error: File not found: {exe_path}")
        sys.exit(1)

    try:
        result = analyze_rife_executable(exe_path)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error analyzing RIFE executable: {e}")
        sys.exit(1)
