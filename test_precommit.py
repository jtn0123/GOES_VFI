#!/usr/bin/env python3
"""
Test file for pre-commit hooks verification.

This file simply demonstrates proper Python styling according to
the project's linting rules.
"""

from typing import Dict, List, Optional


def example_function(
    param1: str, param2: Optional[int] = None, param3: List[str] = None
) -> Dict[str, str]:
    """
    Example function with proper type hints and formatting.

    Args:
        param1: First parameter description
        param2: Second parameter description
        param3: Third parameter description

    Returns:
        Dictionary mapping parameter names to their string representations
    """
    result = {"param1": param1}

    if param2 is not None:
        result["param2"] = str(param2)

    if param3:
        result["param3"] = ", ".join(param3)

    return result


class ExampleClass:
    """Example class demonstrating proper class styling."""

    def __init__(self, name: str) -> None:
        """Initialize with a name.

        Args:
            name: The name to use
        """
        self.name = name

    def get_formatted_name(self) -> str:
        """Return the formatted name.

        Returns:
            Formatted name string
        """
        return f"Name: {self.name}"


if __name__ == "__main__":
    # Example usage
    example = ExampleClass("Test")
    print(example.get_formatted_name())

    result = example_function("test", 42, ["a", "b", "c"])
    print(result)
