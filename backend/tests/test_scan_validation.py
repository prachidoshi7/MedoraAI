"""Regression tests for scan-type upload validation."""

import unittest
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException
from PIL import Image

from routers.scan import _enforce_scan_type_verification, _validate_scan_matches_selected_type
from services.scan_type_verifier import ScanTypeVerification, ScanTypeVerifier


def grayscale_test_image() -> Image.Image:
    """Return a structured, non-flat grayscale image accepted by both models."""
    y, x = np.mgrid[0:256, 0:256]
    pixels = 35 + 150 * np.exp(-(((x - 128) / 82) ** 2 + ((y - 128) / 96) ** 2))
    pixels += 24 * np.sin(x / 9.0) * np.cos(y / 13.0)
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), mode="L").convert("RGB")


class ScanValidationTests(unittest.TestCase):
    def test_brain_selection_is_not_overridden_by_chest_heuristic(self):
        with patch("routers.scan._has_chest_xray_lung_pattern", return_value=True):
            _validate_scan_matches_selected_type(grayscale_test_image(), "brain_mri", "MRI")

    def test_chest_selection_is_not_overridden_by_brain_heuristic(self):
        with (
            patch("routers.scan._looks_like_centered_brain_slice", return_value=True),
            patch("routers.scan._has_chest_xray_lung_pattern", return_value=False),
        ):
            _validate_scan_matches_selected_type(grayscale_test_image(), "chest_xray", "X-ray")

    def test_authoritative_dicom_modality_mismatch_is_still_rejected(self):
        with self.assertRaises(HTTPException):
            _validate_scan_matches_selected_type(grayscale_test_image(), "brain_mri", "DX")
        with self.assertRaises(HTTPException):
            _validate_scan_matches_selected_type(grayscale_test_image(), "chest_xray", "MR")

    def test_blank_image_is_rejected_for_both_models(self):
        blank = Image.new("RGB", (256, 256), (80, 80, 80))
        for scan_type, modality in (("brain_mri", "MRI"), ("chest_xray", "X-ray")):
            with self.subTest(scan_type=scan_type), self.assertRaises(HTTPException):
                _validate_scan_matches_selected_type(blank, scan_type, modality)

    def test_colour_photo_is_rejected_for_both_models(self):
        y, x = np.mgrid[0:256, 0:256]
        colour = np.stack((x, y, (x + y) % 256), axis=-1).astype(np.uint8)
        image = Image.fromarray(colour, mode="RGB")
        for scan_type, modality in (("brain_mri", "MRI"), ("chest_xray", "X-ray")):
            with self.subTest(scan_type=scan_type), self.assertRaises(HTTPException):
                _validate_scan_matches_selected_type(image, scan_type, modality)

    def test_exact_verified_scan_type_is_accepted(self):
        verification = ScanTypeVerification(
            category="brain_mri",
            confidence=0.98,
            is_single_diagnostic_image=True,
            anatomy_complete_enough=True,
            reason="Single brain MRI slice.",
        )
        _enforce_scan_type_verification(verification, "brain_mri", 0.85)

    def test_verified_opposite_scan_type_is_rejected(self):
        verification = ScanTypeVerification(
            category="chest_xray",
            confidence=0.99,
            is_single_diagnostic_image=True,
            anatomy_complete_enough=True,
            reason="Frontal chest radiograph.",
        )
        with self.assertRaises(HTTPException) as raised:
            _enforce_scan_type_verification(verification, "brain_mri", 0.85)
        self.assertIn("chest X-ray", raised.exception.detail)

    def test_poster_or_collage_is_rejected_before_type_match(self):
        verification = ScanTypeVerification(
            category="brain_mri",
            confidence=0.99,
            is_single_diagnostic_image=False,
            anatomy_complete_enough=True,
            reason="Poster containing a scan image and text.",
        )
        with self.assertRaises(HTTPException) as raised:
            _enforce_scan_type_verification(verification, "brain_mri", 0.85)
        self.assertIn("posters", raised.exception.detail.lower())

    def test_uncertain_or_low_confidence_type_is_rejected(self):
        for category, confidence in (("uncertain", 0.99), ("chest_xray", 0.70)):
            verification = ScanTypeVerification(
                category=category,
                confidence=confidence,
                is_single_diagnostic_image=True,
                anatomy_complete_enough=True,
                reason="Uncertain input.",
            )
            with self.subTest(category=category, confidence=confidence), self.assertRaises(HTTPException):
                _enforce_scan_type_verification(verification, "chest_xray", 0.85)

    def test_verifier_response_parser_fails_closed(self):
        verification = ScanTypeVerifier._parse_response(
            '{"category":"unexpected","confidence":4,"is_single_diagnostic_image":1,'
            '"anatomy_complete_enough":true,"reason":"unknown"}'
        )
        self.assertEqual(verification.category, "uncertain")
        self.assertEqual(verification.confidence, 1.0)
        self.assertFalse(verification.is_single_diagnostic_image)

    def test_verifier_uses_bounded_fast_model_attempts(self):
        verifier = ScanTypeVerifier(
            api_key="configured",
            model="gemini-3-flash-preview",
        )
        self.assertEqual(verifier.models[0], "gemini-flash-latest")
        self.assertLessEqual(len(verifier.models), 2)

    def test_local_verifier_rejects_a_non_medical_colour_layout(self):
        verifier = ScanTypeVerifier(api_key=None, model="unused")
        image = Image.new("RGB", (640, 240), (255, 255, 255))
        pixels = np.asarray(image).copy()
        pixels[40:200, 40:250] = (90, 20, 220)
        result = verifier._verify_locally(Image.fromarray(pixels))
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "other")
        self.assertFalse(result.is_single_diagnostic_image)

    def test_primary_provider_prevents_rate_limited_secondary_call(self):
        verifier = ScanTypeVerifier(
            api_key="secondary-key",
            model="secondary-model",
            groq_api_key="primary-key",
        )
        provider_result = ScanTypeVerification(
            category="brain_mri",
            confidence=0.96,
            is_single_diagnostic_image=True,
            anatomy_complete_enough=True,
            reason="Single brain MRI image.",
        )
        with (
            patch.object(verifier, "_verify_locally", return_value=None),
            patch.object(verifier, "_verify_with_groq", return_value=provider_result),
            patch.object(verifier, "_verify_with_gemini") as secondary,
        ):
            result = verifier._verify_sync(grayscale_test_image())
        self.assertEqual(result.category, "brain_mri")
        secondary.assert_not_called()

    def test_secondary_provider_is_used_when_primary_is_unavailable(self):
        verifier = ScanTypeVerifier(
            api_key="secondary-key",
            model="secondary-model",
            groq_api_key="primary-key",
        )
        provider_result = ScanTypeVerification(
            category="chest_xray",
            confidence=0.97,
            is_single_diagnostic_image=True,
            anatomy_complete_enough=True,
            reason="Single frontal chest radiograph.",
        )
        with (
            patch.object(verifier, "_verify_locally", return_value=None),
            patch.object(verifier, "_verify_with_groq", side_effect=RuntimeError("429")),
            patch.object(verifier, "_verify_with_gemini", return_value=provider_result) as secondary,
        ):
            result = verifier._verify_sync(grayscale_test_image())
        self.assertEqual(result.category, "chest_xray")
        secondary.assert_called_once()

    def test_internal_vision_tiles_do_not_turn_one_image_into_a_collage(self):
        verifier = ScanTypeVerifier(api_key=None, model="unused")
        image = grayscale_test_image()
        provider_result = ScanTypeVerification(
            category="brain_mri",
            confidence=0.95,
            is_single_diagnostic_image=False,
            anatomy_complete_enough=True,
            reason="Multiple zoomed panels created from the same brain image.",
        )
        normalized = verifier._normalize_provider_layout(provider_result, image)
        self.assertTrue(normalized.is_single_diagnostic_image)


if __name__ == "__main__":
    unittest.main()
