### Short‑term
- [ ] CUDA Execution Provider (Linux & Windows, NVIDIA)
- [ ] Intel Arc: onnxruntime oneAPI EP

### Medium‑term
- [ ] AV1 export via libaom or SVT‑AV1
- [ ] 10‑bit processing pipeline
- [ ] Batch job queue + parallel worker pool

### Long‑term
- [ ] PyInstaller/Briefcase packaging
- [ ] Full SatDump plugin integration

### Refinements / Features
- [ ] Python API backend for persistent model loading (alternative to CLI calls)
- [ ] Offer a UI control for "frames between" (i.e. the -n value) - *Partially addressed via 'Interpolations per pair', but underlying CLI call strategy differs from example*
- [ ] Model-size selector (v2/v3/v4 trade‑offs)
- [ ] Tile-level parallelism (process tiles concurrently)
- [ ] Driver/hardware tuning & native‑vs‑universal benchmarks
- [ ] Investigate RIFE CLI batch processing (`-i pattern`, `-n num_mid`, `--cache-dir`) - *Per user example, seems incompatible currently*
- [ ] Improve/Validate caching for multi-frame interpolation (`interp_count > 1`)
- [ ] Address `mypy` type mismatch for `NDArray[Any]` from cache vs `NDArray[np.float32]` expectation in `run_vfi.py`
- [ ] Hardware-Accelerated Encoding (FFmpeg `hevc_videotoolbox`)



# TODO List for GOES-VFI

## UI Improvements

- [ ] Add more tooltips/hover text to explain various settings (e.g., Encoder options, FFmpeg Quality settings, Interpolation parameters).
- [ ] Dynamically disable/grey out UI elements that are not applicable based on current selections. For example:
    - Disable CRF preset dropdown in "FFmpeg Quality" tab when a hardware encoder is selected on the main tab.
    - Disable Bitrate/Buffer Size spinboxes in "FFmpeg Quality" tab when a software CRF encoder or "None" is selected on the main tab.

## Features

- [ ] ... (Placeholder for future feature ideas)

## Bugs / Refactoring

- [ ] Tile Size spinbox in Interpolate tab doesn't visually enable/disable when 'Enable tiling' is toggled, despite internal logic appearing correct. Needs investigation into potential event/update issues or style conflicts.
- [ ] Investigate and fix `AttributeError`/Segfault in `tests/integration/test_pipeline.py::test_basic_interpolation` (currently skipped).
- [ ] Investigate and fix Segmentation Fault in `tests/integration/test_pipeline.py::test_skip_model` (currently skipped).
- [ ] Investigate and fix Segmentation Fault in `tests/integration/test_pipeline.py::test_cropping` (currently skipped).
- [ ] ... (Placeholder for bugs or code cleanup tasks)