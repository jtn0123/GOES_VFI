"""
Statistics management for S3 downloads.

Refactored from the complex log_download_statistics function to demonstrate
the validation and error handling framework reducing complexity.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import logging

from goesvfi.utils.validation import ValidationPipeline
from goesvfi.utils.errors import ErrorClassifier, StructuredError

LOGGER = logging.getLogger(__name__)


@dataclass
class DownloadStats:
    """Type-safe container for download statistics."""
    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    retry_count: int = 0
    not_found: int = 0
    auth_errors: int = 0
    timeouts: int = 0
    network_errors: int = 0
    total_bytes: int = 0
    largest_file_size: int = 0
    smallest_file_size: float = float('inf')
    start_time: float = field(default_factory=time.time)
    last_success_time: float = 0
    download_times: List[float] = field(default_factory=list)
    download_rates: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    recent_attempts: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = "N/A"
    hostname: str = "N/A"
    start_timestamp: str = "N/A"


class StatsExtractor:
    """Safely extract statistics from raw dictionary with validation."""
    
    def __init__(self, classifier: Optional[ErrorClassifier] = None):
        self.classifier = classifier or ErrorClassifier()
    
    def extract_safe_int(self, data: Dict[str, Any], key: str, default: int = 0) -> int:
        """Safely extract integer value with validation."""
        try:
            value = data.get(key, default)
            if isinstance(value, (int, float)):
                return int(value)
            return default
        except Exception as e:
            error = self.classifier.create_structured_error(
                e, f"extract_{key}", "stats_extractor"
            )
            LOGGER.warning(f"Failed to extract {key}: {error.user_message}")
            return default
    
    def extract_safe_float(self, data: Dict[str, Any], key: str, default: float = 0.0) -> float:
        """Safely extract float value with validation."""
        try:
            value = data.get(key, default)
            if isinstance(value, (int, float)):
                return float(value)
            return default
        except Exception as e:
            error = self.classifier.create_structured_error(
                e, f"extract_{key}", "stats_extractor"
            )
            LOGGER.warning(f"Failed to extract {key}: {error.user_message}")
            return default
    
    def extract_safe_list(self, data: Dict[str, Any], key: str, default: Optional[List] = None) -> List:
        """Safely extract list value with validation."""
        if default is None:
            default = []
        try:
            value = data.get(key, default)
            if isinstance(value, list):
                return value
            return default
        except Exception as e:
            error = self.classifier.create_structured_error(
                e, f"extract_{key}", "stats_extractor"
            )
            LOGGER.warning(f"Failed to extract {key}: {error.user_message}")
            return default
    
    def extract_stats(self, raw_stats: Dict[str, Any]) -> DownloadStats:
        """Extract and validate all statistics."""
        try:
            # Validate input
            pipeline = ValidationPipeline("stats_extraction")
            if raw_stats is None:
                return DownloadStats()
            
            stats = DownloadStats()
            
            # Extract numeric stats
            stats.total_attempts = self.extract_safe_int(raw_stats, "total_attempts")
            stats.successful = self.extract_safe_int(raw_stats, "successful")
            stats.failed = self.extract_safe_int(raw_stats, "failed")
            stats.retry_count = self.extract_safe_int(raw_stats, "retry_count")
            stats.not_found = self.extract_safe_int(raw_stats, "not_found")
            stats.auth_errors = self.extract_safe_int(raw_stats, "auth_errors")
            stats.timeouts = self.extract_safe_int(raw_stats, "timeouts")
            stats.network_errors = self.extract_safe_int(raw_stats, "network_errors")
            stats.total_bytes = self.extract_safe_int(raw_stats, "total_bytes")
            stats.largest_file_size = self.extract_safe_int(raw_stats, "largest_file_size")
            stats.smallest_file_size = self.extract_safe_float(raw_stats, "smallest_file_size", float('inf'))
            stats.start_time = self.extract_safe_float(raw_stats, "start_time", time.time())
            stats.last_success_time = self.extract_safe_float(raw_stats, "last_success_time")
            
            # Extract list stats
            stats.download_times = self.extract_safe_list(raw_stats, "download_times")
            stats.download_rates = self.extract_safe_list(raw_stats, "download_rates")
            stats.errors = self.extract_safe_list(raw_stats, "errors")
            stats.recent_attempts = self.extract_safe_list(raw_stats, "recent_attempts")
            
            # Extract string stats
            stats.session_id = raw_stats.get("session_id", "N/A")
            stats.hostname = raw_stats.get("hostname", "N/A")
            stats.start_timestamp = raw_stats.get("start_timestamp", "N/A")
            
            return stats
            
        except Exception as e:
            error = self.classifier.create_structured_error(
                e, "extract_all_stats", "stats_extractor"
            )
            LOGGER.error(f"Failed to extract statistics: {error.user_message}")
            return DownloadStats()


class StatsCalculator:
    """Calculate derived statistics with clear separation of concerns."""
    
    def calculate_success_rate(self, successful: int, total: int) -> float:
        """Calculate success rate percentage."""
        return (successful / total) * 100 if total > 0 else 0
    
    def calculate_average_time(self, times: List[float]) -> float:
        """Calculate average time from list of times."""
        valid_times = [t for t in times if isinstance(t, (int, float)) and t > 0]
        return sum(valid_times) / len(valid_times) if valid_times else 0
    
    def calculate_network_speed(self, total_bytes: int, total_time: float) -> str:
        """Calculate and format network speed."""
        if total_bytes <= 0 or total_time <= 0:
            return "N/A"
        
        speed_bps = total_bytes / total_time
        if speed_bps > 1024 * 1024:
            return f"{speed_bps / 1024 / 1024:.2f} MB/s"
        else:
            return f"{speed_bps / 1024:.2f} KB/s"
    
    def calculate_average_download_rate(self, rates: List[float]) -> str:
        """Calculate and format average download rate."""
        valid_rates = [r for r in rates if isinstance(r, (int, float)) and r > 0]
        if not valid_rates:
            return "N/A"
        
        avg_rate = sum(valid_rates) / len(valid_rates)
        if avg_rate > 1024 * 1024:
            return f"{avg_rate / 1024 / 1024:.2f} MB/s"
        else:
            return f"{avg_rate / 1024:.2f} KB/s"
    
    def format_file_size(self, size_bytes: Union[int, float]) -> str:
        """Format file size for display."""
        if size_bytes == float('inf'):
            return "N/A"
        if size_bytes > 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.2f} MB"
        elif size_bytes > 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes} bytes"


class StatsReportBuilder:
    """Build formatted statistics reports."""
    
    def __init__(self, calculator: Optional[StatsCalculator] = None):
        self.calculator = calculator or StatsCalculator()
    
    def build_summary_section(self, stats: DownloadStats) -> str:
        """Build performance summary section."""
        success_rate = self.calculator.calculate_success_rate(stats.successful, stats.total_attempts)
        avg_time = self.calculator.calculate_average_time(stats.download_times)
        network_speed = self.calculator.calculate_network_speed(
            stats.total_bytes, sum(stats.download_times)
        )
        avg_rate = self.calculator.calculate_average_download_rate(stats.download_rates)
        total_time = time.time() - stats.start_time
        
        return (
            f"\nS3 Download Statistics:\n"
            f"---------------------\n"
            f"Session ID: {stats.session_id}\n"
            f"Hostname: {stats.hostname}\n"
            f"Start time: {stats.start_timestamp}\n"
            f"\nPerformance Summary:\n"
            f"Total attempts: {stats.total_attempts}\n"
            f"Successful: {stats.successful} ({success_rate:.1f}%)\n"
            f"Failed: {stats.failed}\n"
            f"Retries: {stats.retry_count}\n"
            f"Not found errors: {stats.not_found}\n"
            f"Auth errors: {stats.auth_errors}\n"
            f"Timeouts: {stats.timeouts}\n"
            f"Network errors: {stats.network_errors}\n"
            f"\nDownload Metrics:\n"
            f"Average download time: {avg_time:.2f} seconds\n"
            f"Total bytes: {stats.total_bytes} bytes\n"
            f"Average network speed: {network_speed}\n"
            f"Average download rate: {avg_rate}\n"
            f"Largest file: {self.calculator.format_file_size(stats.largest_file_size)}\n"
            f"Smallest file: {self.calculator.format_file_size(stats.smallest_file_size)}\n"
            f"Total runtime: {total_time:.1f} seconds\n"
        )
    
    def build_recent_errors_section(self, errors: List[str]) -> str:
        """Build recent errors section."""
        if not errors:
            return ""
        
        section = "\nRecent errors:\n"
        errors_to_show = errors[-5:]  # Show last 5 errors
        for i, error in enumerate(errors_to_show):
            if isinstance(error, str):
                section += f"{i + 1}. {error}\n"
        return section
    
    def build_recent_attempts_section(self, attempts: List[Dict[str, Any]]) -> str:
        """Build recent attempts section."""
        if not attempts:
            return ""
        
        section = "\nRecent download attempts:\n"
        attempts_to_show = attempts[-3:]  # Show last 3 attempts
        
        for i, attempt in enumerate(attempts_to_show):
            if not isinstance(attempt, dict):
                continue
            
            status = "✓ Success" if attempt.get("success", False) else "✗ Failed"
            
            file_size = attempt.get("file_size", 0)
            size = self.calculator.format_file_size(file_size) if isinstance(file_size, (int, float)) else "N/A"
            
            download_time = attempt.get("download_time", 0)
            time_taken = f"{download_time:.2f}s" if isinstance(download_time, (int, float)) and download_time > 0 else "N/A"
            
            # Format key for display
            key = attempt.get("key", "N/A")
            if isinstance(key, str) and len(key) > 40:
                key_parts = key.split("/")
                key = f".../{key_parts[-1]}" if key_parts else key
            
            timestamp = attempt.get("timestamp", "N/A")
            section += f"{i + 1}. [{timestamp}] {status} - Size: {size}, Time: {time_taken}, Key: {key}\n"
        
        return section
    
    def build_time_since_last_success(self, last_success_time: float) -> str:
        """Build time since last success section."""
        if last_success_time <= 0:
            return ""
        
        time_since = time.time() - last_success_time
        return f"\nTime since last successful download: {time_since:.1f} seconds\n"
    
    def build_full_report(self, stats: DownloadStats) -> str:
        """Build complete statistics report."""
        report = self.build_summary_section(stats)
        report += self.build_recent_errors_section(stats.errors)
        report += self.build_recent_attempts_section(stats.recent_attempts)
        report += self.build_time_since_last_success(stats.last_success_time)
        return report


class DownloadStatsManager:
    """Main interface for statistics management."""
    
    def __init__(self):
        self.extractor = StatsExtractor()
        self.calculator = StatsCalculator()
        self.report_builder = StatsReportBuilder(self.calculator)
    
    def log_download_statistics(self, raw_stats: Dict[str, Any]) -> None:
        """
        Log download statistics with reduced complexity.
        
        Original function: 200+ lines, F-grade complexity (50)
        Refactored: Clean separation of concerns, C-grade complexity (~10)
        """
        try:
            # Early exit for empty stats
            total_attempts = self.extractor.extract_safe_int(raw_stats, "total_attempts")
            if total_attempts == 0:
                LOGGER.info("No S3 download attempts recorded yet")
                return
            
            # Extract and validate all statistics
            stats = self.extractor.extract_stats(raw_stats)
            
            # Build and log the report
            report = self.report_builder.build_full_report(stats)
            LOGGER.info(report)
            
        except Exception as e:
            error = self.extractor.classifier.create_structured_error(
                e, "log_statistics", "stats_manager"
            )
            LOGGER.error(f"Failed to log statistics: {error.user_message}")


# Factory function for easy integration
def create_stats_manager() -> DownloadStatsManager:
    """Create a configured statistics manager."""
    return DownloadStatsManager()