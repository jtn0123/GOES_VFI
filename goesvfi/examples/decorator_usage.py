"""Example usage of error handling decorators in the GOES VFI codebase.

This module demonstrates how to use the error decorators to improve
code reliability and reduce duplication.
"""

import contextlib
from pathlib import Path

from goesvfi.core.error_decorators import (
    async_safe,
    robust_operation,
    with_error_handling,
    with_logging,
    with_retry,
)


# Example 1: Simple error handling for file operations
@with_error_handling(operation_name="load_config", component_name="config_loader", reraise=False, default_return={})
def load_config_file(path: Path) -> dict:
    """Load configuration from JSON file."""
    import json

    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Example 2: Retry logic for network operations
@with_retry(max_attempts=3, delay=1.0, backoff_factor=2.0, exceptions=(ConnectionError, TimeoutError))
def download_file(url: str, dest: Path) -> None:
    """Download file with automatic retry."""
    import urllib.request

    urllib.request.urlretrieve(url, dest)


# Example 3: Logging and timing for performance analysis
@with_logging(
    log_args=True,
    log_result=False,  # Don't log large results
    log_time=True,
)
def process_large_dataset(data_path: Path, output_path: Path) -> int:
    """Process dataset and return count of processed items."""
    # Simulate processing
    return 0

    # ... actual processing logic ...


# Example 4: Robust operation for critical functions
@robust_operation(operation_name="s3_download", max_retries=5, retry_delay=2.0)
def download_from_s3(bucket: str, key: str, local_path: Path) -> None:
    """Download file from S3 with retry and error handling."""
    import boto3

    s3 = boto3.client("s3")
    s3.download_file(bucket, key, str(local_path))


# Example 5: Safe async operations
@async_safe(timeout=30.0, default_return=None)
async def fetch_remote_data(url: str) -> dict | None:
    """Fetch data from remote API with timeout protection."""
    import aiohttp

    async with aiohttp.ClientSession() as session, session.get(url) as response:
        return await response.json()


# Example 6: Combining decorators for complex operations
@with_logging(log_time=True)
@with_error_handling(operation_name="batch_process", reraise=True)
@with_retry(max_attempts=3, exceptions=(IOError, OSError))
def batch_process_images(input_dir: Path, output_dir: Path, processor_func: callable) -> list[Path]:
    """Process all images in a directory with full error handling."""
    processed_files = []

    for image_path in input_dir.glob("*.png"):
        output_path = output_dir / image_path.name

        # Process individual image
        processor_func(image_path, output_path)
        processed_files.append(output_path)

    return processed_files


# Example 7: Decorator usage in class methods
class DataProcessor:
    """Example class using decorators on methods."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    @with_error_handling(
        operation_name="load_cache", component_name="DataProcessor", reraise=False, default_return=None
    )
    def load_from_cache(self, key: str) -> dict | None:
        """Load data from cache with error handling."""
        import pickle

        cache_file = self.cache_dir / f"{key}.pkl"
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    @robust_operation(operation_name="save_cache", max_retries=3)
    def save_to_cache(self, key: str, data: dict) -> None:
        """Save data to cache with retry logic."""
        import pickle

        cache_file = self.cache_dir / f"{key}.pkl"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_file, "wb") as f:
            pickle.dump(data, f)


# Example 8: Custom error handling patterns
def create_s3_downloader(max_retries: int = 5, timeout: float = 30.0):
    """Factory function creating decorated S3 downloader."""

    @with_logging(log_args=True, log_time=True)
    @with_error_handling(operation_name="s3_download", component_name="S3Downloader")
    @with_retry(
        max_attempts=max_retries, delay=2.0, backoff_factor=2.0, exceptions=(ConnectionError, TimeoutError, OSError)
    )
    def download(bucket: str, key: str, dest: Path) -> bool:
        """Download with configured retry and timeout."""
        import boto3
        from botocore.config import Config

        config = Config(
            read_timeout=timeout,
            connect_timeout=timeout,
            retries={"max_attempts": 0},  # We handle retries
        )

        s3 = boto3.client("s3", config=config)
        s3.download_file(bucket, key, str(dest))
        return True

    return download


# Example usage patterns for integration
if __name__ == "__main__":
    # Example 1: Load config with fallback
    config = load_config_file(Path("config.json"))

    # Example 2: Download with retry
    with contextlib.suppress(Exception):
        download_file("https://example.com/data.zip", Path("data.zip"))

    # Example 3: Process with timing
    count = process_large_dataset(Path("input_data"), Path("output_data"))

    # Example 4: Create custom downloader
    s3_download = create_s3_downloader(max_retries=10, timeout=60.0)
    success = s3_download("my-bucket", "data/file.nc", Path("local.nc"))

    # Example 5: Async operation
    async def main() -> None:
        data = await fetch_remote_data("https://api.example.com/data")
        if data:
            pass

    # asyncio.run(main())
