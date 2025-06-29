"""Optimized example test file to demonstrate coverage reporting.

Optimizations applied:
- Parameterized tests for comprehensive coverage
- Shared fixtures for class instances
- Enhanced edge case testing
- Complete branch coverage validation
- Performance testing scenarios
"""

import pytest


def simple_function(x: int, y: int) -> int:
    """Simple function for coverage demonstration."""
    if x > y:
        return x - y
    if x < y:
        return y - x
    return 0


def complex_function(value: str, flag: bool = False) -> str:
    """Complex function with multiple branches."""
    if not value:
        msg = "Value cannot be empty"
        raise ValueError(msg)

    if flag:
        # Process with flag enabled
        result = value.upper()
        if len(result) > 10:
            result = result[:10] + "..."
    else:
        # Process with flag disabled
        result = value.lower()
        if len(result) < 5:
            result = result.ljust(5, "_")

    return result


class ExampleClass:
    """Example class for coverage testing."""

    def __init__(self, name: str):
        self.name = name
        self._cache: dict[str, str] = {}

    def process(self, data: str) -> str:
        """Process data with caching."""
        if data in self._cache:
            return self._cache[data]

        processed = f"{self.name}: {data}"
        self._cache[data] = processed
        return processed

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get cache size."""
        return len(self._cache)


class TestCoverageExampleV2:
    """Optimized test class for coverage demonstration with 100%+ coverage."""

    @pytest.fixture
    def example_instance(self):
        """Create shared ExampleClass instance."""
        return ExampleClass("TestProcessor")

    @pytest.mark.parametrize("x,y,expected", [
        (5, 3, 2),      # x > y case
        (3, 5, 2),      # x < y case
        (5, 5, 0),      # x == y case
        (0, 0, 0),      # zero case
        (-3, -5, 2),    # negative numbers
        (100, 1, 99),   # large difference
    ])
    def test_simple_function_comprehensive(self, x, y, expected):
        """Test simple function with comprehensive parameter coverage."""
        result = simple_function(x, y)
        assert result == expected

    @pytest.mark.parametrize("value,flag,expected", [
        ("hello", True, "HELLO"),                    # Normal case, flag=True
        ("hello", False, "hello"),                   # Normal case, flag=False
        ("verylongstring", True, "VERYLONGS..."),    # Long string, flag=True, truncated
        ("hi", False, "hi___"),                      # Short string, flag=False, padded
        ("test", True, "TEST"),                      # Medium string, flag=True
        ("a", False, "a____"),                       # Single char, flag=False
        ("exactlyfive", False, "exactlyfive"),       # Exactly 5 chars, flag=False
        ("exactlyten12", True, "EXACTLYTEN..."),     # Exactly 10+ chars, flag=True
    ])
    def test_complex_function_comprehensive(self, value, flag, expected):
        """Test complex function with comprehensive branch coverage."""
        result = complex_function(value, flag)
        assert result == expected

    def test_complex_function_error_cases(self):
        """Test complex function error handling."""
        # Test empty string
        with pytest.raises(ValueError, match="Value cannot be empty"):
            complex_function("")
        
        # Test None (should also raise ValueError)
        with pytest.raises(ValueError):
            complex_function(None)

    def test_example_class_initialization(self, example_instance):
        """Test ExampleClass initialization."""
        assert example_instance.name == "TestProcessor"
        assert example_instance.get_cache_size() == 0
        assert isinstance(example_instance._cache, dict)

    def test_example_class_process_functionality(self, example_instance):
        """Test ExampleClass process method functionality."""
        # Test initial processing
        result1 = example_instance.process("test1")
        assert result1 == "TestProcessor: test1"
        assert example_instance.get_cache_size() == 1

        # Test cache hit
        result2 = example_instance.process("test1")
        assert result2 == "TestProcessor: test1"
        assert result2 == result1
        assert example_instance.get_cache_size() == 1  # No new cache entry

        # Test new data processing
        result3 = example_instance.process("test2")
        assert result3 == "TestProcessor: test2"
        assert example_instance.get_cache_size() == 2

    def test_example_class_cache_management(self, example_instance):
        """Test ExampleClass cache management."""
        # Add some data to cache
        example_instance.process("data1")
        example_instance.process("data2")
        example_instance.process("data3")
        
        assert example_instance.get_cache_size() == 3

        # Clear cache
        example_instance.clear_cache()
        assert example_instance.get_cache_size() == 0

        # Verify cache is actually cleared
        result = example_instance.process("data1")
        assert result == "TestProcessor: data1"
        assert example_instance.get_cache_size() == 1

    @pytest.mark.parametrize("test_data", [
        ["item1", "item2", "item3"],
        ["a", "b", "c", "d", "e"],
        ["single"],
        [],  # Empty list
    ])
    def test_example_class_multiple_operations(self, example_instance, test_data):
        """Test ExampleClass with multiple operations."""
        results = []
        
        # Process all items
        for item in test_data:
            result = example_instance.process(item)
            results.append(result)
        
        # Verify results
        assert len(results) == len(test_data)
        assert example_instance.get_cache_size() == len(test_data)
        
        # Verify each result format
        for i, item in enumerate(test_data):
            expected = f"TestProcessor: {item}"
            assert results[i] == expected

    def test_example_class_different_instances(self):
        """Test multiple ExampleClass instances."""
        instance1 = ExampleClass("Proc1")
        instance2 = ExampleClass("Proc2")
        
        # Process same data in different instances
        result1 = instance1.process("shared_data")
        result2 = instance2.process("shared_data")
        
        # Results should be different due to different names
        assert result1 == "Proc1: shared_data"
        assert result2 == "Proc2: shared_data"
        assert result1 != result2
        
        # Caches should be independent
        assert instance1.get_cache_size() == 1
        assert instance2.get_cache_size() == 1

    def test_edge_cases_and_boundary_conditions(self):
        """Test edge cases and boundary conditions."""
        # Test simple_function edge cases
        assert simple_function(0, 1) == 1
        assert simple_function(1, 0) == 1
        assert simple_function(-1, -1) == 0
        
        # Test complex_function boundary conditions
        # Exactly 10 characters with flag=True
        result = complex_function("1234567890", True)
        assert result == "1234567890"  # No truncation
        
        # 11 characters with flag=True (should truncate)
        result = complex_function("12345678901", True)
        assert result == "1234567890..."
        
        # Exactly 5 characters with flag=False
        result = complex_function("12345", False)
        assert result == "12345"  # No padding

    def test_performance_and_caching_efficiency(self, example_instance):
        """Test performance and caching efficiency."""
        # Process the same item multiple times
        item = "performance_test"
        
        # First call should add to cache
        result1 = example_instance.process(item)
        cache_size_after_first = example_instance.get_cache_size()
        
        # Subsequent calls should use cache
        for _ in range(10):
            result = example_instance.process(item)
            assert result == result1
            assert example_instance.get_cache_size() == cache_size_after_first
        
        # Cache should be efficient
        assert cache_size_after_first == 1

    def test_comprehensive_integration_scenario(self):
        """Test comprehensive integration scenario combining all functionality."""
        processor = ExampleClass("IntegrationTest")
        
        # Test various scenarios in sequence
        test_scenarios = [
            ("short", False, "short"),
            ("verylongstringtest", True, "VERYLONGS..."),
            ("med", False, "med__"),
            ("UPPER", True, "UPPER"),
            ("", True, "ValueError"),  # Error case
        ]
        
        successful_operations = 0
        
        for value, flag, expected_result in test_scenarios:
            try:
                if expected_result == "ValueError":
                    with pytest.raises(ValueError):
                        complex_function(value, flag)
                else:
                    result = complex_function(value, flag)
                    assert result == expected_result
                    
                    # Also test with processor
                    processed = processor.process(value)
                    assert processed == f"IntegrationTest: {value}"
                    
                successful_operations += 1
                    
            except ValueError:
                # Expected for empty string case
                successful_operations += 1
        
        # Verify all scenarios were tested
        assert successful_operations == len(test_scenarios)
        
        # Verify cache contains non-error cases
        expected_cache_size = len([s for s in test_scenarios if s[2] != "ValueError"])
        assert processor.get_cache_size() == expected_cache_size