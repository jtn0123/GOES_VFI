"""Satellite imagery rendering module.

This package provides utilities for converting NetCDF and other formats 
to PNG images for display and processing.
"""

from .netcdf import render_png, extract_metadata

__all__ = ["render_png", "extract_metadata"]