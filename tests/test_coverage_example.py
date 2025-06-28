"""
Example test file to demonstrate coverage reporting.
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


# Tests


class TestSimpleFunction:
    """Test simple_function with full branch coverage."""

    def test_x_greater_than_y(self) -> None:
        assert simple_function(10, 5) == 5

    def test_x_less_than_y(self) -> None:
        assert simple_function(5, 10) == 5

    def test_x_equals_y(self) -> None:
        assert simple_function(5, 5) == 0


class TestComplexFunction:
    """Test complex_function with branch coverage."""

    def test_empty_value_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Value cannot be empty"):
            complex_function("")

    def test_flag_enabled_short_string(self) -> None:
        result = complex_function("hello", flag=True)
        assert result == "HELLO"

    def test_flag_enabled_long_string(self) -> None:
        result = complex_function("this is a very long string", flag=True)
        assert result == "THIS IS A ..."

    def test_flag_disabled_long_string(self) -> None:
        result = complex_function("HELLO WORLD", flag=False)
        assert result == "hello world"

    def test_flag_disabled_short_string(self) -> None:
        result = complex_function("HI", flag=False)
        assert result == "hi___"


class TestExampleClass:
    """Test ExampleClass with coverage."""

    def test_initialization(self) -> None:
        obj = ExampleClass("test")
        assert obj.name == "test"
        assert obj._cache == {}

    def test_process_without_cache(self) -> None:
        obj = ExampleClass("processor")
        result = obj.process("data")
        assert result == "processor: data"

    def test_process_with_cache(self) -> None:
        obj = ExampleClass("processor")
        # First call
        result1 = obj.process("data")
        # Second call should use cache
        result2 = obj.process("data")
        assert result1 == result2
        assert len(obj._cache) == 1

    def test_clear_cache(self) -> None:
        obj = ExampleClass("processor")
        obj.process("data1")
        obj.process("data2")
        assert len(obj._cache) == 2

        obj.clear_cache()
        assert len(obj._cache) == 0


# Example of excluding code from coverage
def debug_function() -> str:  # pragma: no cover
    """This function is only for debugging and excluded from coverage."""
    return "debug"


if __name__ == "__main__":  # pragma: no cover
    # This block is excluded from coverage

    obj = ExampleClass("main")
