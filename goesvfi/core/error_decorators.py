"""Error handling decorators for consistent error management.

This module provides decorators that standardize error handling patterns
across the codebase, reducing code duplication and ensuring consistent
error reporting and recovery.
"""

from collections.abc import Callable
import functools
import time
from typing import Any, Never, ParamSpec, TypeVar

from goesvfi.utils import log
from goesvfi.utils.errors import ErrorClassifier

LOGGER = log.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def with_error_handling(
    operation_name: str | None = None,
    component_name: str | None = None,
    default_return: Any = None,
    reraise: bool = True,
    log_level: str = "exception",
) -> Callable[[Callable[P, T]], Callable[P, T | Any]]:
    """Decorator for standardized error handling.

    Args:
        operation_name: Name of the operation (defaults to function name)
        component_name: Name of the component (defaults to module name)
        default_return: Value to return on error (if reraise=False)
        reraise: Whether to re-raise the exception after handling
        log_level: Logging level for errors ("exception", "error", "warning")

    Returns:
        Decorated function with error handling
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T | Any]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | Any:
            op_name = operation_name or func.__name__
            comp_name = component_name or func.__module__.split(".")[-1]

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Create structured error
                classifier = ErrorClassifier()
                error = classifier.create_structured_error(e, op_name, comp_name)

                # Log the error
                log_func = getattr(LOGGER, log_level, LOGGER.exception)
                log_func(
                    "[%s] %s failed: %s",
                    comp_name,
                    op_name,
                    error.user_message
                )

                # Re-raise or return default
                if reraise:
                    raise
                return default_return

        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for automatic retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback called on each retry with (attempt, exception)

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        # Call retry callback if provided
                        if on_retry:
                            on_retry(attempt + 1, e)

                        # Log retry attempt
                        LOGGER.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                            attempt + 1,
                            max_attempts,
                            func.__name__,
                            str(e),
                            current_delay
                        )

                        # Wait before retry
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        # Final attempt failed
                        LOGGER.exception(
                            "All %d attempts failed for %s",
                            max_attempts,
                            func.__name__
                        )

            # Re-raise the last exception
            if last_exception:
                raise last_exception

            # Should never reach here
            msg = f"Unexpected state in retry decorator for {func.__name__}"
            raise RuntimeError(msg)

        return wrapper
    return decorator


def with_timeout(
    timeout: float,
    timeout_error: type[Exception] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for function timeout (works with async functions).

    Note: For synchronous functions, this requires signal support (Unix-like systems).
    For cross-platform timeout support, use concurrent.futures.

    Args:
        timeout: Timeout in seconds
        timeout_error: Exception to raise on timeout (default: TimeoutError)

    Returns:
        Decorated function with timeout
    """
    import asyncio
    import signal
    from typing import cast

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Check if function is async
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                except TimeoutError as e:
                    if timeout_error:
                        msg = f"Function {func.__name__} timed out after {timeout}s"
                        raise timeout_error(msg) from e
                    raise

            return cast("Callable[P, T]", async_wrapper)
        # Synchronous function - use signal alarm (Unix only)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            def timeout_handler(signum, frame) -> Never:
                error_cls = timeout_error or TimeoutError
                msg = f"Function {func.__name__} timed out after {timeout}s"
                raise error_cls(msg)

            # Set up timeout
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))

            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel alarm and restore handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return sync_wrapper

    return decorator


def with_logging(
    log_args: bool = True,
    log_result: bool = False,
    log_time: bool = True,
    max_arg_length: int = 200,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for automatic function logging.

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        log_time: Whether to log execution time
        max_arg_length: Maximum length for logged arguments

    Returns:
        Decorated function with logging
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Prepare log message
            func_name = f"{func.__module__}.{func.__name__}"

            # Log function call
            if log_args:
                args_str = ", ".join(
                    str(arg)[:max_arg_length] for arg in args
                )
                kwargs_str = ", ".join(
                    f"{k}={str(v)[:max_arg_length]}" for k, v in kwargs.items()
                )
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                LOGGER.debug("Calling %s(%s)", func_name, all_args)
            else:
                LOGGER.debug("Calling %s", func_name)

            # Execute function
            start_time = time.time() if log_time else 0
            try:
                result = func(*args, **kwargs)

                # Log result
                if log_result:
                    LOGGER.debug(
                        "%s returned: %s",
                        func_name,
                        str(result)[:max_arg_length]
                    )

                return result
            finally:
                # Log execution time
                if log_time:
                    elapsed = time.time() - start_time
                    LOGGER.debug("%s took %.3fs", func_name, elapsed)

        return wrapper
    return decorator


def with_validation(
    validator: Callable[[P.args, P.kwargs], None] | None = None,
    validate_result: Callable[[T], None] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for input/output validation.

    Args:
        validator: Function to validate inputs (raises on invalid)
        validate_result: Function to validate result (raises on invalid)

    Returns:
        Decorated function with validation
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Validate inputs
            if validator:
                validator(args, kwargs)

            # Execute function
            result = func(*args, **kwargs)

            # Validate result
            if validate_result:
                validate_result(result)

            return result

        return wrapper
    return decorator


def deprecated(
    reason: str,
    version: str | None = None,
    alternative: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to mark functions as deprecated.

    Args:
        reason: Reason for deprecation
        version: Version when deprecated
        alternative: Alternative function/method to use

    Returns:
        Decorated function with deprecation warning
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import warnings

            message = f"{func.__name__} is deprecated"
            if version:
                message += f" as of version {version}"
            message += f": {reason}"
            if alternative:
                message += f". Use {alternative} instead."

            warnings.warn(message, DeprecationWarning, stacklevel=2)

            return func(*args, **kwargs)

        # Update docstring
        if func.__doc__:
            wrapper.__doc__ = f"DEPRECATED: {reason}\n\n{func.__doc__}"
        else:
            wrapper.__doc__ = f"DEPRECATED: {reason}"

        return wrapper
    return decorator


# Composite decorators for common patterns

def robust_operation(
    operation_name: str | None = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    log_args: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Composite decorator for robust operations with retry and error handling.

    Combines error handling, retry logic, and logging.

    Args:
        operation_name: Name of the operation
        max_retries: Maximum retry attempts
        retry_delay: Initial retry delay
        log_args: Whether to log arguments

    Returns:
        Decorated function
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Apply decorators in order
        func = with_logging(log_args=log_args, log_time=True)(func)
        func = with_retry(
            max_attempts=max_retries,
            delay=retry_delay,
            exceptions=(IOError, OSError, ConnectionError),
        )(func)
        return with_error_handling(
            operation_name=operation_name,
            reraise=True,
        )(func)

    return decorator


def async_safe(
    timeout: float | None = None,
    default_return: Any = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for safe async operations with timeout and error handling.

    Args:
        timeout: Optional timeout in seconds
        default_return: Value to return on error

    Returns:
        Decorated function
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        # Apply timeout if specified
        if timeout:
            func = with_timeout(timeout)(func)

        # Apply error handling
        return with_error_handling(
            reraise=False,
            default_return=default_return,
            log_level="error",
        )(func)

    return decorator
