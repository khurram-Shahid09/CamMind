"""Object detection (docs/07-video-pipeline.md, "3 · Detection"; ADR-0006).

Apache-2.0 COCO detectors (D-FINE, RT-DETRv2) exported to ONNX, run with ONNX Runtime on the
best available device: CUDA, then DirectML (Windows GPUs), then CPU. Model files are
downloaded once from a pinned revision and checked by SHA-256.

The exports take a 640x640 RGB image scaled to 0-1 (plain resize, no letterbox) and return
``logits`` (B x queries x 80) and ``pred_boxes`` (B x queries x 4, centre x/y, width, height,
relative to the image), so boxes map straight back to the original frame.
"""

import hashlib
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

log = logging.getLogger(__name__)

# COCO's 80 classes in model order, named as in docs/05-rule-spec.md.
CLASS_NAMES: tuple[str, ...] = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)


@dataclass(frozen=True)
class ModelSpec:
    repo: str
    revision: str
    file: str
    sha256: str
    size: int = 640


MODELS = {
    "dfine-n": ModelSpec(
        "onnx-community/dfine_n_coco-ONNX",
        "380d2839c327efaf65dd0fe0c2c10ab7fadd5473",
        "onnx/model.onnx",
        "0f684f409618ee8a822410e754a29caa817d1aa16283ce89cad936d0a48e2f35",
    ),
    "dfine-s": ModelSpec(
        "onnx-community/dfine_s_coco-ONNX",
        "a3cf03147a9b86c78475139115c8ac142577352d",
        "onnx/model.onnx",
        "cd8a49a945feda6d28c6304ae8ae85c2759ba1d78a5a83a22c5ce8db82ef7238",
    ),
    "rtdetrv2-s": ModelSpec(
        "onnx-community/rtdetr_v2_r18vd-ONNX",
        "936f90b6a476c6da4dfe053fc521af55285976ba",
        "onnx/model.onnx",
        "583a236ac21c95a7fd94f284fc21485e42355bfef82c27011ba78fbc09ee87e2",
    ),
}
DEFAULT_MODEL = "dfine-s"
PROVIDERS = ("CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider")


@dataclass
class Detections:
    """Boxes in pixels of the original frame (x1, y1, x2, y2)."""

    boxes: np.ndarray  # N x 4 float32
    scores: np.ndarray  # N float32
    class_ids: np.ndarray  # N int

    @classmethod
    def empty(cls) -> "Detections":
        return cls(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), np.zeros(0, int))

    def __len__(self) -> int:
        return len(self.scores)

    def names(self) -> list[str]:
        return [CLASS_NAMES[i] for i in self.class_ids]


def models_dir() -> Path:
    default = Path.home() / ".cache" / "cammind" / "models"
    return Path(os.environ.get("CAMMIND_MODELS_DIR", default))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(name: str) -> Path:
    """The model file, downloaded on first use from the pinned revision."""
    spec = MODELS[name]
    path = models_dir() / f"{name}-{spec.sha256[:12]}.onnx"
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{spec.repo}/resolve/{spec.revision}/{spec.file}"
    partial = path.with_suffix(".part")
    log.info("downloading %s (%s)", name, url)
    urllib.request.urlretrieve(url, partial)  # noqa: S310  # pinned https URL
    actual = _sha256(partial)
    if actual != spec.sha256:
        partial.unlink()
        raise RuntimeError(f"{name}: checksum mismatch ({actual})")
    partial.rename(path)
    return path


class Detector:
    def __init__(
        self,
        name: str = DEFAULT_MODEL,
        *,
        min_confidence: float = 0.35,
        classes: set[str] | None = None,
        providers: list[str] | None = None,
    ) -> None:
        self.name = name
        self.size = MODELS[name].size
        self.min_confidence = min_confidence
        self.class_filter = np.array([CLASS_NAMES.index(c) for c in classes]) if classes else None
        available = ort.get_available_providers()
        chosen = providers or [p for p in PROVIDERS if p in available]
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(ensure_model(name)), sess_options=options, providers=chosen
        )
        self.provider = self.session.get_providers()[0]
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.last_ms = 0.0

    def _prepare(self, image: np.ndarray) -> np.ndarray:
        resized = cv2.resize(image, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return rgb.transpose(2, 0, 1).astype(np.float32) / 255.0

    def detect(self, images: list[np.ndarray]) -> list[Detections]:
        """One call for several frames (cameras are batched by the worker)."""
        if not images:
            return []
        batch = np.stack([self._prepare(image) for image in images])
        started = time.perf_counter()
        outputs = dict(
            zip(self.output_names, self.session.run(None, {self.input_name: batch}), strict=True)
        )
        self.last_ms = (time.perf_counter() - started) * 1000
        logits, boxes = outputs["logits"], outputs["pred_boxes"]
        return [
            self._decode(logits[i], boxes[i], images[i].shape[1], images[i].shape[0])
            for i in range(len(images))
        ]

    def _decode(self, logits: np.ndarray, boxes: np.ndarray, width: int, height: int) -> Detections:
        scores = 1.0 / (1.0 + np.exp(-logits))  # queries x classes
        if self.class_filter is not None:
            masked = np.zeros_like(scores)
            masked[:, self.class_filter] = scores[:, self.class_filter]
            scores = masked
        class_ids = scores.argmax(axis=1)
        best = scores[np.arange(len(scores)), class_ids]
        keep = best >= self.min_confidence
        if not keep.any():
            return Detections.empty()
        cx, cy, w, h = boxes[keep].T
        xyxy = np.stack(
            [
                (cx - w / 2) * width,
                (cy - h / 2) * height,
                (cx + w / 2) * width,
                (cy + h / 2) * height,
            ],
            axis=1,
        ).clip(0, [width, height, width, height])
        return Detections(xyxy.astype(np.float32), best[keep].astype(np.float32), class_ids[keep])
