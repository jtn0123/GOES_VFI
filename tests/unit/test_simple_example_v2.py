"""Simple example test file to demonstrate v2 test structure."""

from pathlib import Path

import pytest


class TestSimpleExampleV2:
    """Simple example test class for v2 tests."""

    def test_basic_assertion(self) -> None:
        """Test basic assertion works."""
        assert 1 + 1 == 2

    def test_path_operations(self) -> None:
        """Test path operations work correctly."""
        test_path = Path("/tmp/test")
        assert test_path.name == "test"
        assert test_path.parent == Path("/tmp")

    @pytest.mark.parametrize(
        "input_val, expected",
        [
            (1, 2),
            (2, 4),
            (3, 6),
            (4, 8),
        ],
    )
    def test_parameterized_doubling(self, input_val: int, expected: int) -> None:
        """Test parameterized test with doubling function."""
        result = input_val * 2
        assert result == expected
