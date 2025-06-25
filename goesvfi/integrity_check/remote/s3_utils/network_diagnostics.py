"""Network diagnostics for S3 connectivity troubleshooting.

This module provides utilities to diagnose network connectivity issues
when accessing S3 buckets.
"""

import os
import platform
import socket
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class NetworkDiagnostics:
    """Utilities for network connectivity diagnostics."""

    NOAA_S3_HOSTS = [
        "noaa-goes16.s3.amazonaws.com",
        "noaa-goes18.s3.amazonaws.com",
        "s3.amazonaws.com",
    ]

    @staticmethod
    def collect_system_info() -> Dict[str, Any]:
        """Collect system and network information for debugging.

        Returns:
            Dictionary containing system and network information
        """
        info: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "hostname": socket.gethostname(),
        }

        # Try to get DNS server info
        dns_servers = NetworkDiagnostics._get_dns_servers()
        if dns_servers:
            info["dns_servers"] = dns_servers

        # Test S3 hostname resolution
        s3_resolution = NetworkDiagnostics._test_s3_resolution()
        info["s3_host_resolution"] = s3_resolution

        return info

    @staticmethod
    def _get_dns_servers() -> List[str]:
        """Extract DNS server information from system configuration.

        Returns:
            List of DNS server addresses
        """
        dns_servers: List[str] = []

        try:
            # Try to get DNS server info on Unix systems
            if os.path.exists("/etc/resolv.conf"):
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) > 1:
                                dns_servers.append(parts[1])
        except Exception as e:
            LOGGER.debug("Could not read DNS servers: %s", e)

        return dns_servers

    @staticmethod
    def _test_s3_resolution() -> List[Dict[str, Any]]:
        """Test DNS resolution for S3 hostnames.

        Returns:
            List of resolution results for each S3 host
        """
        results = []

        for host in NetworkDiagnostics.NOAA_S3_HOSTS:
            try:
                ip_addr = socket.gethostbyname(host)
                results.append(
                    {
                        "host": host,
                        "ip": ip_addr,
                        "success": True,
                    }
                )
                LOGGER.debug("✓ Successfully resolved %s to %s", host, ip_addr)
            except Exception as e:
                results.append(
                    {
                        "host": host,
                        "error": str(e),
                        "success": False,
                    }
                )
                LOGGER.debug("✗ Failed to resolve %s: %s", host, e)

        return results

    @staticmethod
    def log_connectivity_test() -> None:
        """Log a connectivity test to AWS S3 NOAA buckets."""
        LOGGER.info("Testing connectivity to AWS S3 NOAA buckets...")

        for host in NetworkDiagnostics.NOAA_S3_HOSTS:
            try:
                ip_addr = socket.gethostbyname(host)
                LOGGER.info("✓ Successfully resolved %s to %s", host, ip_addr)
            except Exception as e:
                LOGGER.error("✗ Failed to resolve %s: %s", host, e)

    @staticmethod
    def log_system_info() -> Dict[str, Any]:
        """Collect and log system/network information.

        Returns:
            Dictionary containing the collected information
        """
        info = NetworkDiagnostics.collect_system_info()

        log_lines = [
            "System and Network Information:",
            f"  Timestamp: {info.get('timestamp', 'N/A')}",
            f"  Platform: {info.get('platform', 'N/A')}",
            f"  Python: {info.get('python_version', 'N/A')}",
            f"  Hostname: {info.get('hostname', 'N/A')}",
        ]

        # Add DNS information
        dns_servers = info.get("dns_servers", [])
        if dns_servers:
            log_lines.append(f"  DNS Servers: {', '.join(dns_servers)}")

        # Add S3 host resolution info
        s3_resolutions = info.get("s3_host_resolution", [])
        for resolution in s3_resolutions:
            if resolution.get("success"):
                log_lines.append(
                    f"  S3 Host Resolution: {resolution['host']} -> {resolution['ip']}"
                )
            else:
                log_lines.append(
                    f"  S3 Host Resolution Failed: {resolution['host']} - {resolution.get('error', 'Unknown error')}"
                )

        LOGGER.info("\n".join(log_lines))

        return info

    @staticmethod
    def create_network_error_details(
        error: Exception,
        operation: str,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create detailed network error information for troubleshooting.

        Args:
            error: The network error that occurred
            operation: Description of the operation that failed
            additional_info: Optional additional context

        Returns:
            Formatted error details string
        """
        details = [
            f"Network operation failed: {operation}",
            f"Error type: {type(error).__name__}",
            f"Error message: {str(error)}",
        ]

        # Add network diagnostics
        try:
            # Quick DNS check
            socket.gethostbyname("s3.amazonaws.com")
            details.append("DNS resolution: Working")
        except Exception:
            details.append("DNS resolution: Failed - check your internet connection")

        # Add additional info if provided
        if additional_info:
            for key, value in additional_info.items():
                details.append(f"{key}: {value}")

        details.append("\nTroubleshooting steps:")
        details.append("1. Check your internet connection")
        details.append("2. Verify DNS settings")
        details.append("3. Check for proxy/firewall restrictions")
        details.append("4. Try again in a few moments")

        return "\n".join(details)
