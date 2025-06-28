"""IntegrityCheck package for GOES-VFI.

This package contains modules for the Integrity Check tab, which provides
functionality to verify timestamp completeness in satellite imagery data
and fetch missing images from remote sources using a hybrid CDN/S3 strategy.
"""

# Make public API explicitly available
__all__ = [
    "CDNStore",
    "CombinedIntegrityAndImageryTab",
    # GOES Imagery visualization components
    "EnhancedGOESImageryTab",
    # Enhanced implementation components
    "EnhancedIntegrityCheckTab",
    "EnhancedIntegrityCheckViewModel",
    "ExtendedChannelType",
    "FetchSource",
    # Basic implementation components
    "IntegrityCheckTab",
    "IntegrityCheckViewModel",
    "MissingTimestamp",
    "ReconcileManager",
    "Reconciler",
    "S3Store",
    "SampleProcessor",
    "SatellitePattern",
    "ScanStatus",
    "TimeIndex",
    "VisualizationManager",
    "render_png",
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
