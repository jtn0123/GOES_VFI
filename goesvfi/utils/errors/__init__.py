"""
Error handling framework for reducing complexity in error-heavy functions.

This module provides structured error handling utilities that help reduce the complexity
of functions with extensive error handling and recovery logic.
"""

from .base import ErrorCategory, ErrorContext, StructuredError
from .classifier import ErrorClassifier
from .handler import ErrorHandler, ErrorHandlerChain
from .reporter import ErrorReporter
from .recovery import RecoveryManager, RecoveryStrategy

__all__ = [
    "ErrorCategory",
    "ErrorContext", 
    "StructuredError",
    "ErrorClassifier",
    "ErrorHandler",
    "ErrorHandlerChain",
    "ErrorReporter",
    "RecoveryManager",
    "RecoveryStrategy",
]