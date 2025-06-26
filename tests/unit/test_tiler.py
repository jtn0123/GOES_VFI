import numpy as np

from goesvfi.pipeline.tiler import merge_tiles, tile_image


def test_tile_image_basic():
    # Create a mock image of size 4096x4096 with 3 channels
    img = np.random.rand(4096, 4096, 3).astype(np.float32)
    tile_size = 2048
    overlap = 32

    tiles = tile_image(img, tile_size=tile_size, overlap=overlap)

    # Check that tiles cover the image approximately
    # Tiles should start at positions 0, 2016 (2048-32), and last tile may be smaller
    expected_starts = [0, tile_size - overlap]
    xs = sorted(set(x for x, y, t in tiles))
    ys = sorted(set(y for x, y, t in tiles))

    # Check x and y start positions
    for start in expected_starts:
        assert start in xs
        assert start in ys

    # Check tile sizes except possibly last tiles
    for x, y, tile in tiles:
        h, w, c = tile.shape
        assert c == 3
        assert h <= tile_size
        assert w <= tile_size
        # Tiles should be float32
        assert tile.dtype == np.float32


def test_tile_image_edge_case():
    # Image size not divisible by tile size
    img = np.random.rand(4100, 4100, 3).astype(np.float32)
    tile_size = 2048
    overlap = 32

    tiles = tile_image(img, tile_size=tile_size, overlap=overlap)

    # Last tiles should have smaller size
    last_tile = tiles[-1][2]
    h, w, _ = last_tile.shape
    assert h <= tile_size
    assert w <= tile_size
    assert h == img.shape[0] - tiles[-1][1]
    assert w == img.shape[1] - tiles[-1][0]


def test_merge_tiles_basic():
    # Create a mock image
    img = np.random.rand(4096, 4096, 3).astype(np.float32)
    tile_size = 2048
    overlap = 32

    tiles = tile_image(img, tile_size=tile_size, overlap=overlap)
    merged = merge_tiles(tiles, full_shape=(img.shape[0], img.shape[1]), overlap=overlap)

    # The merged image should be close to the original
    # Allow some tolerance due to overlap averaging
    assert merged.shape == img.shape
    assert np.allclose(merged, img, atol=1e-5)


def test_merge_tiles_with_overlap():
    # Create a small image to test overlap handling
    img = np.ones((100, 100, 3), dtype=np.float32)
    tile_size = 60
    overlap = 20

    tiles = tile_image(img, tile_size=tile_size, overlap=overlap)
    merged = merge_tiles(tiles, full_shape=(img.shape[0], img.shape[1]), overlap=overlap)

    # Since original image is all ones, merged should be all ones
    assert merged.shape == img.shape
    assert np.allclose(merged, img, atol=1e-6)
