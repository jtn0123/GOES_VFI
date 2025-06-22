#!/usr/bin/env python3
"""Example demonstrating memory-aware image processing."""

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.utils.log import get_logger
from goesvfi.utils.memory_manager import (
    MemoryOptimizer,
    estimate_memory_requirement,
    get_memory_monitor,
    log_memory_usage,
)

LOGGER = get_logger(__name__)


def demonstrate_memory_monitoring():
    """Demonstrate basic memory monitoring."""
    print("\n=== Memory Monitoring Demo ===")

    monitor = get_memory_monitor()
    stats = monitor.get_memory_stats()

    print(f"Total Memory: {stats.total_mb}MB")
    print(f"Available Memory: {stats.available_mb}MB")
    print(f"Used Memory: {stats.used_mb}MB ({stats.percent_used:.1f}%)")
    print(f"Process Memory: {stats.process_mb}MB")

    if stats.is_low_memory:
        print("⚠️  WARNING: System memory is running low!")
    if stats.is_critical_memory:
        print("🚨 CRITICAL: System memory is critically low!")


def demonstrate_memory_optimization():
    """Demonstrate memory optimization techniques."""
    print("\n=== Memory Optimization Demo ===")

    optimizer = MemoryOptimizer()

    # Create a large array
    print("Creating large float64 array (800MB)...")
    large_array = np.random.rand(10000, 10000)  # ~800MB
    log_memory_usage("After creating large array")

    # Optimize dtype
    print("Optimizing array dtype...")
    optimized_array = optimizer.optimize_array_dtype(large_array)
    print(f"Original dtype: {large_array.dtype}, size: {large_array.nbytes // (1024*1024)}MB")
    print(f"Optimized dtype: {optimized_array.dtype}, size: {optimized_array.nbytes // (1024*1024)}MB")
    log_memory_usage("After dtype optimization")

    # Free the original array
    del large_array
    optimizer.free_memory(force=True)
    log_memory_usage("After freeing original array")

    # Demonstrate chunking
    print("\nDemonstrating array chunking...")
    chunks = optimizer.chunk_large_array(optimized_array, max_chunk_mb=50)
    print(f"Array split into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: shape={chunk.shape}, size={chunk.nbytes // (1024*1024)}MB")


def demonstrate_memory_aware_image_loading():
    """Demonstrate memory-aware image loading."""
    print("\n=== Memory-Aware Image Loading Demo ===")

    # Create a test image
    test_image_path = Path("test_image.png")
    if not test_image_path.exists():
        print("Creating test image...")
        test_img = Image.new("RGB", (2000, 2000), color="red")
        test_img.save(test_image_path)

    # Load with memory optimization
    print("Loading image with memory optimization...")
    loader = ImageLoader(optimize_memory=True, max_image_size_mb=100)

    try:
        log_memory_usage("Before loading image")
        image_data = loader.load(str(test_image_path))
        log_memory_usage("After loading image")

        print(f"Image loaded successfully:")
        print(f"  Size: {image_data.width}x{image_data.height}")
        print(f"  Memory optimized: {image_data.metadata.get('memory_optimized', False)}")
        print(f"  Array dtype: {image_data.metadata.get('dtype', 'unknown')}")
        print(f"  Size in MB: {image_data.metadata.get('size_mb', 0):.2f}MB")

    except Exception as e:
        print(f"Error loading image: {e}")
    finally:
        # Clean up
        if test_image_path.exists():
            test_image_path.unlink()


def demonstrate_memory_callbacks():
    """Demonstrate memory monitoring callbacks."""
    print("\n=== Memory Callbacks Demo ===")

    monitor = get_memory_monitor()

    # Define a callback
    def memory_warning_callback(stats):
        if stats.is_low_memory:
            print(f"⚠️  Memory callback: Low memory detected! Available: {stats.available_mb}MB")

    # Add callback
    monitor.add_callback(memory_warning_callback)

    # Start monitoring (if not already started)
    monitor.start_monitoring(interval=2.0)

    print("Memory monitoring started with callbacks...")
    print("Allocating memory to trigger warnings...")

    # Allocate some memory to potentially trigger callback
    arrays = []
    try:
        for i in range(5):
            # Allocate 100MB chunks
            arr = np.zeros((25 * 1024 * 1024,), dtype=np.float32)  # ~100MB
            arrays.append(arr)
            print(f"Allocated chunk {i+1} (100MB)")
            time.sleep(1)

            stats = monitor.get_memory_stats()
            if stats.is_low_memory:
                print("Low memory condition reached!")
                break
    except MemoryError:
        print("MemoryError: Cannot allocate more memory")

    # Clean up
    arrays.clear()
    monitor.stop_monitoring()
    print("Memory monitoring stopped")


def main():
    """Run all demonstrations."""
    print("GOES_VFI Memory Management Demonstration")
    print("=" * 50)

    # Run demos
    demonstrate_memory_monitoring()
    demonstrate_memory_optimization()
    demonstrate_memory_aware_image_loading()
    demonstrate_memory_callbacks()

    print("\n" + "=" * 50)
    print("Demonstration complete!")


if __name__ == "__main__":
    main()
