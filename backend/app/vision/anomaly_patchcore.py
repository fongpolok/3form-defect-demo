"""
Detection option B: pretrained-backbone anomaly detection, a lightweight
PatchCore/PaDiM-style approach. Only needs "good" sample images (no labeled
defects) — it extracts a grid of feature-patch embeddings from an ImageNet-
pretrained CNN backbone, keeps them as a "memory bank" of what normal looks
like, and at inference time flags patches whose nearest neighbour in that
bank is unusually far away. This is the closest of the three options to how
ViDi's unsupervised anomaly mode is typically used.

CPU-only and deliberately small (a coreset-subsampled memory bank, a
mid-depth ResNet18 layer) so it stays fast enough for a live demo without a
GPU — accuracy on real product images will improve if you switch to a
deeper layer/backbone and a larger coreset once real data exists, both
tunable below.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torchvision
from sklearn.neighbors import NearestNeighbors
from torchvision.models import ResNet18_Weights

from app.logging_setup import get_logger
from app.vision.base import DefectBox, DefectDetector, DetectionResult, encode_overlay

logger = get_logger(__name__)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class PatchCoreDetector(DefectDetector):
    name = "patchcore"

    def __init__(
        self,
        image_size: int = 224,
        coreset_size: int = 400,
        k_neighbors: int = 3,
        anomaly_threshold: float = 12.0,
        min_blob_area: int = 30,
        seed: int = 0,
    ) -> None:
        self.image_size = image_size
        self.coreset_size = coreset_size
        self.k_neighbors = k_neighbors
        self.anomaly_threshold = anomaly_threshold
        self.min_blob_area = min_blob_area
        self._rng = np.random.default_rng(seed)

        weights = ResNet18_Weights.DEFAULT
        model = torchvision.models.resnet18(weights=weights)
        model.eval()
        self._model = model
        self._features: torch.Tensor | None = None
        model.layer2.register_forward_hook(self._hook)

        self._memory_bank: np.ndarray | None = None
        self._nn: NearestNeighbors | None = None
        self._feature_grid_hw: tuple[int, int] | None = None

    def _hook(self, module, inp, output) -> None:
        self._features = output

    def _preprocess(self, image_bgr: np.ndarray) -> torch.Tensor:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.image_size, self.image_size)).astype(np.float32) / 255.0
        normed = (resized - IMAGENET_MEAN) / IMAGENET_STD
        tensor = torch.from_numpy(normed.transpose(2, 0, 1)).unsqueeze(0).float()
        return tensor

    @torch.no_grad()
    def _extract_patches(self, image_bgr: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
        tensor = self._preprocess(image_bgr)
        self._model(tensor)
        feat = self._features  # (1, C, H, W)
        _, c, h, w = feat.shape
        patches = feat.squeeze(0).permute(1, 2, 0).reshape(h * w, c).numpy()
        return patches, (h, w)

    def load(self, golden_images: list[np.ndarray]) -> None:
        if not golden_images:
            raise ValueError("PatchCoreDetector needs at least one golden (good) image")
        all_patches = []
        for img in golden_images:
            patches, hw = self._extract_patches(img)
            self._feature_grid_hw = hw
            all_patches.append(patches)
        bank = np.concatenate(all_patches, axis=0)

        if len(bank) > self.coreset_size:
            idx = self._rng.choice(len(bank), self.coreset_size, replace=False)
            bank = bank[idx]

        self._memory_bank = bank
        self._nn = NearestNeighbors(n_neighbors=min(self.k_neighbors, len(bank))).fit(bank)
        logger.info(
            "PatchCoreDetector loaded %d golden image(s) -> memory bank of %d patches",
            len(golden_images), len(bank),
        )

    def infer(self, image: np.ndarray) -> DetectionResult:
        if self._nn is None or self._feature_grid_hw is None:
            raise RuntimeError("load() must be called before infer()")

        patches, (h, w) = self._extract_patches(image)
        distances, _ = self._nn.kneighbors(patches)
        patch_scores = distances.mean(axis=1).reshape(h, w)

        overall_score = float(patch_scores.max())
        heat = cv2.resize(patch_scores.astype(np.float32), (image.shape[1], image.shape[0]))
        mask = (heat > self.anomaly_threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: list[DefectBox] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area >= self.min_blob_area:
                x, y, bw, bh = cv2.boundingRect(c)
                local_score = float(heat[y:y + bh, x:x + bw].max())
                boxes.append(DefectBox(x=x, y=y, w=bw, h=bh, score=local_score))

        heat_norm = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_norm, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(image, 0.6, heat_color, 0.4, 0)
        for b in boxes:
            cv2.rectangle(overlay, (b.x, b.y), (b.x + b.w, b.y + b.h), (0, 0, 255), 2)

        return DetectionResult(
            detector=self.name,
            pass_fail="fail" if overall_score >= self.anomaly_threshold else "pass",
            score=overall_score,
            threshold=self.anomaly_threshold,
            boxes=boxes,
            overlay_image_b64=encode_overlay(overlay),
        )
