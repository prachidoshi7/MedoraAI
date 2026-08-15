"""Chest X-ray heatmap behavior ported from the madora reference."""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from pytorch_grad_cam.utils.image import show_cam_on_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CamStats:
    shape: tuple[int, ...]
    min: float
    max: float
    mean: float
    has_nan: bool
    feature_shape: Optional[tuple[int, ...]] = None


class ChestGradCAM:
    """Reference RAD-DINO chest heatmap and lung-mask implementation."""

    HEATMAP_SIZE = 518
    PREPROCESS_RESIZE = 518
    PREPROCESS_CROP = 518

    def __init__(self, classifier):
        model = classifier.get_model() if hasattr(classifier, "get_model") else None
        self._classifier = classifier
        self._model = model if isinstance(model, nn.Module) else None
        self.target_layer_name = None
        self.target_layer = None
        self.target_layers = []
        self.cam = None
        self.last_raw_stats: Optional[CamStats] = None
        self.last_mask_stats: dict[str, float | int | bool] = {}
        input_size = getattr(classifier, "input_size", 518)
        self.HEATMAP_SIZE = input_size
        self.PREPROCESS_RESIZE = input_size
        self.PREPROCESS_CROP = input_size
        if self._model is not None and hasattr(self._model, "backbone"):
            logger.info("ChestGradCAM configured for RAD-DINO Vision Transformer backbone.")

    def _classifier_crop(self, image: Image.Image, size: int) -> tuple[Image.Image, dict[str, int]]:
        rgb = image.convert("RGB")
        width, height = rgb.size
        if width <= 0 or height <= 0:
            raise ValueError("Cannot process an empty image.")
        if width < height:
            resized_width = self.PREPROCESS_RESIZE
            resized_height = int(round(height * self.PREPROCESS_RESIZE / width))
        else:
            resized_height = self.PREPROCESS_RESIZE
            resized_width = int(round(width * self.PREPROCESS_RESIZE / height))
        resized = rgb.resize((resized_width, resized_height), Image.Resampling.BILINEAR)
        left = max((resized_width - self.PREPROCESS_CROP) // 2, 0)
        top = max((resized_height - self.PREPROCESS_CROP) // 2, 0)
        crop = resized.crop((left, top, left + self.PREPROCESS_CROP, top + self.PREPROCESS_CROP))
        if size != self.PREPROCESS_CROP:
            crop = crop.resize((size, size), Image.Resampling.BILINEAR)
        return crop, {
            "original_width": width, "original_height": height,
            "resized_width": resized_width, "resized_height": resized_height,
            "crop_left": left, "crop_top": top,
            "crop_size": self.PREPROCESS_CROP, "output_size": size,
        }

    @staticmethod
    def _stats(cam: np.ndarray, feature_shape=None) -> CamStats:
        return CamStats(
            shape=tuple(int(value) for value in cam.shape),
            min=float(np.nanmin(cam)) if cam.size else float("nan"),
            max=float(np.nanmax(cam)) if cam.size else float("nan"),
            mean=float(np.nanmean(cam)) if cam.size else float("nan"),
            has_nan=bool(np.isnan(cam).any()),
            feature_shape=feature_shape,
        )

    @staticmethod
    def _normalize_cam(cam: np.ndarray) -> np.ndarray:
        cam = np.nan_to_num(cam, nan=0.0, posinf=0.0, neginf=0.0)
        low, high = float(cam.min()), float(cam.max())
        if high - low <= 1e-8:
            return np.zeros_like(cam, dtype=np.float32)
        return ((cam - low) / (high - low)).astype(np.float32)

    def create_lung_mask(self, image: Image.Image, output_shape: tuple[int, int]) -> np.ndarray:
        height, width = output_shape
        crop, _ = self._classifier_crop(image, max(width, height))
        gray = np.asarray(crop.resize((width, height), Image.Resampling.BILINEAR).convert("L"), dtype=np.uint8)
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
        kernel = np.ones((max(3, width // 80), max(3, height // 80)), np.uint8)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, kernel, iterations=2)
        selected = np.zeros_like(candidate)
        min_area, max_area = height * width * 0.015, height * width * 0.38
        for side_start, side_end in ((0, width // 2), (width // 2, width)):
            contours, _ = cv2.findContours(candidate[:, side_start:side_end], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            plausible = []
            for contour in contours:
                _x, _y, box_width, box_height = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                aspect = box_height / max(float(box_width), 1.0)
                if min_area <= area <= max_area and 0.7 <= aspect <= 4.8 and box_height > height * 0.18:
                    plausible.append((area, contour))
            if plausible:
                shifted = max(plausible, key=lambda item: item[0])[1].copy()
                shifted[:, :, 0] += side_start
                cv2.drawContours(selected, [shifted], -1, 1, thickness=cv2.FILLED)
        used_fallback = float(selected.mean()) < 0.08
        if used_fallback:
            selected = np.zeros_like(candidate)
            axes = (int(width * 0.19), int(height * 0.34))
            cv2.ellipse(selected, (int(width * 0.34), int(height * 0.52)), axes, -8, 0, 360, 1, cv2.FILLED)
            cv2.ellipse(selected, (int(width * 0.66), int(height * 0.52)), axes, 8, 0, 360, 1, cv2.FILLED)
            selected = (selected & body).astype(np.uint8) if body.any() else selected
        selected = cv2.morphologyEx(selected, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        selected = cv2.GaussianBlur(selected.astype(np.float32), (9, 9), 0)
        selected = np.clip(selected, 0.0, 1.0)
        self.last_mask_stats = {
            "shape_h": int(height), "shape_w": int(width),
            "coverage": float(selected.mean()), "used_fallback": used_fallback,
        }
        return selected.astype(np.float32)

    def _compute_cam(self, input_tensor, target_class_idx: int, image: Optional[Image.Image] = None) -> np.ndarray:
        # This is the reference RAD-DINO path: its generic GradCAM object has no
        # convolutional target layer, so it uses the same anatomical saliency map.
        size = self.PREPROCESS_CROP
        if image is not None:
            crop, _ = self._classifier_crop(image, size)
            gray = np.asarray(crop.convert("L"), dtype=np.float32) / 255.0
            sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            cam = cv2.GaussianBlur(np.sqrt(sobel_x ** 2 + sobel_y ** 2), (15, 15), 0)
        else:
            cam = np.zeros((size, size), dtype=np.float32)
            cam[size // 4:size * 3 // 4, size // 4:size * 3 // 4] = 1.0
        self.last_raw_stats = self._stats(cam, (size, size))
        return self._normalize_cam(cam)

    def generate_heatmap(self, image, input_tensor, target_class_idx, target_label="", *, apply_lung_mask=True, **_kwargs):
        grayscale_cam = self._compute_cam(input_tensor, target_class_idx, image=image)
        if apply_lung_mask:
            grayscale_cam = self._normalize_cam(grayscale_cam * self.create_lung_mask(image, grayscale_cam.shape))
        size = self.HEATMAP_SIZE
        grayscale_cam = np.clip(cv2.resize(grayscale_cam, (size, size), interpolation=cv2.INTER_LINEAR), 0.0, 1.0)
        crop, geometry = self._classifier_crop(image, size)
        visualization = show_cam_on_image(np.asarray(crop, dtype=np.float32) / 255.0, grayscale_cam, use_rgb=True)
        logger.info("Chest heatmap generated for %s; geometry=%s", target_label, geometry)
        return visualization

    def generate_raw_cam(self, input_tensor, target_class_idx, image=None, *, apply_lung_mask=True, **_kwargs):
        cam = self._compute_cam(input_tensor, target_class_idx, image=image)
        if apply_lung_mask and image is not None:
            cam = self._normalize_cam(cam * self.create_lung_mask(image, cam.shape))
        return cam

    @staticmethod
    def heatmap_to_bboxes(cam: np.ndarray, threshold: float = 0.5) -> list[dict]:
        effective_threshold = max(threshold, float(np.quantile(cam, 0.85)))
        binary = (cam > effective_threshold).astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        image_area = cam.shape[0] * cam.shape[1]
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            area = width * height
            if max(20, image_area * 0.005) <= area <= image_area * 0.50:
                boxes.append({
                    "x1": int(x), "y1": int(y), "x2": int(x + width), "y2": int(y + height),
                    "label": "anomaly_region",
                    "confidence": round(float(cam[y:y + height, x:x + width].max()), 4),
                })
        return sorted(boxes, key=lambda box: box["confidence"], reverse=True)[:5]
