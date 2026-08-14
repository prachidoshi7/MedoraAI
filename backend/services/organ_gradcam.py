"""Stable class-targeted Grad-CAM++ for compact grayscale organ models.

The lung and kidney classifiers resize their input directly to a square. This
module computes attribution in classifier space, projects it back to the source
image, removes obvious scanner/background pixels, and only then creates the
512 px report overlay and regions.
"""

from __future__ import annotations

import threading
from typing import Iterable

import cv2
import numpy as np
import torch
from PIL import Image


class GrayscaleOrganGradCAM:
    """Multi-layer Grad-CAM++ with a standard Grad-CAM fallback."""

    HEATMAP_SIZE = 512

    def __init__(
        self,
        classifier,
        target_layers: torch.nn.Module | Iterable[torch.nn.Module],
        input_size: int,
        *,
        layer_weights: Iterable[float] | None = None,
        anatomy_mode: str = "visible_field",
        region_label: str = "model_attribution_region",
    ) -> None:
        self.classifier = classifier
        self.model = classifier.get_model()
        self.input_size = int(input_size)
        self.target_layers = (
            list(target_layers)
            if isinstance(target_layers, (list, tuple))
            else [target_layers]
        )
        if not self.target_layers:
            raise ValueError("At least one target layer is required")

        weights = list(layer_weights or [1.0] * len(self.target_layers))
        if len(weights) != len(self.target_layers) or any(weight < 0 for weight in weights):
            raise ValueError("layer_weights must match target_layers and be non-negative")
        if not any(weights):
            raise ValueError("At least one layer weight must be positive")
        total = float(sum(weights))
        self.layer_weights = [float(weight) / total for weight in weights]

        self.anatomy_mode = anatomy_mode
        self.region_label = region_label
        self.inference_lock = getattr(classifier, "inference_lock", threading.RLock())
        self.last_stats: dict[str, float | int | str] = {}

    @staticmethod
    def _normalize(cam: np.ndarray) -> np.ndarray:
        cam = np.nan_to_num(
            np.asarray(cam, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0
        )
        cam = np.maximum(cam, 0.0)
        maximum = float(cam.max()) if cam.size else 0.0
        minimum = float(cam.min()) if cam.size else 0.0
        if maximum - minimum <= 1e-8:
            return np.zeros_like(cam, dtype=np.float32)
        return ((cam - minimum) / (maximum - minimum)).astype(np.float32)

    @classmethod
    def _smooth_cam(cls, cam: np.ndarray) -> np.ndarray:
        normalized = cls._normalize(cam)
        if not np.any(normalized):
            return normalized
        height, width = normalized.shape[:2]
        sigma = max(0.8, min(height, width) / 90.0)
        return cls._normalize(
            cv2.GaussianBlur(normalized, (0, 0), sigmaX=sigma, sigmaY=sigma)
        )

    @classmethod
    def _gradcam_pp(cls, activation: torch.Tensor, gradient: torch.Tensor) -> np.ndarray:
        """Return a positive-support Grad-CAM++ map for one convolutional layer."""

        activation = torch.nan_to_num(activation.float())
        gradient = torch.nan_to_num(gradient.float())
        gradient_2 = gradient.pow(2)
        gradient_3 = gradient_2 * gradient
        denominator = 2.0 * gradient_2 + (
            activation * gradient_3
        ).sum(dim=(1, 2), keepdim=True)
        alpha = torch.where(
            denominator.abs() > 1e-8,
            gradient_2 / denominator,
            torch.zeros_like(gradient_2),
        )
        alpha = alpha / (alpha.sum(dim=(1, 2), keepdim=True) + 1e-8)
        weights = (alpha * torch.relu(gradient)).sum(dim=(1, 2))
        cam = torch.relu((weights[:, None, None] * activation).sum(dim=0))

        # Saturated compact CNNs can occasionally have no positive gradient at
        # the deepest layer. A standard Grad-CAM weighting is a stable fallback.
        if float(cam.max().detach().cpu()) <= 1e-8:
            standard_weights = gradient.mean(dim=(1, 2))
            cam = torch.relu(
                (standard_weights[:, None, None] * activation).sum(dim=0)
            )

        return cls._normalize(cam.detach().cpu().numpy())

    def _compute_classifier_cam(
        self, input_tensor: torch.Tensor, target_idx: int
    ) -> np.ndarray:
        captured: list[torch.Tensor | None] = [None] * len(self.target_layers)
        handles = []

        def capture(index: int):
            def hook(_module, _inputs, output):
                if not isinstance(output, torch.Tensor):
                    raise TypeError("Grad-CAM target layer must return a tensor")
                output.retain_grad()
                captured[index] = output

            return hook

        for index, layer in enumerate(self.target_layers):
            handles.append(layer.register_forward_hook(capture(index)))

        try:
            with self.inference_lock, torch.enable_grad():
                self.model.eval()
                self.model.zero_grad(set_to_none=True)
                grad_input = input_tensor.detach().clone().requires_grad_(True)
                logits = self.model(grad_input)
                if logits.ndim != 2 or logits.shape[0] != 1:
                    raise ValueError(
                        f"Expected logits shaped [1, classes], got {tuple(logits.shape)}"
                    )
                if target_idx < 0 or target_idx >= int(logits.shape[1]):
                    raise ValueError(
                        f"Target class {target_idx} is outside classifier output "
                        f"0..{logits.shape[1] - 1}"
                    )
                logits[0, target_idx].backward()

                maps: list[tuple[np.ndarray, float]] = []
                for output, layer_weight in zip(captured, self.layer_weights):
                    if output is None or output.grad is None or output.ndim != 4:
                        continue
                    layer_cam = self._gradcam_pp(output[0], output.grad[0])
                    if not np.any(layer_cam):
                        continue
                    resized = cv2.resize(
                        layer_cam,
                        (self.input_size, self.input_size),
                        interpolation=cv2.INTER_CUBIC,
                    )
                    maps.append((self._normalize(resized), layer_weight))
        finally:
            for handle in handles:
                handle.remove()
            self.model.zero_grad(set_to_none=True)

        if not maps:
            return np.zeros(
                (self.input_size, self.input_size), dtype=np.float32
            )
        available_weight = sum(weight for _, weight in maps)
        combined = sum(cam * (weight / available_weight) for cam, weight in maps)
        return self._smooth_cam(combined)

    @staticmethod
    def _largest_foreground_mask(
        gray: np.ndarray, *, min_coverage: float
    ) -> np.ndarray:
        """Conservatively remove black borders, scanner furniture, and text."""

        height, width = gray.shape
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        otsu_threshold, _ = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        positive = gray[gray > 2]
        low_content = float(np.percentile(positive, 8)) if positive.size else 5.0
        threshold = max(4.0, min(float(otsu_threshold) * 0.45, low_content))
        mask = (blurred > threshold).astype(np.uint8) * 255

        kernel_size = max(3, int(round(min(height, width) * 0.025)) | 1)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return np.ones_like(gray, dtype=np.float32)

        output = np.zeros_like(mask)
        image_area = float(height * width)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            if cv2.contourArea(contour) >= image_area * 0.015:
                cv2.drawContours(output, [contour], -1, 255, thickness=cv2.FILLED)

        coverage = float(np.count_nonzero(output)) / image_area
        if coverage < min_coverage or coverage > 0.985:
            return np.ones_like(gray, dtype=np.float32)
        output = cv2.dilate(output, kernel, iterations=1)
        sigma = max(1.0, min(height, width) / 100.0)
        return cv2.GaussianBlur(
            output.astype(np.float32) / 255.0, (0, 0), sigma
        )

    def _create_anatomy_mask(
        self, image: Image.Image, shape: tuple[int, int]
    ) -> np.ndarray:
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        if gray.shape != shape:
            gray = cv2.resize(
                gray, (shape[1], shape[0]), interpolation=cv2.INTER_AREA
            )
        min_coverage = 0.08 if self.anatomy_mode == "lung_ct" else 0.12
        return self._largest_foreground_mask(gray, min_coverage=min_coverage)

    def _project_to_source(
        self, image: Image.Image, classifier_cam: np.ndarray
    ) -> np.ndarray:
        width, height = image.size
        projected = cv2.resize(
            classifier_cam, (width, height), interpolation=cv2.INTER_CUBIC
        )
        anatomy_mask = self._create_anatomy_mask(image, (height, width))
        if anatomy_mask.shape == projected.shape:
            projected = projected * anatomy_mask
        return self._smooth_cam(projected)

    @staticmethod
    def _overlay(image_rgb: np.ndarray, cam: np.ndarray) -> np.ndarray:
        heatmap = cv2.applyColorMap(
            np.uint8(np.clip(cam, 0.0, 1.0) * 255), cv2.COLORMAP_JET
        )
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        return np.clip(0.62 * image_rgb + 0.38 * heatmap, 0, 255).astype(
            np.uint8
        )

    def _blank_result(self, image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
        display = np.asarray(
            image.convert("RGB").resize(
                (self.HEATMAP_SIZE, self.HEATMAP_SIZE), Image.Resampling.LANCZOS
            ),
            dtype=np.uint8,
        )
        return display, np.zeros(
            (self.HEATMAP_SIZE, self.HEATMAP_SIZE), dtype=np.float32
        )

    def generate_heatmap_and_raw(
        self,
        image: Image.Image,
        target_idx: int,
        *,
        target_label: str | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.model is None:
            self.last_stats = {
                "status": "model_unavailable",
                "target_idx": int(target_idx),
            }
            return self._blank_result(image)

        input_tensor = self.classifier.preprocess(image)
        classifier_cam = self._compute_classifier_cam(input_tensor, int(target_idx))
        source_cam = self._project_to_source(image, classifier_cam)
        display_cam = cv2.resize(
            source_cam,
            (self.HEATMAP_SIZE, self.HEATMAP_SIZE),
            interpolation=cv2.INTER_CUBIC,
        )
        display_cam = self._smooth_cam(display_cam)
        display_image = np.asarray(
            image.convert("RGB").resize(
                (self.HEATMAP_SIZE, self.HEATMAP_SIZE), Image.Resampling.LANCZOS
            ),
            dtype=np.uint8,
        )
        overlay = (
            self._overlay(display_image, display_cam)
            if np.any(display_cam)
            else display_image
        )
        self.last_stats = {
            "status": "ok" if np.any(display_cam) else "empty_attribution",
            "target_idx": int(target_idx),
            "target_label": target_label or "",
            "active_fraction": float(
                np.count_nonzero(display_cam > 0.1) / display_cam.size
            ),
            "peak": float(display_cam.max()),
        }
        return overlay, display_cam

    def heatmap_to_bboxes(
        self,
        cam: np.ndarray,
        threshold: float = 0.55,
        *,
        label: str | None = None,
    ) -> list[dict]:
        cam = self._normalize(cam)
        if not np.any(cam):
            return []
        if cam.shape != (self.HEATMAP_SIZE, self.HEATMAP_SIZE):
            cam = cv2.resize(
                cam,
                (self.HEATMAP_SIZE, self.HEATMAP_SIZE),
                interpolation=cv2.INTER_CUBIC,
            )
            cam = self._normalize(cam)

        positive = cam[cam > 0]
        dynamic_threshold = max(
            float(threshold), float(np.quantile(positive, 0.85))
        )
        binary = (cam >= dynamic_threshold).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        boxes: list[dict] = []
        image_area = float(self.HEATMAP_SIZE * self.HEATMAP_SIZE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            area = float(cv2.contourArea(contour))
            if area < image_area * 0.003 or area > image_area * 0.55:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            region = cam[y : y + height, x : x + width]
            confidence = float(region.max()) if region.size else 0.0
            boxes.append(
                {
                    "x1": int(x),
                    "y1": int(y),
                    "x2": int(x + width),
                    "y2": int(y + height),
                    "label": label or self.region_label,
                    "confidence": round(confidence, 4),
                }
            )
            if len(boxes) >= 4:
                break
        return boxes

    def generate(
        self,
        image: Image.Image,
        target_idx: int,
        target_label: str | None = None,
    ) -> tuple[np.ndarray, list[dict]]:
        overlay, raw_cam = self.generate_heatmap_and_raw(
            image, target_idx, target_label=target_label
        )
        return overlay, self.heatmap_to_bboxes(raw_cam, label=target_label)
