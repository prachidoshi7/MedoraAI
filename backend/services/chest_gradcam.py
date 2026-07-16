"""
MedoraAI chest X-ray explainability.

Production Grad-CAM defaults to the final EfficientNet convolutional layer
(`conv_head`) and targets one raw class logit. The generated overlay is aligned
to the same resize + center-crop geometry used by the classifier.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from pytorch_grad_cam import EigenCAM, GradCAM, GradCAMPlusPlus
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CamStats:
    """Diagnostics for a raw CAM array before colorization."""

    shape: tuple[int, ...]
    min: float
    max: float
    mean: float
    has_nan: bool
    feature_shape: Optional[tuple[int, ...]] = None


class ChestGradCAM:
    """Grad-CAM explainability for the chest X-ray EfficientNet-B4 classifier."""

    HEATMAP_SIZE = 512
    PREPROCESS_RESIZE = 256
    PREPROCESS_CROP = 224

    def __init__(self, classifier):
        model = classifier.get_model()
        self._model = model
        self.target_layer_name, self.target_layer = self._find_last_conv_before_pool(model)
        self.target_layers = [self.target_layer]
        self.cam = GradCAM(model=model, target_layers=self.target_layers)
        self.last_raw_stats: Optional[CamStats] = None
        self.last_mask_stats: dict[str, float | int | bool] = {}

        logger.info(
            "ChestGradCAM targeting %s (%s), the final convolution before global pooling.",
            self.target_layer_name,
            self.target_layer.__class__.__name__,
        )

    @staticmethod
    def _module_name(model: nn.Module, target: nn.Module) -> str:
        for name, module in model.named_modules():
            if module is target:
                return name or "<root>"
        return "<unnamed>"

    def _find_last_conv_before_pool(self, model: nn.Module) -> tuple[str, nn.Module]:
        """Prefer EfficientNet conv_head; otherwise use the last Conv2d before pooling."""
        if hasattr(model, "conv_head") and isinstance(model.conv_head, nn.Conv2d):
            return "conv_head", model.conv_head

        last_conv_name = ""
        last_conv: Optional[nn.Module] = None
        for name, module in model.named_modules():
            if isinstance(module, nn.Conv2d):
                last_conv_name = name
                last_conv = module
        if last_conv is None:
            raise RuntimeError("Could not find a Conv2d layer for chest Grad-CAM.")
        return last_conv_name, last_conv

    def _build_cam(self, method: str, target_layers: Optional[list[nn.Module]] = None):
        layers = target_layers or self.target_layers
        method_key = method.lower().replace("_", "").replace("-", "").replace("+", "plus")
        if method_key == "gradcam":
            return GradCAM(model=self._model, target_layers=layers)
        if method_key in {"gradcamplusplus", "gradcampp"}:
            return GradCAMPlusPlus(model=self._model, target_layers=layers)
        if method_key == "eigencam":
            return EigenCAM(model=self._model, target_layers=layers)
        raise ValueError(f"Unsupported CAM method: {method}")

    def _classifier_crop(self, image: Image.Image, size: int) -> tuple[Image.Image, dict[str, int]]:
        """
        Recreate torchvision Resize(256) + CenterCrop(224), then resize to `size`.
        This keeps the CAM and displayed X-ray in the same coordinate frame.
        """
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
        crop = resized.crop((
            left,
            top,
            left + self.PREPROCESS_CROP,
            top + self.PREPROCESS_CROP,
        ))
        if size != self.PREPROCESS_CROP:
            crop = crop.resize((size, size), Image.Resampling.BILINEAR)

        return crop, {
            "original_width": width,
            "original_height": height,
            "resized_width": resized_width,
            "resized_height": resized_height,
            "crop_left": left,
            "crop_top": top,
            "crop_size": self.PREPROCESS_CROP,
            "output_size": size,
        }

    @staticmethod
    def _stats(cam: np.ndarray, feature_shape: Optional[tuple[int, ...]] = None) -> CamStats:
        return CamStats(
            shape=tuple(int(v) for v in cam.shape),
            min=float(np.nanmin(cam)) if cam.size else float("nan"),
            max=float(np.nanmax(cam)) if cam.size else float("nan"),
            mean=float(np.nanmean(cam)) if cam.size else float("nan"),
            has_nan=bool(np.isnan(cam).any()),
            feature_shape=feature_shape,
        )

    @staticmethod
    def _normalize_cam(cam: np.ndarray) -> np.ndarray:
        cam = np.nan_to_num(cam, nan=0.0, posinf=0.0, neginf=0.0)
        cam_min = float(cam.min())
        cam_max = float(cam.max())
        if cam_max - cam_min <= 1e-8:
            return np.zeros_like(cam, dtype=np.float32)
        return ((cam - cam_min) / (cam_max - cam_min)).astype(np.float32)

    def create_lung_mask(
        self,
        image: Image.Image,
        output_shape: tuple[int, int],
    ) -> np.ndarray:
        """
        Segment a coarse lung field mask using thresholding and contour cleanup.
        This is intentionally conservative and falls back to anatomical ellipses
        if contour detection does not find two plausible lung regions.
        """
        height, width = output_shape
        crop, _ = self._classifier_crop(image, max(width, height))
        crop = crop.resize((width, height), Image.Resampling.BILINEAR)
        gray = np.asarray(crop.convert("L"), dtype=np.uint8)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)

        body_threshold = max(8, int(np.quantile(blurred, 0.12)))
        body = (blurred > body_threshold).astype(np.uint8)
        body[: int(height * 0.04), :] = 0
        body[int(height * 0.96) :, :] = 0
        body[:, : int(width * 0.03)] = 0
        body[:, int(width * 0.97) :] = 0

        if body.any():
            lung_threshold = int(np.quantile(blurred[body.astype(bool)], 0.48))
        else:
            lung_threshold = int(np.quantile(blurred, 0.48))

        candidate = ((blurred <= lung_threshold) & (body > 0)).astype(np.uint8)
        candidate[: int(height * 0.12), :] = 0
        candidate[int(height * 0.93) :, :] = 0
        candidate[:, int(width * 0.46) : int(width * 0.54)] = 0

        kernel = np.ones((max(3, width // 80), max(3, height // 80)), np.uint8)
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
                x, y, w, h = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                aspect = h / max(float(w), 1.0)
                if min_area <= area <= max_area and 0.7 <= aspect <= 4.8 and h > height * 0.18:
                    plausible.append((area, contour))
            if plausible:
                contour = max(plausible, key=lambda item: item[0])[1]
                shifted = contour.copy()
                shifted[:, :, 0] += side_start
                cv2.drawContours(selected, [shifted], -1, 1, thickness=cv2.FILLED)

        used_fallback = False
        if float(selected.mean()) < 0.08:
            used_fallback = True
            selected = np.zeros_like(candidate)
            left_center = (int(width * 0.34), int(height * 0.52))
            right_center = (int(width * 0.66), int(height * 0.52))
            axes = (int(width * 0.19), int(height * 0.34))
            cv2.ellipse(selected, left_center, axes, -8, 0, 360, 1, thickness=cv2.FILLED)
            cv2.ellipse(selected, right_center, axes, 8, 0, 360, 1, thickness=cv2.FILLED)
            selected = (selected & body).astype(np.uint8) if body.any() else selected

        selected = cv2.morphologyEx(selected, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        selected = cv2.GaussianBlur(selected.astype(np.float32), (9, 9), 0)
        selected = np.clip(selected, 0.0, 1.0)

        self.last_mask_stats = {
            "shape_h": int(height),
            "shape_w": int(width),
            "coverage": float(selected.mean()),
            "used_fallback": used_fallback,
        }
        logger.info(
            "Lung mask generated: shape=%sx%s coverage=%.3f fallback=%s",
            height,
            width,
            self.last_mask_stats["coverage"],
            used_fallback,
        )
        return selected.astype(np.float32)

    def _compute_cam(
        self,
        input_tensor: torch.Tensor,
        target_class_idx: int,
        method: str = "gradcam",
        target_layers: Optional[list[nn.Module]] = None,
    ) -> np.ndarray:
        feature_shape: Optional[tuple[int, ...]] = None
        layers = target_layers or self.target_layers

        def capture_shape(_module, _inputs, output):
            nonlocal feature_shape
            if isinstance(output, torch.Tensor):
                feature_shape = tuple(int(v) for v in output.shape)

        handle = layers[0].register_forward_hook(capture_shape)
        try:
            method_key = method.lower().replace("_", "").replace("-", "").replace("+", "plus")
            cam_runner = self.cam if method_key == "gradcam" and layers == self.target_layers else self._build_cam(method, layers)
            targets = [ClassifierOutputTarget(target_class_idx)]
            grayscale_cam = cam_runner(input_tensor=input_tensor, targets=targets)
            cam = grayscale_cam[0, :].astype(np.float32)
        finally:
            handle.remove()

        self.last_raw_stats = self._stats(cam, feature_shape)
        logger.info(
            "Raw %s stats before colorization: cam_shape=%s feature_shape=%s min=%.6f max=%.6f mean=%.6f has_nan=%s target_idx=%s",
            method,
            self.last_raw_stats.shape,
            self.last_raw_stats.feature_shape,
            self.last_raw_stats.min,
            self.last_raw_stats.max,
            self.last_raw_stats.mean,
            self.last_raw_stats.has_nan,
            target_class_idx,
        )
        return self._normalize_cam(cam)

    def generate_heatmap(
        self,
        image: Image.Image,
        input_tensor: torch.Tensor,
        target_class_idx: int,
        target_label: str = "",
        *,
        apply_lung_mask: bool = True,
        method: str = "gradcam",
        target_layers: Optional[list[nn.Module]] = None,
    ) -> np.ndarray:
        """
        Generate a heatmap overlay for one raw class logit.

        Returns an RGB uint8 array in the classifier crop coordinate frame.
        """
        grayscale_cam = self._compute_cam(
            input_tensor=input_tensor,
            target_class_idx=target_class_idx,
            method=method,
            target_layers=target_layers,
        )

        if apply_lung_mask:
            mask = self.create_lung_mask(image, grayscale_cam.shape)
            grayscale_cam = self._normalize_cam(grayscale_cam * mask)

        sz = self.HEATMAP_SIZE
        grayscale_cam = cv2.resize(
            grayscale_cam,
            (sz, sz),
            interpolation=cv2.INTER_LINEAR,
        )
        grayscale_cam = np.clip(grayscale_cam, 0.0, 1.0)

        crop, geometry = self._classifier_crop(image, sz)
        rgb_img = np.asarray(crop, dtype=np.float32) / 255.0
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)

        if target_label:
            logger.info(
                "%s generated for %s using %s; resize/crop geometry=%s",
                method,
                target_label,
                self.target_layer_name if target_layers is None else "custom target layer",
                geometry,
            )

        return visualization

    def generate_raw_cam(
        self,
        input_tensor: torch.Tensor,
        target_class_idx: int,
        image: Optional[Image.Image] = None,
        *,
        apply_lung_mask: bool = True,
        method: str = "gradcam",
        target_layers: Optional[list[nn.Module]] = None,
    ) -> np.ndarray:
        """Return a raw normalized CAM array before colorization."""
        cam = self._compute_cam(
            input_tensor=input_tensor,
            target_class_idx=target_class_idx,
            method=method,
            target_layers=target_layers,
        )
        if apply_lung_mask and image is not None:
            mask = self.create_lung_mask(image, cam.shape)
            cam = self._normalize_cam(cam * mask)
        return cam

    @staticmethod
    def heatmap_to_bboxes(cam: np.ndarray, threshold: float = 0.5) -> list[dict]:
        """Extract bounding boxes from a normalized activation map."""
        effective_threshold = max(threshold, float(np.quantile(cam, 0.85)))
        binary = (cam > effective_threshold).astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        bboxes = []
        image_area = cam.shape[0] * cam.shape[1]
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            box_area = w * h
            if max(20, image_area * 0.005) <= box_area <= image_area * 0.50:
                bboxes.append({
                    "x1": int(x),
                    "y1": int(y),
                    "x2": int(x + w),
                    "y2": int(y + h),
                    "label": "anomaly_region",
                    "confidence": round(float(cam[y:y + h, x:x + w].max()), 4),
                })

        return sorted(bboxes, key=lambda box: box["confidence"], reverse=True)[:5]
