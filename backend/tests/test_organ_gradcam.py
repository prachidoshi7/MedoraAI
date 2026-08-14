"""Regression tests for lung/kidney class-targeted Grad-CAM++."""

import threading
import unittest

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

from services.organ_gradcam import GrayscaleOrganGradCAM


class _TinyOrganModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 4, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(4)
        self.conv2 = nn.Conv2d(4, 6, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(6)
        self.classifier = nn.Linear(6, 2, bias=False)
        with torch.no_grad():
            self.conv1.weight.fill_(1.0 / 9.0)
            self.conv2.weight.fill_(1.0 / 36.0)
            self.classifier.weight[0].fill_(1.0)
            self.classifier.weight[1].fill_(-1.0)

    def forward(self, inputs):
        inputs = F.relu(self.bn1(self.conv1(inputs)))
        inputs = F.relu(self.bn2(self.conv2(inputs)))
        return self.classifier(inputs.mean(dim=(2, 3)))


class _TinyClassifier:
    def __init__(self):
        self.model = _TinyOrganModel().eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.inference_lock = threading.RLock()

    def get_model(self):
        return self.model

    @staticmethod
    def preprocess(image: Image.Image) -> torch.Tensor:
        values = np.asarray(
            image.convert("L").resize((32, 32), Image.Resampling.BILINEAR),
            dtype=np.float32,
        ) / 255.0
        return torch.from_numpy(values).unsqueeze(0).unsqueeze(0)


class OrganGradCAMTests(unittest.TestCase):
    def setUp(self):
        classifier = _TinyClassifier()
        self.engine = GrayscaleOrganGradCAM(
            classifier,
            [classifier.model.bn2, classifier.model.bn1],
            input_size=32,
            layer_weights=[0.8, 0.2],
            anatomy_mode="lung_ct",
            region_label="test_attribution",
        )
        pixels = np.zeros((72, 96), dtype=np.uint8)
        cv2.ellipse(pixels, (48, 37), (31, 26), 0, 0, 360, 90, -1)
        pixels[25:46, 53:75] = 230
        self.image = Image.fromarray(pixels, mode="L")

    def test_generates_finite_source_projected_heatmap_and_overlay(self):
        overlay, cam = self.engine.generate_heatmap_and_raw(
            self.image,
            0,
            target_label="Positive",
        )

        self.assertEqual(overlay.shape, (512, 512, 3))
        self.assertEqual(overlay.dtype, np.uint8)
        self.assertEqual(cam.shape, (512, 512))
        self.assertTrue(np.isfinite(cam).all())
        self.assertGreater(float(cam.max()), 0.99)
        self.assertLessEqual(float(cam.max()), 1.0)
        self.assertLess(float(cam[:35, :35].mean()), float(cam[180:330, 260:410].mean()))
        self.assertEqual(self.engine.last_stats["target_label"], "Positive")

    def test_regions_use_report_coordinates_and_target_label(self):
        _overlay, cam = self.engine.generate_heatmap_and_raw(self.image, 0)
        boxes = self.engine.heatmap_to_bboxes(cam, label="Positive_model_attribution")

        self.assertTrue(boxes)
        for box in boxes:
            self.assertGreaterEqual(box["x1"], 0)
            self.assertGreaterEqual(box["y1"], 0)
            self.assertLessEqual(box["x2"], 512)
            self.assertLessEqual(box["y2"], 512)
            self.assertEqual(box["label"], "Positive_model_attribution")

    def test_invalid_target_class_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.generate_heatmap_and_raw(self.image, 8)


if __name__ == "__main__":
    unittest.main()
