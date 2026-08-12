"""Shared Grad-CAM implementation for compact grayscale organ models."""

import cv2
import numpy as np
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget


class GrayscaleOrganGradCAM:
    def __init__(self, classifier, target_layer, input_size: int):
        self.classifier = classifier
        self.model = classifier.get_model()
        self.target_layers = [target_layer]
        self.input_size = input_size

    def generate(self, image: Image.Image, target_idx: int):
        tensor = self.classifier.preprocess(image)
        with GradCAM(model=self.model, target_layers=self.target_layers) as cam:
            raw_cam = cam(
                input_tensor=tensor,
                targets=[ClassifierOutputTarget(target_idx)],
            )[0]
        gray = np.asarray(
            image.resize((self.input_size, self.input_size)).convert("L"),
            dtype=np.float32,
        ) / 255.0
        rgb = np.stack([gray, gray, gray], axis=-1)
        overlay = show_cam_on_image(rgb, raw_cam, use_rgb=True)
        overlay = cv2.resize(overlay, (512, 512), interpolation=cv2.INTER_CUBIC)
        bboxes = self._boxes(raw_cam, target_idx)
        return overlay, bboxes

    @staticmethod
    def _boxes(raw_cam: np.ndarray, target_idx: int) -> list[dict]:
        mask = (raw_cam >= max(0.55, float(raw_cam.max()) * 0.65)).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        height, width = raw_cam.shape
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            if cv2.contourArea(contour) < height * width * 0.01:
                continue
            x, y, box_width, box_height = cv2.boundingRect(contour)
            boxes.append({
                "x1": int(x / width * 512),
                "y1": int(y / height * 512),
                "x2": int((x + box_width) / width * 512),
                "y2": int((y + box_height) / height * 512),
                "label": f"Activation {target_idx + 1}",
                "confidence": round(float(raw_cam[y:y + box_height, x:x + box_width].mean()), 4),
            })
        return boxes
