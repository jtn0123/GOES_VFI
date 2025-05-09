"""exceptions.py

Defines custom exception classes for the GOES_VFI application, providing
clear error types for pipeline processing, configuration, GUI operations,
and external tool execution.

All exceptions inherit from GoesVfiError, allowing for unified error handling.
"""

from typing import Optional

class GoesVfiError(Exception):
    """Base class for all GOES_VFI application-specific errors.

    All custom exceptions in the GOES_VFI application should inherit from this class.
    """
    pass

# Alias for consistent naming
GoesvfiError = GoesVfiError

class PipelineError(GoesVfiError):
    """Exception raised for errors occurring during pipeline processing.

    This error indicates a failure or issue within the main data processing pipeline.
    """
    pass

class ConfigurationError(GoesVfiError):
    """Exception raised for errors related to application configuration.

    This error is used when configuration values are missing, invalid, or inconsistent.
    """
    pass

class GuiError(GoesVfiError):
    """Exception raised for errors related to GUI operation.

    This error indicates a problem with the graphical user interface logic or state.
    """
    pass

class ExternalToolError(PipelineError):
    """Exception raised when an external tool (e.g., FFmpeg, Sanchez) fails to execute.

    This error is used to wrap errors from subprocesses or third-party tools invoked by the pipeline.
    """

    def __init__(self, tool_name: str, message: str, stderr: Optional[str] = None):
        """Initialize an ExternalToolError.

        Args:
            tool_name (str): The name of the external tool that failed.
            message (str): A description of the error.
            stderr (Optional[str]): The standard error output from the tool, if available.
        """
        self.tool_name = tool_name
        self.stderr = stderr
        super().__init__(f"Error executing {tool_name}: {message}")