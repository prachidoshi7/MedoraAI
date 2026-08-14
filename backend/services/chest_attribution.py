"""Class-targeted token attribution for the RAD-DINO chest classifier."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)

LUNG_FIELD_LABELS = frozenset({
    "Atelectasis",
    "Consolidation",
    "Edema",
    "Lung Lesion",
    "Lung Opacity",
    "Pneumonia",
    "Pneumothorax",
})


@dataclass(frozen=True)
class AttributionStats:
    shape: tuple[int, ...]
    min: float
    max: float
    mean: float
    has_nan: bool
    target_index: int


class ChestRadDinoAttribution:
    """Generate a class-specific heatmap from RAD-DINO patch-token gradients.

    The hook captures tokens entering the final transformer block. Gradients of
    the selected CheXpert logit weight those patch representations, yielding a
    37x37 class-targeted attribution map without materializing the model's very
    large all-layer attention matrices.
    """

    HEATMAP_SIZE = 512

    def __init__(self, classifier):
        self.classifier = classifier
        self.model = classifier.get_model()
        self.image_size = classifier.image_size
        self.patch_grid_size = classifier.patch_grid_size
        self.last_raw_stats: Optional[AttributionStats] = None
        self.last_mask_stats: dict[str, float | int | bool] = {}

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        values = np.nan_to_num(
            np.asarray(values, dtype=np.float32),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        values = np.maximum(values, 0.0)
        low = float(values.min())
        high = float(values.max())
        if high - low <= 1e-8:
            return np.zeros_like(values, dtype=np.float32)
        return ((values - low) / (high - low)).astype(np.float32)

    @classmethod
    def _smooth_cam(cls, values: np.ndarray) -> np.ndarray:
        values = cls._normalize(values)
        if not np.any(values):
            return values
        sigma = max(0.8, min(values.shape[:2]) / 45.0)
        return cls._normalize(
            cv2.GaussianBlur(values, (0, 0), sigmaX=sigma, sigmaY=sigma)
        )

    @staticmethod
    def should_apply_lung_mask(target_label: str) -> bool:
        """Only confine conditions whose evidence should lie in lung fields."""
        return target_label in LUNG_FIELD_LABELS

    @classmethod
    def _token_gradcam_pp(
        cls,
        activations: torch.Tensor,
        gradients: torch.Tensor,
    ) -> np.ndarray:
        """Compute positive class support across ViT patch tokens."""
        activations = torch.nan_to_num(activations.float())
        gradients = torch.nan_to_num(gradients.float())
        gradients_2 = gradients.pow(2)
        gradients_3 = gradients_2 * gradients
        denominator = 2.0 * gradients_2 + (
            activations * gradients_3
        ).sum(dim=0, keepdim=True)
        alpha = torch.where(
            denominator.abs() > 1e-8,
            gradients_2 / denominator,
            torch.zeros_like(gradients_2),
        )
        alpha = alpha / (alpha.sum(dim=0, keepdim=True) + 1e-8)
        channel_weights = (alpha * torch.relu(gradients)).sum(dim=0)
        attribution = torch.relu(
            (activations * channel_weights.unsqueeze(0)).sum(dim=-1)
        )

        if float(attribution.max().detach().cpu()) <= 1e-8:
            channel_weights = gradients.mean(dim=0)
            attribution = torch.relu(
                (activations * channel_weights.unsqueeze(0)).sum(dim=-1)
            )
        if float(attribution.max().detach().cpu()) <= 1e-8:
            attribution = torch.relu((activations * gradients).sum(dim=-1))
        return cls._normalize(attribution.detach().cpu().numpy())

    def _processor_crop(self, image: Image.Image, size: int) -> Image.Image:
        """Recreate HF shortest-edge resize plus square center crop."""
        rgb = image.convert("RGB")
        width, height = rgb.size
        if width <= 0 or height <= 0:
            raise ValueError("Cannot process an empty image.")

        if width < height:
            resized_width = self.image_size
            resized_height = int(round(height * self.image_size / width))
        else:
            resized_height = self.image_size
            resized_width = int(round(width * self.image_size / height))
        resized = rgb.resize((resized_width, resized_height), Image.Resampling.BICUBIC)
        left = max((resized_width - self.image_size) // 2, 0)
        top = max((resized_height - self.image_size) // 2, 0)
        crop = resized.crop((left, top, left + self.image_size, top + self.image_size))
        if size != self.image_size:
            crop = crop.resize((size, size), Image.Resampling.BILINEAR)
        return crop

    def create_lung_mask(self, image: Image.Image, output_shape: tuple[int, int]) -> np.ndarray:
        """Create a conservative coarse lung-field mask for display cleanup."""
        height, width = output_shape
        crop = self._processor_crop(image, max(width, height)).resize(
            (width, height), Image.Resampling.BILINEAR
        )
        gray = np.asarray(crop.convert("L"), dtype=np.uint8)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        body_threshold = max(8, int(np.quantile(blurred, 0.12)))
        body = (blurred > body_threshold).astype(np.uint8)
        body[: int(height * 0.04), :] = 0
        body[int(height * 0.96):, :] = 0
        body[:, : int(width * 0.03)] = 0
        body[:, int(width * 0.97):] = 0

        lung_threshold = int(np.quantile(blurred[body.astype(bool)], 0.48)) if body.any() else int(np.quantile(blurred, 0.48))
        candidate = ((blurred <= lung_threshold) & (body > 0)).astype(np.uint8)
        candidate[: int(height * 0.12), :] = 0
        candidate[int(height * 0.93):, :] = 0
        candidate[:, int(width * 0.46): int(width * 0.54)] = 0

        kernel_size = max(3, min(width, height) // 80)
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, kernel, iterations=2)

        selected = np.zeros_like(candidate)
        min_area = height * width * 0.015
        max_area = height * width * 0.38
        for side_start, side_end in ((0, width // 2), (width // 2, width)):
            side = candidate[:, side_start:side_end]
            contours, _ = cv2.findContours(side, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            plausible = []
            for contour in contours:
                _x, _y, box_width, box_height = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                aspect = box_height / max(float(box_width), 1.0)
                if min_area <= area <= max_area and 0.7 <= aspect <= 4.8 and box_height > height * 0.18:
                    plausible.append((area, contour))
            if plausible:
                contour = max(plausible, key=lambda item: item[0])[1].copy()
                contour[:, :, 0] += side_start
                cv2.drawContours(selected, [contour], -1, 1, thickness=cv2.FILLED)

        used_fallback = float(selected.mean()) < 0.08
        if used_fallback:
            selected = np.zeros_like(candidate)
            axes = (int(width * 0.19), int(height * 0.34))
            cv2.ellipse(selected, (int(width * 0.34), int(height * 0.52)), axes, -8, 0, 360, 1, cv2.FILLED)
            cv2.ellipse(selected, (int(width * 0.66), int(height * 0.52)), axes, 8, 0, 360, 1, cv2.FILLED)
            selected = (selected & body).astype(np.uint8) if body.any() else selected

        selected = cv2.GaussianBlur(selected.astype(np.float32), (9, 9), 0)
        selected = np.clip(selected, 0.0, 1.0)
        self.last_mask_stats = {
            "shape_h": height,
            "shape_w": width,
            "coverage": float(selected.mean()),
            "used_fallback": used_fallback,
        }
        return selected

    def create_chest_field_mask(
        self,
        image: Image.Image,
        output_shape: tuple[int, int],
    ) -> np.ndarray:
        """Retain the full radiograph for cardiac, pleural, bone, and device labels."""
        height, width = output_shape
        crop = self._processor_crop(image, max(width, height)).resize(
            (width, height), Image.Resampling.BILINEAR
        )
        gray = np.asarray(crop.convert("L"), dtype=np.uint8)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        positive = blurred[blurred > 2]
        threshold = max(
            4.0,
            float(np.percentile(positive, 3)) if positive.size else 4.0,
        )
        mask = (blurred > threshold).astype(np.uint8) * 255
        kernel_size = max(3, int(round(min(height, width) * 0.04)) | 1)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        selected = np.zeros_like(mask)
        if contours:
            cv2.drawContours(
                selected,
                [max(contours, key=cv2.contourArea)],
                -1,
                255,
                thickness=cv2.FILLED,
            )
        coverage = float(np.count_nonzero(selected)) / float(height * width)
        used_fallback = coverage < 0.35 or coverage > 0.99
        if used_fallback:
            selected[:] = 255
        selected = cv2.GaussianBlur(
            selected.astype(np.float32) / 255.0, (0, 0), max(0.8, width / 120.0)
        )
        self.last_mask_stats = {
            "shape_h": height,
            "shape_w": width,
            "coverage": float(selected.mean()),
            "used_fallback": used_fallback,
            "mask_type": "full_chest_field",
        }
        return np.clip(selected, 0.0, 1.0)

    def generate_heatmap_and_raw(
        self,
        image: Image.Image,
        input_tensor: torch.Tensor,
        target_class_idx: int,
        *,
        target_label: str = "",
        apply_lung_mask: Optional[bool] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the 512px overlay and the underlying normalized patch map."""
        captured: dict[str, torch.Tensor] = {}

        def capture_final_block_input(_module, inputs):
            # Attribution targets the final block input. Detaching here avoids
            # retaining backward graphs for the preceding eleven ViT blocks.
            hidden_state = inputs[0].detach().requires_grad_(True)
            captured["tokens"] = hidden_state
            return (hidden_state, *inputs[1:])

        layer = self.model.dinov2.encoder.layer[-1]
        handle = layer.register_forward_pre_hook(capture_final_block_input)
        pixels = input_tensor.detach()

        try:
            with self.classifier.inference_lock, torch.enable_grad():
                logits = self.model(pixels)
                if not 0 <= target_class_idx < logits.shape[-1]:
                    raise ValueError(f"Invalid CheXpert attribution target: {target_class_idx}")
                logits[0, target_class_idx].backward()
                tokens = captured.get("tokens")
                if tokens is None or tokens.grad is None:
                    raise RuntimeError("Could not capture RAD-DINO patch-token gradients.")
                patch_count = self.patch_grid_size ** 2
                activations = tokens[0, -patch_count:, :].detach()
                gradients = tokens.grad[0, -patch_count:, :].detach()
                raw = self._token_gradcam_pp(activations, gradients).reshape(
                    self.patch_grid_size, self.patch_grid_size
                )
        finally:
            handle.remove()
            self.model.zero_grad(set_to_none=True)

        raw = self._smooth_cam(raw)
        use_lung_mask = (
            self.should_apply_lung_mask(target_label)
            if apply_lung_mask is None
            else apply_lung_mask
        )
        anatomy_mask = (
            self.create_lung_mask(image, raw.shape)
            if use_lung_mask
            else self.create_chest_field_mask(image, raw.shape)
        )
        self.last_mask_stats["target_label"] = target_label
        self.last_mask_stats["mask_type"] = (
            "lung_fields" if use_lung_mask else "full_chest_field"
        )
        raw = self._smooth_cam(raw * anatomy_mask)
        self.last_raw_stats = AttributionStats(
            shape=tuple(raw.shape),
            min=float(raw.min()),
            max=float(raw.max()),
            mean=float(raw.mean()),
            has_nan=bool(np.isnan(raw).any()),
            target_index=target_class_idx,
        )

        display_map = cv2.resize(
            raw,
            (self.HEATMAP_SIZE, self.HEATMAP_SIZE),
            interpolation=cv2.INTER_CUBIC,
        )
        display_map = self._smooth_cam(display_map)
        display_image = np.asarray(
            self._processor_crop(image, self.HEATMAP_SIZE), dtype=np.uint8
        )
        if np.any(display_map):
            heatmap = cv2.applyColorMap(
                np.uint8(display_map * 255), cv2.COLORMAP_JET
            )
            heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
            overlay = np.clip(
                0.62 * display_image + 0.38 * heatmap, 0, 255
            ).astype(np.uint8)
        else:
            overlay = display_image
        logger.info(
            "RAD-DINO token attribution generated for %s (target=%s, map=%s, mean=%.4f).",
            target_label or "selected finding",
            target_class_idx,
            raw.shape,
            self.last_raw_stats.mean,
        )
        return overlay, raw

    def heatmap_to_bboxes(
        self,
        attribution: np.ndarray,
        threshold: float = 0.55,
        *,
        label: str = "model_attribution_region",
    ) -> list[dict]:
        """Extract display-coordinate regions from a normalized token map."""
        cam = cv2.resize(
            self._normalize(attribution),
            (self.HEATMAP_SIZE, self.HEATMAP_SIZE),
            interpolation=cv2.INTER_CUBIC,
        )
        if not np.any(cam):
            return []
        effective_threshold = max(
            threshold,
            float(np.quantile(cam[cam > 0], 0.85)),
        )
        binary = (cam > effective_threshold).astype(np.uint8) * 255
        kernel = np.ones((5, 5), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        image_area = self.HEATMAP_SIZE ** 2
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            area = width * height
            if image_area * 0.005 <= area <= image_area * 0.50:
                boxes.append({
                    "x1": int(x),
                    "y1": int(y),
                    "x2": int(x + width),
                    "y2": int(y + height),
                    "label": label,
                    "confidence": round(float(cam[y:y + height, x:x + width].max()), 4),
                })
        return sorted(boxes, key=lambda box: box["confidence"], reverse=True)[:5]
