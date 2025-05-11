"""IntegrityCheck package for GOES-VFI.

This package contains modules for the Integrity Check tab, which provides
functionality to verify timestamp completeness in satellite imagery data
and fetch missing images from remote sources using a hybrid CDN/S3 strategy.
"""

# Make public API explicitly available
__all__ = [
    # Basic implementation components
    "IntegrityCheckTab",
    "IntegrityCheckViewModel",
    "ScanStatus",
    "MissingTimestamp",
    "Reconciler",
    "SatellitePattern",
    "TimeIndex",
    # Enhanced implementation components
    "EnhancedIntegrityCheckTab",
    "EnhancedIntegrityCheckViewModel",
    "FetchSource",
    "ReconcileManager",
    "CDNStore",
    "S3Store",
    "render_png",
    # GOES Imagery visualization components
    "EnhancedGOESImageryTab",
    "VisualizationManager",
    "ExtendedChannelType",
    "SampleProcessor",
    "CombinedIntegrityAndImageryTab",
]

from .combined_tab import CombinedIntegrityAndImageryTab

# Enhanced implementation components
from .enhanced_gui_tab import EnhancedIntegrityCheckTab

# GOES Imagery visualization components
from .enhanced_imagery_tab import EnhancedGOESImageryTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel, FetchSource

# Basic implementation components
from .gui_tab import IntegrityCheckTab
from .reconcile_manager import ReconcileManager
from .reconciler import Reconciler
from .remote.cdn_store import CDNStore
from .remote.s3_store import S3Store
from .render.netcdf import render_png
from .sample_processor import SampleProcessor
from .time_index import SatellitePattern, TimeIndex
from .view_model import IntegrityCheckViewModel, MissingTimestamp, ScanStatus
from .visualization_manager import ExtendedChannelType, VisualizationManager
