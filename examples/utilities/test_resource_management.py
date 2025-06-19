#!/usr/bin/env python3
"""Test script for resource management functionality.

This script demonstrates the resource management capabilities
without requiring the full GUI to be running.
"""

import os
import sys
import time
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

try:
    from goesvfi.utils import log
    from goesvfi.utils.resource_manager import (
        ResourceLimitedContext,
        ResourceLimits,
        ResourceMonitor,
        get_system_resource_info,
    )

    LOGGER = log.get_logger(__name__)

    def test_basic_resource_info():
        """Test getting system resource information."""
        print("📊 System Resource Information:")
        print("=" * 50)

        info = get_system_resource_info()

        # Memory info
        memory = info.get("memory", {})
        print(
            f"Memory: {memory.get('total_mb', 0):.0f} MB total, "
            f"{memory.get('available_mb', 0):.0f} MB available "
            f"({memory.get('percent_used', 0):.1f}% used)"
        )

        # CPU info
        cpu = info.get("cpu", {})
        print(f"CPU: {cpu.get('count', 'Unknown')} cores")
        if cpu.get("frequency_mhz"):
            print(f"  Frequency: {cpu.get('frequency_mhz', 0):.0f} MHz")

        # Disk info
        disk = info.get("disk", {})
        print(
            f"Disk: {disk.get('free_gb', 0):.1f} GB free of "
            f"{disk.get('total_gb', 0):.1f} GB total "
            f"({disk.get('percent_used', 0):.1f}% used)"
        )

        # Platform info
        platform_info = info.get("platform", {})
        print(
            f"Platform: {platform_info.get('system', 'Unknown')} "
            f"({platform_info.get('architecture', 'Unknown')})"
        )

        print()

    def test_resource_monitoring():
        """Test resource monitoring functionality."""
        print("🔍 Resource Monitoring Test:")
        print("=" * 50)

        # Create some conservative limits for testing
        limits = ResourceLimits(
            max_memory_mb=1024,  # 1 GB memory limit
            max_processing_time_sec=10,  # 10 second time limit
            max_cpu_percent=90.0,  # 90% CPU limit
        )

        print(f"Testing with limits: {limits}")

        # Create a monitor
        monitor = ResourceMonitor(limits, check_interval=0.5)

        # Add callbacks
        def on_usage_update(usage):
            print(
                f"  📈 Current usage: Memory={usage.memory_mb:.1f}MB, "
                f"CPU={usage.cpu_percent:.1f}%, Time={usage.processing_time_sec:.1f}s"
            )

        def on_warning(usage):
            print(
                f"  ⚠️  Resource warning: Memory={usage.memory_mb:.1f}MB, "
                f"CPU={usage.cpu_percent:.1f}%, Time={usage.processing_time_sec:.1f}s"
            )

        def on_limit_exceeded(usage):
            print(
                f"  🚨 Limit exceeded: Memory={usage.memory_mb:.1f}MB, "
                f"CPU={usage.cpu_percent:.1f}%, Time={usage.processing_time_sec:.1f}s"
            )

        monitor.add_callback("usage_update", on_usage_update)
        monitor.add_callback("limit_warning", on_warning)
        monitor.add_callback("limit_exceeded", on_limit_exceeded)

        # Start monitoring
        monitor.start_monitoring()

        try:
            print("  Monitoring for 5 seconds...")
            time.sleep(5)

            # Get current usage
            usage = monitor.get_current_usage()
            print(
                f"  Final usage: Memory={usage.memory_mb:.1f}MB, "
                f"CPU={usage.cpu_percent:.1f}%, Time={usage.processing_time_sec:.1f}s"
            )

        finally:
            monitor.stop_monitoring()

        print()

    def test_resource_limited_context():
        """Test the resource-limited context manager."""
        print("⚡ Resource Limited Context Test:")
        print("=" * 50)

        limits = ResourceLimits(
            max_memory_mb=512,  # 512 MB limit
            max_processing_time_sec=3,  # 3 second limit
        )

        print(f"Testing context with limits: {limits}")

        try:
            with ResourceLimitedContext(limits, monitor=True) as context:
                monitor = context.get_monitor()
                if monitor:
                    print("  ✅ Context manager created monitor successfully")

                    # Simulate some work
                    print("  🔄 Simulating work for 2 seconds...")
                    time.sleep(2)

                    usage = monitor.get_current_usage()
                    print(
                        f"  📊 Work completed. Usage: Memory={usage.memory_mb:.1f}MB, "
                        f"Time={usage.processing_time_sec:.1f}s"
                    )
                else:
                    print("  ⚠️  No monitor created")

        except Exception as e:
            print(f"  ❌ Context error: {e}")

        print()

    def test_resource_limits_creation():
        """Test creating different types of resource limits."""
        print("🎛️  Resource Limits Creation Test:")
        print("=" * 50)

        # Test different limit configurations
        configs = [
            {
                "name": "Basic limits",
                "limits": ResourceLimits(
                    max_memory_mb=1024, max_processing_time_sec=300
                ),
            },
            {
                "name": "CPU intensive",
                "limits": ResourceLimits(max_cpu_percent=50.0, max_open_files=100),
            },
            {
                "name": "Memory conservative",
                "limits": ResourceLimits(max_memory_mb=256, enable_swap_limit=False),
            },
            {"name": "No limits", "limits": ResourceLimits()},
        ]

        for config in configs:
            limits = config["limits"]
            print(f"  {config['name']}: {limits}")

        print()

    def main():
        """Run all resource management tests."""
        print("🧪 GOES_VFI Resource Management Test Suite")
        print("=" * 60)
        print()

        try:
            test_basic_resource_info()
            test_resource_limits_creation()
            test_resource_monitoring()
            test_resource_limited_context()

            print("✅ All resource management tests completed successfully!")

        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("📝 Note: You may need to install psutil: pip install psutil")
            return 1

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return 1

        return 0

    if __name__ == "__main__":
        sys.exit(main())

except ImportError as e:
    print(f"❌ Could not import required modules: {e}")
    print("📝 This likely means psutil is not installed.")
    print("   Try: pip install psutil")
    sys.exit(1)
