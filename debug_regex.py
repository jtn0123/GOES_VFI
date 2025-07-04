#!/usr/bin/env python3
"""Debug regex patterns for test count extraction."""

import re

# Sample output from pytest
sample_output = """===================== test session starts =====================
platform darwin -- Python 3.13.5, pytest-8.3.5, pluggy-1.5.0 -- /Users/justin/Documents/Github/GOES_VFI/.venv/bin/python
cachedir: .pytest_cache
PyQt6 6.9.0 -- Qt runtime 6.9.0 -- Qt compiled 6.9.0
metadata: {'Python': '3.13.5', 'Platform': 'macOS-16.0-arm64-arm-64bit-Mach-O', 'Packages': {'pytest': '8.3.5', 'pluggy': '1.5.0'}, 'Plugins': {'xdist': '3.7.0', 'qt': '4.4.0', 'anyio': '4.9.0', 'json-report': '1.5.0', 'timeout': '2.4.0', 'metadata': '3.1.1', 'mock': '3.14.0', 'asyncio': '1.0.0'}}
rootdir: /Users/justin/Documents/Github/GOES_VFI
configfile: pytest.ini
plugins: xdist-3.7.0, qt-4.4.0, anyio-4.9.0, json-report-1.5.0, timeout-2.4.0, metadata-3.1.1, mock-3.14.0, asyncio-1.0.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 18 items

tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_concurrent_rendering FAILED [  5%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_custom_colormap_creation FAILED [ 11%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_edge_cases FAILED [ 16%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_extract_metadata_comprehensive FAILED [ 22%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_extract_metadata_error_handling PASSED [ 27%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_extract_metadata_missing_fields FAILED [ 33%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_real_netcdf_simulation PASSED [ 38%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_colormap_variations FAILED [ 44%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_comprehensive FAILED [ 50%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_error_scenarios FAILED [ 55%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_figure_options FAILED [ 61%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_large_data FAILED [ 66%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_memory_efficiency FAILED [ 72%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_output_formats FAILED [ 77%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_with_different_bands FAILED [ 83%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_with_nan_values FAILED [ 88%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_render_png_with_scaling FAILED [ 94%]
tests/unit/test_netcdf_renderer_v2.py::TestNetCDFRendererV2::test_temperature_conversion_accuracy FAILED [100%]

=================================== FAILURES ===================================
... lots of error content ...
=================== 16 failed, 2 passed, 1 warning in 1.54s ===================
"""

def test_regex_patterns():
    """Test the regex patterns."""
    print("Testing regex patterns...")
    
    # Test summary line extraction
    summary_matches = re.findall(r"={5,}\s*(.*?)\s*in\s+[\d.]+s\s*={5,}", sample_output)
    print(f"Summary matches: {summary_matches}")
    
    # Test count extraction from summary
    counts = {}
    for summary_line in summary_matches:
        print(f"Processing summary line: '{summary_line}'")
        for pattern, key in [
            (r"(\d+)\s+passed", "passed"),
            (r"(\d+)\s+failed", "failed"),
            (r"(\d+)\s+skipped", "skipped"),
            (r"(\d+)\s+error(?:s)?", "error"),
        ]:
            match = re.search(pattern, summary_line, re.IGNORECASE)
            if match:
                counts[key] = int(match.group(1))
                print(f"  Found {key}: {match.group(1)}")
    
    print(f"Final counts from summary: {counts}")
    
    # Test fallback patterns on full output
    print("\nTesting fallback patterns on full output...")
    fallback_counts = {}
    for pattern, key in [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+skipped", "skipped"),
        (r"(\d+)\s+error(?:s)?", "error"),
    ]:
        matches = re.findall(pattern, sample_output, re.IGNORECASE)
        print(f"Pattern '{pattern}' matches: {matches}")
        if matches:
            # This might be the problem - taking the first match instead of last
            fallback_counts[key] = int(matches[0])
    
    print(f"Fallback counts: {fallback_counts}")
    
    # Test the original fallback logic (from extract_counts)
    print("\nTesting original fallback logic...")
    passed_matches = re.findall(r"test_\w+.*?PASSED", sample_output)
    failed_matches = re.findall(r"test_\w+.*?FAILED", sample_output)
    skipped_matches = re.findall(r"test_\w+.*?SKIPPED", sample_output)
    error_matches = re.findall(r"test_\w+.*?ERROR", sample_output)
    
    print(f"Individual test line matches:")
    print(f"  PASSED: {len(passed_matches)} matches")
    print(f"  FAILED: {len(failed_matches)} matches")
    print(f"  SKIPPED: {len(skipped_matches)} matches")
    print(f"  ERROR: {len(error_matches)} matches")
    
    # Let's see the content of these matches
    print(f"\nPASSED matches: {passed_matches[:5]}...")  # First 5
    print(f"FAILED matches: {failed_matches[:5]}...")   # First 5
    print(f"ERROR matches: {error_matches[:5]}...")     # First 5
    
    # Now test the most problematic part - the error pattern
    print("\nTesting error pattern with different approaches...")
    
    # Test the error word pattern on the whole output
    error_word_matches = re.findall(r"(\d+)\s+error(?:s)?", sample_output, re.IGNORECASE)
    print(f"Error word pattern matches: {error_word_matches}")
    
    # Test just the word "error" appearances
    error_word_count = sample_output.lower().count("error")
    print(f"Total 'error' word count: {error_word_count}")
    
    # Test with a more specific pattern
    error_test_matches = re.findall(r"test_\w+.*?error", sample_output, re.IGNORECASE)
    print(f"Test+error pattern matches: {len(error_test_matches)}")

if __name__ == "__main__":
    test_regex_patterns()