#!/usr/bin/env python3
"""Example showing how to integrate enhanced logging into S3Store operations."""

import asyncio
import sys
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from goesvfi.integrity_check.remote.s3_store import S3Store
from goesvfi.utils.debug_mode import enable_debug_mode, track_performance
from goesvfi.utils.enhanced_log import correlation_context, get_enhanced_logger
from goesvfi.utils.logging_integration import LoggerAdapter
from goesvfi.utils.operation_history import get_operation_store, track_operation


# Enhanced S3Store wrapper demonstrating integration
class EnhancedS3Store(S3Store):
    """S3Store with enhanced logging integration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Replace standard logger with enhanced adapter
        self.LOGGER = LoggerAdapter(self.__class__.__module__)

    @track_performance("s3_download")
    async def download_file(self, key: str, local_path: Path, progress_callback=None):
        """Download with operation tracking and performance metrics."""
        # Track the entire download operation
        with track_operation(
            "s3_download_file",
            key=key,
            bucket=self.bucket_name,
            size_bytes=None,  # Will be updated
        ) as op:
            try:
                # Add verbose debug logging
                self.LOGGER.debug_verbose(
                    "s3_store",
                    f"Starting download: {key}",
                    bucket=self.bucket_name,
                    local_path=str(local_path),
                )

                # Call parent method
                result = await super().download_file(key, local_path, progress_callback)

                # Update operation metadata
                if local_path.exists():
                    size = local_path.stat().st_size
                    op.metadata["size_bytes"] = size
                    op.metadata["size_mb"] = size / (1024 * 1024)

                self.LOGGER.debug_verbose(
                    "s3_store",
                    f"Download complete: {key}",
                    size_bytes=op.metadata.get("size_bytes", 0),
                )

                return result

            except Exception as e:
                self.LOGGER.debug_verbose(
                    "s3_store",
                    f"Download failed: {key}",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    async def list_objects(self, prefix: str = "", limit: int = 1000):
        """List objects with correlation tracking."""
        # Each list operation gets its own correlation ID
        with correlation_context() as correlation_id:
            self.LOGGER.info(
                f"Listing objects in {self.bucket_name}",
                extra={
                    "prefix": prefix,
                    "limit": limit,
                    "correlation_id": correlation_id,
                },
            )

            with track_operation("s3_list_objects", prefix=prefix, limit=limit) as op:
                result = await super().list_objects(prefix, limit)
                op.metadata["object_count"] = len(result)
                return result


async def demonstrate_enhanced_s3():
    """Demonstrate enhanced S3 operations."""
    print("Enhanced S3Store Demo")
    print("=" * 50)

    # Enable debug mode with S3 component
    enable_debug_mode(
        components=["s3_store", "download"],
        json_logging=False,
        performance_tracking=True,
        operation_tracking=True,
    )

    # Create enhanced S3 store
    store = EnhancedS3Store(bucket_name="noaa-goes16", endpoint_url=None, unsigned=True)

    async with store:
        # List objects with tracking
        print("\nListing objects...")
        objects = await store.list_objects(prefix="ABI-L1b-RadF/2024/001/00/", limit=5)

        print(f"Found {len(objects)} objects")
        for obj in objects[:3]:
            print(f"  - {obj['Key']} ({obj['Size']} bytes)")

        # Simulate multiple correlated operations
        with correlation_context("batch-download-001") as batch_id:
            print(f"\nStarting batch download (ID: {batch_id})")

            # Mock download (would need actual S3 keys)
            print("Note: Actual downloads skipped in demo")

            # Simulate operations for metrics
            for i in range(3):
                with track_operation(f"simulated_download_{i}", batch_id=batch_id, file_index=i) as op:
                    import time

                    time.sleep(0.1 * (i + 1))
                    op.metadata["simulated"] = True
                    op.metadata["size_mb"] = 10 * (i + 1)

    # Show operation metrics
    print("\n=== Operation Metrics ===")
    store = get_operation_store()

    # Recent operations
    recent = store.get_recent_operations(limit=10)
    print(f"\nRecent Operations ({len(recent)} total):")
    for op in recent:
        duration = op.get("duration", 0)
        print(f"  - {op['name']}: {op['status']} ({duration*1000:.1f}ms)")

    # Aggregated metrics
    metrics = store.get_operation_metrics()
    print("\nOperation Statistics:")
    for metric in metrics:
        if metric["total_count"] > 0:
            print(f"  {metric['operation_name']}:")
            print(f"    Total: {metric['total_count']}")
            print(f"    Avg duration: {metric['avg_duration']*1000:.1f}ms")

    # Search for specific correlation ID
    if recent:
        correlation_id = recent[0].get("correlation_id")
        if correlation_id:
            print(f"\nOperations with correlation ID {correlation_id[:8]}...:")
            correlated = store.get_operations_by_correlation_id(correlation_id)
            for op in correlated:
                print(f"  - {op['name']} ({op['status']})")


def main():
    """Run the demonstration."""
    try:
        asyncio.run(demonstrate_enhanced_s3())
    except KeyboardInterrupt:
        print("\nDemo interrupted")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
