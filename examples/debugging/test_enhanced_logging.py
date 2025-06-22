#!/usr/bin/env python3
"""Example demonstrating enhanced logging and debugging features."""

import asyncio
import sys
import time
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from goesvfi.utils.debug_mode import (
    debug_log,
    disable_debug_mode,
    enable_debug_mode,
    get_debug_manager,
    track_performance,
)
from goesvfi.utils.enhanced_log import (
    correlation_context,
    get_enhanced_logger,
    set_correlation_id,
    setup_json_logging,
)
from goesvfi.utils.operation_history import get_operation_store, track_operation

# Get logger instances
LOGGER = get_enhanced_logger(__name__)
JSON_LOGGER = get_enhanced_logger(__name__ + ".json", use_json=True)


@track_performance("example_calculation")
def complex_calculation(n: int) -> int:
    """Example function with performance tracking."""
    debug_log("calculation", f"Starting calculation with n={n}")

    # Simulate some work
    result = 0
    for i in range(n):
        result += i**2
        if i % 1000 == 0:
            debug_log("calculation", f"Progress: {i}/{n}")

    debug_log("calculation", f"Calculation complete: result={result}")
    return result


async def example_async_operation(name: str, delay: float) -> str:
    """Example async operation with tracking."""
    with track_operation(f"async_{name}", delay=delay) as op:
        LOGGER.info(f"Starting async operation: {name}")
        op.metadata["start_message"] = f"Operation {name} started"

        await asyncio.sleep(delay)

        result = f"Completed {name} after {delay}s"
        op.metadata["result"] = result

        LOGGER.info(f"Completed async operation: {name}")
        return result


def demonstrate_correlation_ids():
    """Demonstrate correlation ID usage."""
    print("\n=== Correlation ID Demo ===")

    # Manual correlation ID
    correlation_id = set_correlation_id("manual-correlation-123")
    LOGGER.info("This message has a manual correlation ID")

    # Nested correlation contexts
    with correlation_context() as outer_id:
        LOGGER.info(f"Outer context with ID: {outer_id}")

        with correlation_context("inner-specific-id") as inner_id:
            LOGGER.info(f"Inner context with ID: {inner_id}")
            JSON_LOGGER.info("JSON log with inner correlation ID")

        LOGGER.info("Back to outer context")

    LOGGER.info("Back to original correlation ID")


def demonstrate_operation_tracking():
    """Demonstrate operation history tracking."""
    print("\n=== Operation Tracking Demo ===")

    # Track a successful operation
    with track_operation("data_processing", input_size=1000) as op:
        LOGGER.info("Processing data...")
        time.sleep(0.1)  # Simulate work
        op.metadata["records_processed"] = 1000
        op.metadata["output_size"] = 500

    # Track a failed operation
    try:
        with track_operation("failing_operation") as op:
            LOGGER.info("Starting operation that will fail...")
            time.sleep(0.05)
            raise ValueError("Simulated failure")
    except ValueError:
        LOGGER.error("Operation failed as expected")

    # Show operation history
    store = get_operation_store()
    recent_ops = store.get_recent_operations(limit=5)

    print("\nRecent Operations:")
    for op in recent_ops:
        print(f"  - {op['name']}: {op['status']} ({op.get('duration', 0):.3f}s)")


def demonstrate_debug_mode():
    """Demonstrate debug mode features."""
    print("\n=== Debug Mode Demo ===")

    # Enable debug mode with specific components
    enable_debug_mode(
        components=["calculation", "network"],
        json_logging=False,
        performance_tracking=True,
        operation_tracking=True,
    )

    # Component-specific verbose logging
    debug_log("calculation", "This is visible - calculation is enabled")
    debug_log("network", "This is visible - network is enabled")
    debug_log("database", "This is NOT visible - database not enabled")

    # Performance tracking (automatic with decorator)
    result = complex_calculation(5000)
    print(f"Calculation result: {result}")

    # Get debug info
    debug_info = get_debug_manager().get_debug_info()
    print("\nDebug Info:")
    for key, value in debug_info.items():
        if key != "operation_metrics":
            print(f"  {key}: {value}")

    # Create debug report
    report_path = get_debug_manager().create_debug_report()
    print(f"\nDebug report created: {report_path}")

    disable_debug_mode()


def demonstrate_performance_logging():
    """Demonstrate performance metric logging."""
    print("\n=== Performance Logging Demo ===")

    logger = get_enhanced_logger(__name__)

    # Use performance context manager
    with logger.performance.measure("database_query", table="users", rows=1000):
        time.sleep(0.1)  # Simulate database query

    with logger.performance.measure("api_call", endpoint="/users", method="GET"):
        time.sleep(0.05)  # Simulate API call

    # Multiple measurements of same operation
    for i in range(3):
        with logger.performance.measure("batch_process", batch_id=i):
            time.sleep(0.02 * (i + 1))  # Variable processing time

    # Get and display statistics
    print("\nPerformance Statistics:")
    for operation in ["database_query", "api_call", "batch_process"]:
        stats = logger.performance.get_stats(operation)
        if stats:
            print(f"  {operation}:")
            print(f"    Count: {stats['count']}")
            print(f"    Average: {stats['avg']*1000:.2f}ms")
            print(f"    Min: {stats['min']*1000:.2f}ms")
            print(f"    Max: {stats['max']*1000:.2f}ms")

    # Log summary
    logger.performance.log_summary()


async def demonstrate_async_tracking():
    """Demonstrate async operation tracking."""
    print("\n=== Async Operation Tracking Demo ===")

    # Set correlation ID for all async operations
    with correlation_context("async-batch-001"):
        # Run multiple async operations
        tasks = [example_async_operation(f"task_{i}", delay=0.1 * (i + 1)) for i in range(3)]

        results = await asyncio.gather(*tasks)

        for result in results:
            print(f"  Result: {result}")


def main():
    """Run all demonstrations."""
    print("Enhanced Logging and Debugging Demo")
    print("=" * 50)

    # Optional: Enable JSON logging for entire application
    # setup_json_logging()

    # Run demonstrations
    demonstrate_correlation_ids()
    demonstrate_operation_tracking()
    demonstrate_debug_mode()
    demonstrate_performance_logging()

    # Run async demonstration
    asyncio.run(demonstrate_async_tracking())

    # Show final metrics
    print("\n=== Final Operation Metrics ===")
    store = get_operation_store()
    metrics = store.get_operation_metrics()

    for metric in metrics[:5]:  # Top 5 operations
        print(f"  {metric['operation_name']}:")
        print(f"    Total: {metric['total_count']}")
        print(f"    Success rate: {metric['success_count']/metric['total_count']*100:.1f}%")
        print(f"    Avg duration: {metric.get('avg_duration', 0)*1000:.1f}ms")


if __name__ == "__main__":
    main()
