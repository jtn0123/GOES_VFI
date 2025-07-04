#!/usr/bin/env python3
"""Debug the actual parser behavior."""

import subprocess
import sys
import os

# Import the parser class from the test runner
sys.path.insert(0, "/Users/justin/Documents/Github/GOES_VFI")
from run_all_tests import PytestOutputParser

def capture_real_output():
    """Capture real pytest output."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, ".venv", "bin", "python")
    
    cmd = [venv_python, "-m", "pytest", "tests/unit/test_netcdf_renderer_v2.py", "-v", "-p", "no:cov"]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=60,
        )
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return None, -1

def debug_parser():
    """Debug the parser behavior."""
    print("Capturing real pytest output...")
    output, returncode = capture_real_output()
    
    if output is None:
        print("Timeout occurred")
        return
    
    print(f"Return code: {returncode}")
    print(f"Output length: {len(output)} characters")
    
    # Parse with the actual parser
    parser = PytestOutputParser()
    result = parser.parse_output("tests/unit/test_netcdf_renderer_v2.py", output, 1.0)
    
    print(f"\nParser results:")
    print(f"  Status: {result.status}")
    print(f"  Collected: {result.collected}")
    print(f"  Counts: passed={result.counts.passed}, failed={result.counts.failed}, skipped={result.counts.skipped}, error={result.counts.error}")
    
    # Debug the extract_counts method step by step
    print(f"\nDebugging extract_counts...")
    counts = parser.extract_counts(output)
    print(f"  extract_counts result: passed={counts.passed}, failed={counts.failed}, skipped={counts.skipped}, error={counts.error}")
    
    # Debug the summary extraction
    print(f"\nDebugging _extract_summary_counts...")
    summary_counts = parser._extract_summary_counts(output)
    print(f"  _extract_summary_counts result: {summary_counts}")
    
    # Let's see what the summary lines actually contain
    import re
    summary_matches = re.findall(r"={5,}\s*(.*?)\s*in\s+[\d.]+s\s*={5,}", output)
    print(f"  Actual summary matches: {summary_matches}")
    
    # Let's look for the summary pattern more carefully
    print(f"  Looking for summary pattern in output...")
    lines = output.split('\n')
    for i, line in enumerate(lines):
        if '=====' in line and ('failed' in line or 'passed' in line) and 'in ' in line and 's ' in line:
            print(f"    Line {i}: {repr(line)}")
        if 'failed' in line and 'passed' in line and 'in ' in line:
            print(f"    Summary candidate {i}: {repr(line)}")
    
    # Try a more flexible summary pattern
    flexible_matches = re.findall(r"=+\s*(.*?failed.*?passed.*?in\s+[\d.]+s.*?)=+", output, re.IGNORECASE)
    print(f"  Flexible summary matches: {flexible_matches}")
    
    # Try another approach
    simple_matches = re.findall(r"(.*?\d+\s+failed.*?\d+\s+passed.*?in\s+[\d.]+s.*?)", output, re.IGNORECASE)
    print(f"  Simple summary matches: {simple_matches}")
    
    # Debug the fallback pattern on full output
    print(f"  Testing fallback patterns on full output...")
    for pattern, key in [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+skipped", "skipped"),
        (r"(\d+)\s+error(?:s)?", "error"),
    ]:
        all_matches = re.findall(pattern, output, re.IGNORECASE)
        print(f"    Pattern '{pattern}' found {len(all_matches)} matches: {all_matches[:10]}...")
        if all_matches:
            first_match = re.search(pattern, output, re.IGNORECASE)
            if first_match:
                print(f"      First match: {first_match.group(1)} at position {first_match.start()}")
                if key == "error" and first_match.group(1) == "262":
                    context_start = max(0, first_match.start() - 50)
                    context_end = min(len(output), first_match.start() + 100)
                    context = output[context_start:context_end]
                    print(f"        Context around 262 error: {repr(context)}")
    
    
    # Debug collected count extraction  
    print(f"\nDebugging _extract_collected_count...")
    collected = parser._extract_collected_count(output)
    print(f"  _extract_collected_count result: {collected}")
    
    # Debug the special case adjustment
    print(f"\nDebugging _adjust_counts_for_special_cases...")
    original_counts = parser.extract_counts(output)
    adjusted_counts = parser._adjust_counts_for_special_cases(
        "tests/unit/test_netcdf_renderer_v2.py",
        output,
        original_counts,
        collected,
        result.status
    )
    print(f"  Before adjustment: passed={original_counts.passed}, failed={original_counts.failed}, skipped={original_counts.skipped}, error={original_counts.error}")
    print(f"  After adjustment: passed={adjusted_counts.passed}, failed={adjusted_counts.failed}, skipped={adjusted_counts.skipped}, error={adjusted_counts.error}")
    
    # Check specific parts of the output for clues
    print(f"\nChecking output for suspicious content...")
    lines = output.split('\n')
    error_lines = [line for line in lines if 'error' in line.lower()]
    print(f"  Lines containing 'error': {len(error_lines)}")
    if error_lines:
        print(f"  First few error lines:")
        for line in error_lines[:5]:
            print(f"    {repr(line)}")

if __name__ == "__main__":
    debug_parser()