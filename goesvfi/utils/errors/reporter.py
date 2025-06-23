"""
Error reporting utilities.

Provides consistent error reporting to reduce complexity in error display logic.
"""

import sys
from typing import Optional, TextIO

from .base import StructuredError


class ErrorReporter:
    """Formats and reports structured errors."""

    def __init__(self, output: Optional[TextIO] = None, verbose: bool = False):
        self.output = output or sys.stderr
        self.verbose = verbose

    def report_error(self, error: StructuredError) -> None:
        """Report a structured error."""
        if self.verbose:
            self._report_verbose(error)
        else:
            self._report_simple(error)

    def _report_simple(self, error: StructuredError) -> None:
        """Report simple error message."""
        self.output.write(f"Error: {error.user_message}\n")

        if error.suggestions:
            self.output.write("\nSuggestions:\n")
            for suggestion in error.suggestions:
                self.output.write(f"  • {suggestion}\n")

    def _report_verbose(self, error: StructuredError) -> None:
        """Report detailed error information."""
        self.output.write(
            f"Error in {error.context.component} ({error.category.name}):\n"
        )
        self.output.write(f"  Message: {error.message}\n")
        self.output.write(f"  Operation: {error.context.operation}\n")
        self.output.write(f"  Recoverable: {error.recoverable}\n")

        if error.context.user_data:
            self.output.write("  Context:\n")
            for key, value in error.context.user_data.items():
                self.output.write(f"    {key}: {value}\n")

        if error.suggestions:
            self.output.write("  Suggestions:\n")
            for suggestion in error.suggestions:
                self.output.write(f"    • {suggestion}\n")

        if error.cause and self.verbose:
            self.output.write(f"  Caused by: {error.cause}\n")
