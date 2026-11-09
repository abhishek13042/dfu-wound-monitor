---
title: DFU-WoundMonitor browser demo
emoji: 🩹
colorFrom: purple
colorTo: green
sdk: static
app_file: index.html
pinned: false
short_description: Foot-ulcer photo quality check and segmentation, in-browser
---

# DFU-WoundMonitor browser demo

**Research prototype. Not a medical device.** Results are image-derived technical
measurements, not a diagnosis.

This Space is a static page. Everything runs in the visitor's browser:

1. The photo is decoded and checked against the nine limits of quality gate
   `p03-s02-v1`. A photo that fails any check is refused and not measured.
2. A photo that passes is segmented by the ResNet34 U-Net
   (`spec-02-03-resnet34-unet-512-onnx-v1`) with ONNX Runtime Web, using WebGPU
   when available and WebAssembly otherwise. The 97.7 MB model is downloaded from
   [abhishek1402/dfu-resnet34-unet](https://huggingface.co/abhishek1402/dfu-resnet34-unet)
   at a pinned revision, checked against its SHA-256, and cached by the browser.
3. Four flipped views are averaged, the probability map is thresholded at 0.40 and
   regions under 128 px are dropped, the same as the project's Python pipeline.

The photo is never uploaded. Measurements are in pixels only.

Held-out Dice: 0.922 on FUSeg2021 test, 0.256 on the LowerLimb external set. The
second number is the one to keep in mind for photos unlike the training data.

Source: `deploy/hf_static_space/` in the DFU-WoundMonitor repository.
