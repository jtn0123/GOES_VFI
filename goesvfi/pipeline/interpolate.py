# TODO: IFRNet‑S via ONNX Runtime (CoreML/DirectML)

from __future__ import annotations
import platform
import pathlib
import numpy as np  # type: ignore
import onnxruntime as ort  # type: ignore

class IFRNetSession:
    """Wraps ONNXRuntime session for IFRNet‑S.
    Chooses CoreML EP on macOS, DirectML on Windows, else CPU."""

    def __init__(self, model_path: pathlib.Path):
        self.model_path = model_path
        providers = ["CPUExecutionProvider"]
        if platform.system() == "Darwin":
            providers.insert(0, "CoreMLExecutionProvider")
        elif platform.system() == "Windows":
            providers.insert(0, "DmlExecutionProvider")
        self.sess = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.sess.get_inputs()[0].name

    def _prep(self, img: np.ndarray) -> np.ndarray:
        # convert H×W×3 float32 0‑1 → 3×H×W fp32
        return img.transpose(2,0,1)[None]

    def interpolate_pair(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        inp = np.concatenate([self._prep(img1), self._prep(img2)], axis=1)
        out = self.sess.run(None, {self.input_name: inp})[0][0]  # 3×H×W
        return out.transpose(1,2,0)
