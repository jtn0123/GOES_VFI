#!/bin/bash
# Performance comparison script for optimized tests

echo "🚀 Test Performance Comparison"
echo "=============================================="

# Activate virtual environment
source .venv/bin/activate

echo ""
echo "1️⃣ Testing: Security Validation Tests"
echo "----------------------------------------------"

echo "Original version:"
time python -m pytest tests/unit/test_security.py -v --tb=short --no-header -q

echo ""
echo "Optimized v2 version:"
time python -m pytest tests/unit/test_security_optimized_v2.py -v --tb=short --no-header -q

echo ""
echo "2️⃣ Testing: Model Manager Tests"
echo "----------------------------------------------"

echo "Original version:"
time python -m pytest tests/unit/test_model_manager.py -v --tb=short --no-header -q

echo ""
echo "Optimized v2 version:"
time python -m pytest tests/unit/test_model_manager_optimized_v2.py -v --tb=short --no-header -q

echo ""
echo "✅ Performance comparison complete!"
echo ""
echo "Note: The 'real' time shows the actual wall-clock time taken."
echo "The optimized versions use:"
echo "  • Shared fixtures at class level"
echo "  • Mocked time operations"
echo "  • In-memory filesystem"
echo "  • Batch validation"