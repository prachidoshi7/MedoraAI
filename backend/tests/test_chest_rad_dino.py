"""Regression checks for the madora-reference chest integration."""

import unittest

import numpy as np

from services.chest_classifier import (
    CLASS_LABELS,
    INPUT_SIZE,
    MIN_PATHOLOGY_CONFIDENCE,
    NO_FINDING_LABEL,
    SECONDARY_FINDING_THRESHOLD,
    confidence_to_severity,
)
from services.chest_gradcam import ChestGradCAM


class ReferenceChestTests(unittest.TestCase):
    def test_reference_configuration(self):
        self.assertEqual(CLASS_LABELS, ["Normal", "Pneumonia", "Tuberculosis"])
        self.assertEqual(NO_FINDING_LABEL, "Normal")
        self.assertEqual(INPUT_SIZE, 518)
        self.assertEqual(MIN_PATHOLOGY_CONFIDENCE, 0.30)
        self.assertEqual(SECONDARY_FINDING_THRESHOLD, 0.20)

    def test_reference_severity_thresholds(self):
        self.assertEqual(confidence_to_severity(0.99, "Normal"), "Normal")
        self.assertEqual(confidence_to_severity(0.49, "Pneumonia"), "Mild")
        self.assertEqual(confidence_to_severity(0.50, "Pneumonia"), "Moderate")
        self.assertEqual(confidence_to_severity(0.75, "Tuberculosis"), "Severe")

    def test_reference_cam_normalization_is_finite(self):
        cam = np.array([[0.0, np.nan], [1.0, np.inf]], dtype=np.float32)
        normalized = ChestGradCAM._normalize_cam(cam)
        self.assertTrue(np.isfinite(normalized).all())
        self.assertGreaterEqual(float(normalized.min()), 0.0)
        self.assertLessEqual(float(normalized.max()), 1.0)

    def test_reference_bbox_contract(self):
        cam = np.zeros((518, 518), dtype=np.float32)
        cam[100:220, 120:250] = 1.0
        boxes = ChestGradCAM.heatmap_to_bboxes(cam, threshold=0.6)
        self.assertTrue(boxes)
        self.assertEqual(boxes[0]["label"], "anomaly_region")


if __name__ == "__main__":
    unittest.main()
