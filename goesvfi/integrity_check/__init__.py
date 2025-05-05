"""IntegrityCheck package for GOES-VFI.

This package contains modules for the Integrity Check tab, which provides
functionality to verify timestamp completeness in satellite imagery data
and fetch missing images from remote sources using a hybrid CDN/S3 strategy.
"""

# Basic implementation components
from .gui_tab import IntegrityCheckTab
from .view_model import IntegrityCheckViewModel, ScanStatus, MissingTimestamp
from .reconciler import Reconciler
from .time_index import SatellitePattern, TimeIndex

# Enhanced implementation components
from .enhanced_gui_tab import EnhancedIntegrityCheckTab
from .enhanced_view_model import EnhancedIntegrityCheckViewModel, FetchSource
from .reconcile_manager import ReconcileManager
from .remote.cdn_store import CDNStore
from .remote.s3_store import S3Store
from .render.netcdf import render_png