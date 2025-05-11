"""Satellite imagery rendering module.

This package provides utilities for converting NetCDF and other formats
to PNG images for display and processing.
"""

from .netcdf import extract_metadata, render_png

__all__ = ["render_png", "extract_metadata"]
