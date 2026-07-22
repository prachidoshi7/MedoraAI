import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from services.llm_report_engine import LLMReportEngine


def result(label="Glioma", confidence=0.91, severity="Severe"):
    return SimpleNamespace(
        top_label=label,
        confidence=confidence,
        severity=severity,
        all_scores={"Glioma": confidence, "Meningioma": 0.06, "No Tumor": 0.02, "Pituitary": 0.01},
        is_low_confidence=confidence < 0.5,
        heatmap_target_label=label,
        secondary_findings=[],
    )


class ReportSchemaTests(unittest.TestCase):
    def test_json_parser_requires_grounded_clinical_sections(self):
        payload = {
            "technique": "Single image.",
            "comparison": "None.",
            "image_quality": "Limited.",
            "findings": "Visible structures assessed on the supplied image.",
            "impression": "1. Indeterminate finding.",
            "differential_diagnosis": "None.",
            "recommendations": "Review the complete study.",
            "critical_communication": "No critical communication generated.",
            "patient_explanation": "A concise explanation for the patient.",
        }
        parsed = LLMReportEngine._parse_json_report(json.dumps(payload))
        self.assertEqual(set(parsed), set(payload))

    def test_fallback_does_not_turn_confidence_severity_into_urgent_treatment(self):
        report = LLMReportEngine()._generate_template_report(result(), "brain_mri")
        combined = " ".join(report.values()).lower()
        self.assertNotIn("urgent", combined)
        self.assertNotIn("biopsy", combined)
        self.assertNotIn("surgery", combined)
        self.assertIn("single", report["technique"].lower())
        self.assertIn("insufficient", report["impression"].lower())

    def test_translation_chunks_stay_inside_api_limit(self):
        text = "Sentence for the patient. " * 250
        chunks = LLMReportEngine._chunk_translation_text(text, limit=1900)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 1900 for chunk in chunks))

    def test_brain_report_grounding_removes_unsupported_acquisition_claims(self):
        generated = {
            "technique": "Single exported coronal post-contrast MRI slice.",
            "comparison": "Compared with an unavailable prior examination.",
            "image_quality": "Diagnostic quality.",
            "findings": (
                "SELLA: A lobulated, heterogeneously enhancing sellar mass is visible, "
                "demonstrating concordance with the supportive classifier finding.\n"
                "BRAIN: Restricted diffusion is present."
            ),
            "impression": "1. Enhancing sellar mass, supported by the model.",
            "differential_diagnosis": "Pituitary adenoma.",
            "recommendations": "Obtain a complete pituitary MRI protocol.",
            "critical_communication": "No critical communication generated.",
            "patient_explanation": "",
        }

        report = LLMReportEngine._ground_report_to_available_input(
            generated, "brain_mri"
        )
        clinical_text = " ".join(
            report[field]
            for field in ("findings", "impression", "differential_diagnosis")
        ).lower()

        self.assertIn("pulse sequence", report["technique"].lower())
        self.assertIn("not available", report["technique"].lower())
        self.assertEqual(
            report["comparison"],
            "No prior imaging was supplied for comparison.",
        )
        self.assertIn("sellar mass", clinical_text)
        self.assertNotIn("enhanc", clinical_text)
        self.assertNotIn("classifier", clinical_text)
        self.assertNotIn("restricted diffusion", clinical_text)

    def test_grounding_preserves_anatomy_line_breaks(self):
        report = LLMReportEngine._ground_report_to_available_input(
            {
                "findings": "LUNGS/AIRWAYS: Clear.\nPLEURA: No visible pleural fluid.",
                "impression": "1. No focal chest abnormality identified.",
                "differential_diagnosis": "None based on the supplied image.",
            },
            "chest_xray",
        )
        self.assertIn("\n", report["findings"])


class PatientTranslationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stored_patient_explanation_returns_without_an_extra_generation_call(self):
        engine = LLMReportEngine(gemini_api_key="configured")
        engine._generate_gemini_text = AsyncMock(return_value="should not be used")

        output = await engine._generate_patient_explanation_english({
            "patient_explanation": "A prepared plain-language explanation.",
            "scan_type": "chest_xray",
        })

        self.assertEqual(output, "A prepared plain-language explanation.")
        engine._generate_gemini_text.assert_not_awaited()

    async def test_existing_report_gets_an_immediate_grounded_english_explanation(self):
        engine = LLMReportEngine(gemini_api_key="configured")
        engine._generate_gemini_text = AsyncMock(return_value="should not be used")

        output = await engine._generate_patient_explanation_english({
            "scan_type": "brain_mri",
            "top_label": "Meningioma",
            "critical_communication": "No critical communication generated.",
        })

        self.assertIn("covering around the brain", output)
        self.assertIn("not a confirmed diagnosis", output)
        engine._generate_gemini_text.assert_not_awaited()

    async def test_patient_translation_uses_primary_translator_first(self):
        engine = LLMReportEngine(sarvam_api_key="configured", gemini_api_key="configured")
        engine._generate_patient_explanation_english = AsyncMock(return_value="English explanation")
        engine._translate_with_sarvam = AsyncMock(return_value="हिंदी विवरण")
        engine._translate_with_gemini = AsyncMock(return_value="fallback")

        output = await engine.generate_patient_report({}, "Hindi")

        self.assertEqual(output, "हिंदी विवरण")
        engine._translate_with_sarvam.assert_awaited_once_with("English explanation", "hi-IN")
        engine._translate_with_gemini.assert_not_awaited()

    async def test_patient_translation_falls_back_without_exposing_provider(self):
        engine = LLMReportEngine(sarvam_api_key="configured", gemini_api_key="configured")
        engine._generate_patient_explanation_english = AsyncMock(return_value="English explanation")
        engine._translate_with_sarvam = AsyncMock(return_value=None)
        engine._translate_with_gemini = AsyncMock(return_value="தமிழ் விளக்கம்")

        output = await engine.generate_patient_report({}, "Tamil")

        self.assertEqual(output, "தமிழ் விளக்கம்")
        self.assertNotIn("Gemini", output)
        self.assertNotIn("Sarvam", output)


if __name__ == "__main__":
    unittest.main()
