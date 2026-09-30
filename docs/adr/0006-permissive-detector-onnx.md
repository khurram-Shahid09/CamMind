# ADR-0006: Apache-2.0 object detector, run with ONNX Runtime

**Status:** Accepted (model pick after the day-3 benchmark) · 2026-10-30

## Context
The detector is the most-run component. It must:
- run on a CPU at 5 fps for several cameras, and much faster on a GPU
- detect people and vehicles well, including small far-away people
- run on Windows, Linux, mini PCs and Jetsons
- carry a licence that doesn't block a future commercial or self-hosted product.

The popular Ultralytics YOLO models are AGPL-3.0. Offering them as part of a network service or closed product requires releasing the source or buying an enterprise licence.

## Decision
- Use an **Apache-2.0** real-time detector trained on COCO: **RT-DETRv2** or **D-FINE**, small variant, exported to ONNX at 640 px. The final pick comes from a day-3 benchmark on the eval clips (recall on small people, CPU latency).
- Run it with **ONNX Runtime**, choosing CUDA → DirectML → CPU at start-up. One model file for every platform; TensorRT for Jetson in v0.2.
- The detector sits behind a `Detector` interface, so an Ultralytics plug-in can be added for personal or non-commercial users who accept its licence.
- Model files are downloaded on first run from a pinned URL and checked by SHA-256.

## Consequences
- ✅ No licence surprises for a school or company deployment.
- ✅ Hardware-portable; GPU acceleration on Windows laptops through DirectML.
- ❌ Transformer-based detectors can be slower on CPU than the smallest YOLO models. Mitigated by motion gating (the detector skips most frames), a 5 fps sample rate and batching across cameras.
- ❌ COCO classes only. Helmets, vests, packages and smoke go through `verify` / `scene`. A fine-tuned safety-gear model is a possible v0.3 addition.
