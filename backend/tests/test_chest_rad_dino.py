"""Focused regression tests for RAD-DINO chest result handling."""

import unittest

import numpy as np
import torch

from services.chest_attribution import ChestRadDinoAttribution
from services.chest_classifier import (
    CLASS_LABELS,
    NO_FINDING_LABEL,
    build_classification_result,
)


class RadDinoChestResultTests(unittest.TestCase):
    def test_pathology_above_threshold_becomes_primary(self):
        scores = np.zeros(len(CLASS_LABELS), dtype=np.float32)
        scores[CLASS_LABELS.index(NO_FINDING_LABEL)] = 0.91
        scores[CLASS_LABELS.index("Pneumonia")] = 0.78
        scores[CLASS_LABELS.index("Support Devices")] = 0.69

        result = build_classification_result(scores)

        self.assertEqual(result.top_label, "Pneumonia")
        self.assertEqual(result.heatmap_target_idx, CLASS_LABELS.index("Pneumonia"))
        self.assertEqual(result.severity, "Moderate")
        self.assertIn("Support Devices", [item["label"] for item in result.secondary_findings])
        self.assertNotIn(NO_FINDING_LABEL, [item["label"] for item in result.secondary_findings])

    def test_no_finding_requires_all_pathologies_below_threshold(self):
        scores = np.zeros(len(CLASS_LABELS), dtype=np.float32)
        scores[0] = 0.72
        scores[CLASS_LABELS.index("Cardiomegaly")] = 0.49

        result = build_classification_result(scores, pathology_threshold=0.50)

        self.assertEqual(result.top_label, NO_FINDING_LABEL)
        self.assertEqual(result.confidence, 0.72)
        self.assertEqual(result.heatmap_target_idx, 0)
        self.assertFalse(result.is_low_confidence)

    def test_invalid_checkpoint_output_is_rejected(self):
        with self.assertRaises(ValueError):
            build_classification_result(np.zeros(13, dtype=np.float32))
        invalid = np.zeros(len(CLASS_LABELS), dtype=np.float32)
        invalid[4] = np.nan
        with self.assertRaises(ValueError):
            build_classification_result(invalid)

    def test_attribution_boxes_use_512_pixel_display_coordinates(self):
        attribution = ChestRadDinoAttribution.__new__(ChestRadDinoAttribution)
        raw = np.zeros((37, 37), dtype=np.float32)
        raw[8:18, 5:15] = 1.0

        boxes = attribution.heatmap_to_bboxes(raw)

        self.assertTrue(boxes)
        for box in boxes:
            self.assertGreaterEqual(box["x1"], 0)
            self.assertGreaterEqual(box["y1"], 0)
            self.assertLessEqual(box["x2"], 512)
            self.assertLessEqual(box["y2"], 512)
            self.assertEqual(box["label"], "model_attribution_region")

    def test_chest_mask_is_selected_by_finding_anatomy(self):
        self.assertTrue(ChestRadDinoAttribution.should_apply_lung_mask("Pneumonia"))
        self.assertTrue(ChestRadDinoAttribution.should_apply_lung_mask("Lung Opacity"))
        self.assertFalse(ChestRadDinoAttribution.should_apply_lung_mask("Cardiomegaly"))
        self.assertFalse(ChestRadDinoAttribution.should_apply_lung_mask("Fracture"))
        self.assertFalse(ChestRadDinoAttribution.should_apply_lung_mask("Pleural Effusion"))

    def test_token_gradcam_pp_is_finite_and_class_targeted(self):
        activations = torch.zeros((16, 4), dtype=torch.float32)
        activations[5:11, :] = 2.0
        gradients = torch.full((16, 4), -0.1, dtype=torch.float32)
        gradients[6:10, :] = 0.8

        attribution = ChestRadDinoAttribution._token_gradcam_pp(
            activations,
            gradients,
        )

        self.assertEqual(attribution.shape, (16,))
        self.assertTrue(np.isfinite(attribution).all())
        self.assertGreater(float(attribution[6:10].mean()), float(attribution[:4].mean()))

    def test_attribution_box_accepts_finding_label(self):
        attribution = ChestRadDinoAttribution.__new__(ChestRadDinoAttribution)
        raw = np.zeros((37, 37), dtype=np.float32)
        raw[10:22, 12:25] = 1.0

        boxes = attribution.heatmap_to_bboxes(
            raw,
            label="Pneumonia_model_attribution",
        )

        self.assertTrue(boxes)
        self.assertEqual(boxes[0]["label"], "Pneumonia_model_attribution")


if __name__ == "__main__":
    unittest.main()
