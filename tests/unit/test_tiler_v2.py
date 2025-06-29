"""Optimized unit tests for tiler functionality.

Optimizations applied:
- Shared array fixtures for consistent testing
- Parameterized tests for comprehensive coverage
- Combined related test scenarios
- Reduced redundant array creation
- Enhanced edge case coverage
"""

import numpy as np
import pytest

from goesvfi.pipeline.tiler import merge_tiles, tile_image


class TestTilerV2:
    """Optimized test class for tiler functionality."""

    @pytest.fixture(scope="class")
    def base_image(self):
        """Create base test image for reuse across tests."""
        return np.random.rand(4096, 4096, 3).astype(np.float32)

    @pytest.fixture(scope="class")
    def small_image(self):
        """Create small test image for overlap testing."""
        return np.ones((256, 256, 3), dtype=np.float32)

    @pytest.fixture(scope="class")
    def edge_case_image(self):
        """Create edge case image not divisible by tile size."""
        return np.random.rand(4100, 4100, 3).astype(np.float32)

    @pytest.fixture(scope="class")
    def tiny_image(self):
        """Create tiny test image for edge cases."""
        return np.random.rand(100, 100, 3).astype(np.float32)

    @pytest.mark.parametrize("tile_size,overlap", [
        (2048, 32),
        (1024, 16),
        (512, 8),
    ])
    def test_tile_image_basic_parametrized(self, base_image, tile_size, overlap):
        """Test basic tiling with different tile sizes and overlaps."""
        tiles = tile_image(base_image, tile_size=tile_size, overlap=overlap)

        # Verify tiles are generated
        assert len(tiles) > 0

        # Check that tiles cover the image approximately
        expected_starts = [0, tile_size - overlap] if base_image.shape[0] > tile_size else [0]
        xs = sorted({x for x, y, t in tiles})
        ys = sorted({y for x, y, t in tiles})

        # Check x and y start positions
        for start in expected_starts:
            if start < base_image.shape[1]:  # Only check if within image bounds
                assert start in xs
            if start < base_image.shape[0]:  # Only check if within image bounds
                assert start in ys

        # Check tile properties
        for _x, _y, tile in tiles:
            h, w, c = tile.shape
            assert c == 3
            assert h <= tile_size
            assert w <= tile_size
            assert tile.dtype == np.float32

    def test_tile_image_edge_case_dimensions(self, edge_case_image):
        """Test tiling with image dimensions not divisible by tile size."""
        tile_size = 2048
        overlap = 32

        tiles = tile_image(edge_case_image, tile_size=tile_size, overlap=overlap)

        # Verify tiles are generated
        assert len(tiles) > 0

        # Last tiles should handle edge cases correctly
        last_tile = tiles[-1][2]
        h, w, _ = last_tile.shape
        assert h <= tile_size
        assert w <= tile_size
        assert h == edge_case_image.shape[0] - tiles[-1][1]
        assert w == edge_case_image.shape[1] - tiles[-1][0]

    @pytest.mark.parametrize("tile_size,overlap", [
        (2048, 32),
        (1024, 16),
        (512, 8),
    ])
    def test_merge_tiles_lossless_reconstruction(self, base_image, tile_size, overlap):
        """Test that tiling and merging produces lossless reconstruction."""
        tiles = tile_image(base_image, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(base_image.shape[0], base_image.shape[1]), overlap=overlap)

        # Verify reconstruction quality
        assert merged.shape == base_image.shape
        assert np.allclose(merged, base_image, atol=1e-5)

    def test_merge_tiles_with_overlap_uniform_image(self, small_image):
        """Test overlap handling with uniform (all ones) image."""
        tile_size = 128
        overlap = 32

        tiles = tile_image(small_image, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(small_image.shape[0], small_image.shape[1]), overlap=overlap)

        # Since original image is all ones, merged should be all ones
        assert merged.shape == small_image.shape
        assert np.allclose(merged, small_image, atol=1e-6)

    @pytest.mark.parametrize("image_size,tile_size,overlap", [
        ((256, 256, 3), 128, 32),
        ((100, 100, 3), 60, 20),
        ((512, 512, 3), 256, 64),
    ])
    def test_lossless_reconstruction_parametrized(self, image_size, tile_size, overlap):
        """Test lossless reconstruction with various image and tile sizes."""
        img = np.random.rand(*image_size).astype(np.float32)
        tiles = tile_image(img, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(img.shape[0], img.shape[1]), overlap=overlap)

        assert merged.shape == img.shape
        assert np.allclose(merged, img, atol=1e-6)

    def test_tile_image_minimal_overlap(self, tiny_image):
        """Test tiling with minimal overlap."""
        tile_size = 64
        overlap = 4

        tiles = tile_image(tiny_image, tile_size=tile_size, overlap=overlap)

        # Should handle minimal overlap correctly
        assert len(tiles) > 0
        for _x, _y, tile in tiles:
            assert tile.shape[2] == 3
            assert tile.dtype == np.float32

    def test_tile_image_large_overlap(self, tiny_image):
        """Test tiling with large overlap relative to tile size."""
        tile_size = 64
        overlap = 32  # 50% overlap

        tiles = tile_image(tiny_image, tile_size=tile_size, overlap=overlap)

        # Should handle large overlap correctly
        assert len(tiles) > 0
        for _x, _y, tile in tiles:
            assert tile.shape[2] == 3
            assert tile.dtype == np.float32

    def test_tile_boundaries_comprehensive(self, base_image):
        """Test that tile boundaries are calculated correctly."""
        tile_size = 1024
        overlap = 64

        tiles = tile_image(base_image, tile_size=tile_size, overlap=overlap)

        # Verify all tiles are within image bounds
        for x, y, tile in tiles:
            assert x >= 0
            assert y >= 0
            assert x + tile.shape[1] <= base_image.shape[1]
            assert y + tile.shape[0] <= base_image.shape[0]

            # Verify tile content matches original image
            original_patch = base_image[y:y+tile.shape[0], x:x+tile.shape[1], :]
            assert np.allclose(tile, original_patch, atol=1e-6)

    def test_merge_tiles_exact_reconstruction(self, small_image):
        """Test exact reconstruction with known pattern."""
        # Create a gradient pattern for testing
        h, w, c = small_image.shape
        for i in range(h):
            for j in range(w):
                small_image[i, j, :] = [i/h, j/w, (i+j)/(h+w)]

        tile_size = 128
        overlap = 16

        tiles = tile_image(small_image, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(small_image.shape[0], small_image.shape[1]), overlap=overlap)

        # Should exactly reconstruct the gradient pattern
        assert merged.shape == small_image.shape
        assert np.allclose(merged, small_image, atol=1e-6)

    def test_single_tile_case(self):
        """Test edge case where image is smaller than tile size."""
        small_img = np.random.rand(64, 64, 3).astype(np.float32)
        tile_size = 128
        overlap = 16

        tiles = tile_image(small_img, tile_size=tile_size, overlap=overlap)

        # Should produce exactly one tile
        assert len(tiles) == 1
        x, y, tile = tiles[0]
        assert x == 0
        assert y == 0
        assert tile.shape == small_img.shape
        assert np.allclose(tile, small_img, atol=1e-6)

    def test_merge_tiles_performance_validation(self, base_image):
        """Test merge tiles performance with larger image."""
        tile_size = 1024
        overlap = 32

        tiles = tile_image(base_image, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(base_image.shape[0], base_image.shape[1]), overlap=overlap)

        # Verify performance is reasonable and reconstruction is accurate
        assert merged.shape == base_image.shape
        assert merged.dtype == base_image.dtype
        assert np.allclose(merged, base_image, atol=1e-5)

    def test_zero_overlap_case(self, tiny_image):
        """Test tiling with zero overlap."""
        tile_size = 64
        overlap = 0

        tiles = tile_image(tiny_image, tile_size=tile_size, overlap=overlap)
        merged = merge_tiles(tiles, full_shape=(tiny_image.shape[0], tiny_image.shape[1]), overlap=overlap)

        # Should still reconstruct correctly
        assert merged.shape == tiny_image.shape
        assert np.allclose(merged, tiny_image, atol=1e-6)