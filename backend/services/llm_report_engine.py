"""
MedoraAI — LLM-Powered Clinical Report Engine
Generates professional radiology reports by sending model output to LLM APIs.

Flow: Image + Model Output → Grounded Clinical Prompt → Structured Report
Patient communication: English explanation → Sarvam translation → internal fallback
"""

import asyncio
import base64
import io
import json
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# AI Disclaimer — mandatory on every report
DISCLAIMER = (
    "This preliminary report was prepared by the MedoraAI clinical support model "
    "and is intended as a decision-support tool only. "
    "It must NOT be used as a standalone diagnostic instrument. "
    "All findings must be reviewed, verified, and co-signed by a "
    "licensed radiologist before any clinical action is taken. "
    "MedoraAI is not a certified medical device."
)


SYSTEM_PROMPT = """You prepare a structured preliminary imaging report for a doctor.
Write with the organization, precision, and restraint of a careful senior radiologist.
You receive:
1. the uploaded medical image when a multimodal provider is available,
2. the local ML classifier output,
3. model confidence scores and severity metadata.

GROUNDING RULES:
- The image is the visual evidence. Classifier output is supporting evidence and must never be copied as a visual fact when the image does not support it.
- This may be a single exported image, not a complete imaging study. State that limitation in technique and image_quality.
- Never fabricate clinical history, symptoms, patient age/sex, projection, MRI sequence, contrast use, comparison, measurements, laterality, anatomical location, devices, or prior studies.
- Only state laterality, location, morphology, mass effect, edema, pleural findings, support devices, or measurements when clearly visible.
- Do not convert classifier confidence into clinical severity, urgency, tumor grade, or disease stage.
- If image and classifier disagree, say the examination is indeterminate and explain what confirmatory review is needed.
- Use concise radiology language. Do not discuss model architecture, provider names, prompts, confidence percentages, or heatmaps in the clinical prose.
- Do not mention the classifier, automated analysis, model agreement, concordance, confidence, or Grad-CAM anywhere in the clinical sections. Those results are displayed separately.
- For a brain MRI image with unknown sequence and contrast status, never describe enhancement, restricted diffusion, ADC, FLAIR, T1/T2 signal, susceptibility, perfusion, or contrast uptake as an observed finding.
- Put the most clinically important supported conclusion first in impression. Number multiple impressions.
- Differential diagnosis must be short and evidence-based. Use "None based on the supplied image" when no differential is supported.
- Recommendations must follow from the observed finding and limitations. Do not recommend biopsy, surgery, emergency treatment, or disease-specific laboratory testing solely from a classifier label.
- critical_communication must be "No critical communication generated" unless the supplied image clearly demonstrates an immediately dangerous finding.

You MUST output ONLY valid JSON with exactly these nine string keys:
{
  "technique": "What image/view was supplied and the limits of that input",
  "comparison": "Prior study availability",
  "image_quality": "Diagnostic adequacy and visible technical limitations",
  "findings": "Detailed, anatomy-organized observations supported by the image",
  "impression": "Numbered prioritized conclusions",
  "differential_diagnosis": "Brief supported differential or none",
  "recommendations": "Actionable next steps proportional to the evidence",
  "critical_communication": "Critical result communication status",
  "patient_explanation": "Four short plain-English paragraphs explaining the supported conclusion, meaning, next step, and limitations without model terms or confidence scores"
}

Output ONLY valid JSON. No markdown, no code fences, no explanation, no extra text."""


class LLMReportEngine:
    """
    Generates clinical reports using LLM APIs.
    
    Tries providers in priority order:
    1. Gemini — image-aware multimodal reporting
    2. Groq (Llama 3.1 70B) — text-only fallback
    3. Anthropic Claude 3 Haiku — text-only fallback
    4. OpenAI GPT-4o-mini — text-only fallback
    5. Template fallback — no API key needed
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-3-flash-preview",
        sarvam_api_key: Optional[str] = None,
        sarvam_translate_model: str = "sarvam-translate:v1",
        groq_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.gemini_key = gemini_api_key
        self.gemini_model = gemini_model
        self.gemini_models = list(dict.fromkeys([
            gemini_model,
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]))
        self.sarvam_key = sarvam_api_key
        self.sarvam_translate_model = sarvam_translate_model
        self.sarvam_translation_disabled = False
        self.groq_key = groq_api_key
        self.anthropic_key = anthropic_api_key
        self.openai_key = openai_api_key

        providers = []
        if self.gemini_key:
            providers.append("gemini")
        if self.groq_key:
            providers.append("groq")
        if self.anthropic_key:
            providers.append("claude")
        if self.openai_key:
            providers.append("openai")
        if not providers:
            providers.append("template (fallback)")

        logger.info(
            "Clinical report engine initialized (%s); patient translation: %s",
            ", ".join(providers),
            "configured" if self.sarvam_key else "local fallback",
        )

    def _build_user_prompt(self, result, scan_type: str) -> str:
        """Build the clinical context prompt from model output."""
        if scan_type == "chest_xray":
            # Format all scores for context
            supported_scores = [
                (label, score)
                for label, score in sorted(result.all_scores.items(), key=lambda x: -x[1])
                if score >= 0.20
            ][:5]
            scores_text = "\n".join(
                f"  - {label}: {score * 100:.1f}%"
                for label, score in supported_scores
            ) or "  - No secondary score reached the reporting threshold."
            return f"""EXAM: Chest radiograph
AVAILABLE INPUT: One uploaded image only; projection and patient positioning are not provided.
CLINICAL HISTORY: Not provided.
COMPARISON: No prior study supplied.

SUPPORTING CLASSIFIER OUTPUT (not a substitute for visual findings):
- Highest-scoring label: {result.top_label} ({result.confidence * 100:.1f}%)
- Labels at or above the reporting threshold:
{scores_text}

CHEST-SPECIFIC INSTRUCTIONS:
- Organize findings under these plain-text labels: LUNGS/AIRWAYS, PLEURA, CARDIOMEDIASTINAL SILHOUETTE, HILA, BONES/SOFT TISSUES, SUPPORT DEVICES.
- Assess only what is visible. If a structure cannot be assessed, say so instead of assuming normality.
- Do not infer AP versus PA, portable technique, inspiration, rotation, or upright/supine position unless clearly demonstrated.
- "No Finding" means the classifier did not flag a trained label; it does not prove a normal radiograph.
- A positive classifier label may be reported as visually suspected only if the image supports it; otherwise describe the discordance in the impression.
- Do not include educational definitions of diseases in the report.

Generate a detailed, grounded chest radiograph report for clinical review."""

        elif scan_type == "brain_mri":
            # Format all 4-class scores for context
            scores_text = "\n".join(
                f"  - {label}: {score * 100:.1f}%"
                for label, score in sorted(result.all_scores.items(), key=lambda x: -x[1])
            )
            return f"""EXAM: Brain MRI image
AVAILABLE INPUT: One uploaded 2D image only; the sequence, plane, contrast status, and complete series are not provided.
CLINICAL HISTORY: Not provided.
COMPARISON: No prior study supplied.

SUPPORTING FOUR-CLASS CLASSIFIER OUTPUT (not a substitute for visual findings):
- Highest-scoring label: {result.top_label} ({result.confidence * 100:.1f}%)
- Class scores:
{scores_text}

CLASS DEFINITIONS:
- Glioma: Primary brain tumor arising from glial cells; includes astrocytomas, oligodendrogliomas, glioblastomas
- Meningioma: Typically benign tumor arising from meninges; usually well-circumscribed, extra-axial
- No Tumor: No model-supported mass lesion identified
- Pituitary: Tumor of the pituitary gland (sellar/suprasellar region); usually adenoma

BRAIN-SPECIFIC INSTRUCTIONS:
- Organize findings under these plain-text labels: BRAIN PARENCHYMA, EXTRA-AXIAL SPACES, VENTRICLES/MASS EFFECT, SELLA, VISIBLE POSTERIOR FOSSA.
- A single image cannot establish a complete brain MRI interpretation. Explicitly state which areas or features cannot be assessed.
- Do not infer MRI sequence, signal characteristics across sequences, enhancement, diffusion restriction, perfusion, hemorrhage, or exact tumor boundaries from absent series.
- Do not assign tumor grade, molecular subtype, histology, stage, or treatment urgency from the class label.
- "No Tumor" means no model-supported lesion in the four trained categories; it does not exclude other intracranial disease.
- Name a tumor category in the impression only when image appearance and classifier output are concordant. Otherwise use "indeterminate abnormality" and recommend complete diagnostic MRI review.
- Do not include general disease definitions in findings.

Generate a detailed, grounded limited-image neuroradiology report for clinical review."""

        else:
            return f"""SCAN TYPE: Medical Image ({scan_type})
AI MODEL OUTPUT:
- Primary Finding: {result.top_label} (Confidence: {result.confidence * 100:.1f}%)
- Severity Assessment: {result.severity}

Generate a structured diagnostic report."""

    async def generate_report(
        self,
        result,
        scan_type: str,
        modality: str = "X-ray",
        patient_id: str = "DEMO-001",
        image=None,
    ) -> dict:
        """
        Generate a full clinical report using the best available LLM provider.
        
        Args:
            result: ClassificationResult or BrainClassificationResult
            scan_type: "chest_xray" or "brain_mri"
            modality: Imaging modality string
            patient_id: Patient identifier
            image: Optional PIL image for multimodal report providers
            
        Returns:
            Complete report dictionary with all fields
        """
        user_prompt = self._build_user_prompt(result, scan_type)
        llm_report = None
        llm_provider = "template"

        # Try providers in order
        if self.gemini_key and image is not None:
            llm_report = await self._call_gemini(user_prompt, image)
            if llm_report:
                llm_provider = "gemini"

        if llm_report is None and self.groq_key:
            llm_report = await self._call_groq(user_prompt)
            if llm_report:
                llm_provider = "groq"

        if llm_report is None and self.anthropic_key:
            llm_report = await self._call_claude(user_prompt)
            if llm_report:
                llm_provider = "claude"

        if llm_report is None and self.openai_key:
            llm_report = await self._call_openai(user_prompt)
            if llm_report:
                llm_provider = "openai"

        # Fallback to template if no LLM succeeded
        if llm_report is None:
            llm_report = self._generate_template_report(result, scan_type)
            llm_provider = "template"
        elif scan_type == "chest_xray" and not self._is_chest_report_supported(
            llm_report,
            result,
            allow_visual_details=(llm_provider == "gemini"),
        ):
            logger.warning("LLM chest report contained unsupported findings. Falling back to template.")
            llm_report = self._generate_template_report(result, scan_type)
            llm_provider = "template"

        llm_report = self._complete_report_sections(llm_report, scan_type)
        llm_report = self._ground_report_to_available_input(llm_report, scan_type)

        # Build the full report
        now = datetime.now()

        # Determine heatmap target and low-confidence flag
        is_low_confidence = getattr(result, "is_low_confidence", False)
        heatmap_target_label = getattr(result, "heatmap_target_label", result.top_label)
        secondary_findings = getattr(result, "secondary_findings", [])

        # Model methodology description
        if scan_type == "chest_xray":
            methodology = (
                "Classification was performed using an EfficientNet-B4 convolutional neural network "
                "fine-tuned on the NIH ChestX-ray14 dataset (multi-label, 15 classes including No Finding). "
                "The model outputs per-class sigmoid probabilities. "
                "Explainability was generated using Gradient-weighted Class Activation Mapping (Grad-CAM) "
                "targeting the last convolutional layer (conv_head). "
                "The heatmap represents actual gradient-weighted activations from the trained model — "
                "it is NOT a simulated or synthetic overlay. "
                f"Grad-CAM target class: {heatmap_target_label}."
            )
        elif scan_type == "brain_mri":
            methodology = (
                "Classification was performed using an EfficientNetB3 convolutional neural network "
                "with ImageNet pretrained weights, fine-tuned via progressive 3-phase training "
                "for 4-class brain tumor classification (Glioma, Meningioma, No Tumor, Pituitary). "
                "Input images undergo brain contour cropping and are processed at 260×260 resolution. "
                "Test-Time Augmentation (TTA) is applied at inference for improved accuracy. "
                "Explainability was generated using multi-scale Grad-CAM++ targeting "
                "top_activation (9×9) and block6a_expand_activation (17×17) layers. "
                "The heatmap represents actual gradient-weighted activations from the trained model."
            )
        else:
            methodology = "AI model classification with Grad-CAM explainability."

        limitations = (
            "This AI system has inherent limitations: (1) The model was trained on a specific dataset "
            "and may not generalize to all patient populations or imaging equipment. "
            "(2) Multi-label classification confidence scores are not calibrated probabilities and "
            "should not be interpreted as disease prevalence. "
            "(3) Grad-CAM heatmaps indicate model-influential regions but do not constitute "
            "radiologist-confirmed lesion localization. "
            "(4) The system cannot detect pathologies outside its training classes. "
            "(5) Image quality, positioning, and artifacts may affect model performance."
        )

        return {
            "patient_id": patient_id,
            "scan_date": now.strftime("%Y-%m-%d"),
            "scan_type": scan_type,
            "modality": modality,
            "top_label": result.top_label,
            "confidence": result.confidence,
            "clinical_history": "Not provided.",
            "technique": llm_report["technique"],
            "comparison": llm_report["comparison"],
            "image_quality": llm_report["image_quality"],
            "findings": llm_report.get("findings", "Findings not available."),
            "impression": llm_report.get("impression", "Impression not available."),
            "differential_diagnosis": llm_report["differential_diagnosis"],
            "recommendations": llm_report.get("recommendations", "Clinical correlation recommended."),
            "critical_communication": llm_report["critical_communication"],
            "patient_explanation": llm_report.get("patient_explanation", ""),
            "severity": result.severity,
            "all_scores": result.all_scores,
            "llm_provider": llm_provider,
            "disclaimer": DISCLAIMER,
            "generated_at": now.isoformat(),
            "is_low_confidence": is_low_confidence,
            "heatmap_target_label": heatmap_target_label,
            "secondary_findings": secondary_findings,
            "methodology": methodology,
            "limitations": limitations,
        }

    async def _call_gemini(self, user_prompt: str, image) -> Optional[dict]:
        """Call Gemini with inline image data for image-aware report generation."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._call_gemini_sync, user_prompt, image),
                timeout=40.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Image-aware report generation exceeded the 40-second safety limit")
            return None

    def _call_gemini_sync(self, user_prompt: str, image) -> Optional[dict]:
        try:
            import httpx

            image_rgb = image.convert("RGB")
            buffer = io.BytesIO()
            image_rgb.save(buffer, format="JPEG", quality=90)
            image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            prompt = f"""{SYSTEM_PROMPT}

ADDITIONAL SAFETY REQUIREMENTS:
- This output is an unsigned preliminary draft for clinician verification.
- If the image does not match the selected scan type, state that the image is not suitable for this workflow.
- Use the uploaded image for clinical observations. Never expose the classifier, its confidence, model agreement, or concordance in the report prose.
- For brain MRI, contrast status and pulse sequence are unknown. Do not call a lesion enhancing or make diffusion-, ADC-, FLAIR-, T1-, T2-, susceptibility-, or perfusion-specific claims.
- Return only the required JSON object.

{user_prompt}"""

            model_candidates = [
                "gemini-flash-latest",
                self.gemini_model,
                "gemini-2.5-flash",
            ]
            seen = set()
            model_candidates = [
                m for m in model_candidates
                if m and not (m in seen or seen.add(m))
            ][:2]

            last_error = None
            for model_name in model_candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": prompt},
                                    {
                                        "inlineData": {
                                            "mimeType": "image/jpeg",
                                            "data": image_b64,
                                        }
                                    },
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0,
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 2048,
                        },
                    }
                    response = httpx.post(
                        url,
                        headers={
                            "x-goog-api-key": self.gemini_key,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=httpx.Timeout(
                            18.0, connect=5.0, read=18.0, write=18.0, pool=5.0
                        ),
                    )

                    if response.status_code >= 500 or response.status_code in {404, 429}:
                        logger.warning(
                            f"Gemini model {model_name} returned {response.status_code}: {response.text[:300]}"
                        )
                        continue
                    response.raise_for_status()

                    data = response.json()
                    content = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text")
                    )
                    if not content:
                        logger.warning(f"Gemini model {model_name} returned no text.")
                        continue

                    result = self._parse_json_report(content)
                    logger.info(f"Gemini image-aware report generated successfully with {model_name}.")
                    return result
                except Exception as model_error:
                    last_error = model_error
                    logger.warning(f"Gemini model {model_name} failed: {model_error}")

            if last_error:
                raise last_error
            return None

        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")
            return None

    async def _call_groq(self, user_prompt: str) -> Optional[dict]:
        """Call Groq API with Llama 3.1 70B."""
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=self.groq_key)
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1800,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = self._parse_json_report(content)
            logger.info("Groq report generated successfully.")
            return result

        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")
            return None

    async def _call_claude(self, user_prompt: str) -> Optional[dict]:
        """Call Anthropic Claude API."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1800,
                        "system": SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_prompt}],
                        "temperature": 0,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["content"][0]["text"]
                    # Strip markdown code fences if present
                    content = content.strip()
                    if content.startswith("```"):
                        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
                    result = self._parse_json_report(content)
                    logger.info("Claude report generated successfully.")
                    return result

        except Exception as e:
            logger.warning(f"Claude API call failed: {e}")
        return None

    async def _call_openai(self, user_prompt: str) -> Optional[dict]:
        """Call OpenAI API."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.openai_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1800,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = self._parse_json_report(content)
            logger.info("OpenAI report generated successfully.")
            return result

        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}")
            return None

    def _generate_template_report(self, result, scan_type: str) -> dict:
        """Grounded fallback used when image-aware report generation is unavailable."""
        label = result.top_label
        score = float(result.confidence)
        secondary = [
            (name, float(value))
            for name, value in sorted(result.all_scores.items(), key=lambda item: -item[1])
            if name != label and float(value) >= 0.20
        ][:3]
        differential = (
            "; ".join(f"{name} (secondary classifier score {value * 100:.1f}%)" for name, value in secondary)
            if secondary else "None based on the available automated signal."
        )

        if scan_type == "chest_xray":
            technique = (
                "Single chest radiograph submitted for review. Projection, positioning, exposure "
                "parameters, and additional views were not provided."
            )
            image_quality = (
                "Limited assessment: a formal image-quality and anatomy-by-anatomy visual review "
                "could not be generated. Subtle findings may not be represented."
            )
            if label == "No Finding":
                findings = (
                    "LUNGS/AIRWAYS: No trained thoracic abnormality crossed the configured reporting threshold.\n"
                    "PLEURA: Not independently assessed in this fallback report.\n"
                    "CARDIOMEDIASTINAL SILHOUETTE: Not independently assessed in this fallback report.\n"
                    "HILA: Not independently assessed in this fallback report.\n"
                    "BONES/SOFT TISSUES: Not independently assessed in this fallback report.\n"
                    "SUPPORT DEVICES: Not independently assessed in this fallback report."
                )
                impression = (
                    "1. No model-supported thoracic abnormality above the reporting threshold.\n"
                    "2. This limited result does not establish a normal chest radiograph."
                )
            else:
                findings = (
                    f"LUNGS/AIRWAYS: Automated analysis produced its strongest signal for {label} "
                    f"({score * 100:.1f}%); independent visual confirmation is unavailable in this fallback report.\n"
                    "PLEURA: Not independently assessed except where represented by the classifier label above.\n"
                    "CARDIOMEDIASTINAL SILHOUETTE: Not independently assessed except where represented by the classifier label above.\n"
                    "HILA: Not independently assessed.\n"
                    "BONES/SOFT TISSUES: Not independently assessed.\n"
                    "SUPPORT DEVICES: Not independently assessed."
                )
                impression = (
                    f"1. Indeterminate chest radiograph with an automated signal for {label}; "
                    "confirmation on direct image review is required."
                )
            recommendations = (
                "Direct review of the original radiograph with clinical correlation is recommended. "
                "Obtain additional or follow-up imaging only when indicated by symptoms, examination, and the verified imaging finding."
            )
        elif scan_type == "brain_mri":
            technique = (
                "Single brain MRI image submitted for review. Sequence, plane, contrast status, and "
                "the remainder of the diagnostic MRI series were not provided."
            )
            image_quality = (
                "Severely limited examination because only one exported image is available. A complete "
                "assessment of the brain, diffusion, enhancement, hemorrhage, and small lesions is not possible."
            )
            if label == "No Tumor":
                findings = (
                    "BRAIN PARENCHYMA: No lesion in the three trained tumor categories was supported above the classification threshold.\n"
                    "EXTRA-AXIAL SPACES: Not completely assessable on the supplied image.\n"
                    "VENTRICLES/MASS EFFECT: Not completely assessable on the supplied image.\n"
                    "SELLA: Not completely assessable on the supplied image.\n"
                    "VISIBLE POSTERIOR FOSSA: Not completely assessable on the supplied image."
                )
                impression = (
                    "1. No model-supported glioma, meningioma, or pituitary tumor on this limited single-image analysis.\n"
                    "2. Other intracranial pathology and lesions not represented in the trained categories are not excluded."
                )
            else:
                findings = (
                    f"BRAIN PARENCHYMA: Automated analysis produced its strongest category signal for {label} "
                    f"({score * 100:.1f}%); independent lesion characterization is unavailable in this fallback report.\n"
                    "EXTRA-AXIAL SPACES: Not completely assessable on the supplied image.\n"
                    "VENTRICLES/MASS EFFECT: Not completely assessable on the supplied image.\n"
                    "SELLA: Not completely assessable beyond the category signal above.\n"
                    "VISIBLE POSTERIOR FOSSA: Not completely assessable on the supplied image."
                )
                impression = (
                    f"1. Indeterminate abnormality with an automated category signal for {label}; "
                    "the single supplied image is insufficient for a definitive tumor diagnosis or characterization."
                )
            recommendations = (
                "Review the complete diagnostic MRI examination, including all available sequences and prior studies. "
                "Further imaging or specialty referral should be based on verified imaging findings and the clinical presentation."
            )
        else:
            technique = "Single medical image submitted for limited review."
            image_quality = "Completeness and diagnostic adequacy cannot be established from the supplied input."
            findings = f"Automated analysis produced its strongest signal for {label} ({score * 100:.1f}%)."
            impression = f"1. Indeterminate automated finding: {label}."
            recommendations = "Direct clinician review and clinical correlation are recommended."

        return {
            "technique": technique,
            "comparison": "No prior imaging was supplied for comparison.",
            "image_quality": image_quality,
            "findings": findings,
            "impression": impression,
            "differential_diagnosis": differential,
            "recommendations": recommendations,
            "critical_communication": "No critical communication generated.",
            "patient_explanation": "",
        }

    def _generate_legacy_template_report(self, result, scan_type: str) -> dict:
        """
        Template-based report generation (fallback when no LLM API key).
        Produces clinically structured text without LLM enhancement.
        """
        label = result.top_label
        conf = result.confidence
        severity = result.severity
        is_low_confidence = getattr(result, "is_low_confidence", False)
        secondary_findings = getattr(result, "secondary_findings", [])
        heatmap_target_label = getattr(result, "heatmap_target_label", label)

        if scan_type == "chest_xray":
            if label == "No Finding":
                findings = (
                    "TECHNIQUE: Frontal chest radiograph was analyzed using the MedoraAI "
                    "EfficientNet-B4 classifier (15-class, NIH ChestX-ray14 label set). "
                    "Gradient-weighted Class Activation Mapping (Grad-CAM) was computed "
                    f"targeting the highest-scoring pathology class ({heatmap_target_label}) "
                    "to visualize model attention even in the absence of a positive finding.\n\n"
                    "FINDINGS: The AI classifier did not identify any model-supported acute "
                    "cardiopulmonary abnormality above the configured reporting threshold. "
                    "No pathology class produced a sigmoid activation score exceeding the "
                    "minimum confidence threshold. The Grad-CAM attention map shows where the "
                    "model focused its analysis, but no region triggered a pathology classification. "
                    "This automated result does not exclude subtle or early-stage pathology that "
                    "falls below model sensitivity."
                )
                impression = (
                    "No model-supported acute chest X-ray abnormality detected. "
                    "The AI attention map (Grad-CAM) did not localize a significant pathological region. "
                    "Clinical correlation with patient history and symptoms is recommended."
                )
                recommendations = (
                    "1. Radiologist review is recommended as clinically indicated.\n"
                    "2. Correlate with clinical symptoms, patient history, and physical examination.\n"
                    "3. Consider repeat imaging if clinical suspicion remains high despite negative AI result.\n"
                    "4. This AI system cannot detect all pathologies; absence of a finding does not exclude disease."
                )
            else:
                # Build secondary findings text
                secondary_text = ""
                if secondary_findings:
                    sec_items = [f"{sf['label']} ({sf['score'] * 100:.0f}%)" for sf in secondary_findings[:3]]
                    secondary_text = (
                        f"\n\nDIFFERENTIAL CONSIDERATIONS: The model also produced elevated "
                        f"scores for: {', '.join(sec_items)}. These may represent co-existing "
                        f"pathology or classification overlap and should be considered during "
                        f"radiologist review."
                    )

                confidence_note = ""
                if is_low_confidence:
                    confidence_note = (
                        " IMPORTANT: The model confidence for this finding is below 50%, "
                        "indicating significant uncertainty. The finding should be interpreted "
                        "with caution and requires careful radiologist correlation. "
                        "Low-confidence AI results have higher rates of false positives."
                    )

                findings = (
                    "TECHNIQUE: Frontal chest radiograph was analyzed using the MedoraAI "
                    "EfficientNet-B4 classifier (15-class, NIH ChestX-ray14 label set). "
                    "Gradient-weighted Class Activation Mapping (Grad-CAM) was computed "
                    f"targeting the {heatmap_target_label} class to visualize the region of "
                    "model attention most relevant to the primary finding.\n\n"
                    f"FINDINGS: The AI chest X-ray model produced findings suggestive of "
                    f"{label} with a sigmoid activation confidence of {conf * 100:.1f}%. "
                    f"The Grad-CAM attention map highlights the region that contributed most "
                    f"to this classification — this represents actual gradient-weighted "
                    f"neural network activations, not a simulated overlay. "
                    f"The highlighted region should be correlated with clinical findings and "
                    f"is NOT equivalent to radiologist-confirmed lesion localization. "
                    f"The findings are assessed as {severity.lower()} based on model "
                    f"confidence scoring.{confidence_note}{secondary_text}"
                )
                impression = (
                    f"AI findings suggestive of {label} "
                    f"(confidence: {conf * 100:.1f}%, severity: {severity}). "
                    + ("Low model confidence — interpret with caution. " if is_low_confidence else "")
                    + "Clinical correlation with patient history, symptoms, and physical "
                    "examination is essential. Radiologist review required before clinical action."
                )
                recommendations = (
                    f"1. Formal radiologist review and interpretation is required.\n"
                    f"2. Correlate with clinical history, symptoms, and physical examination findings.\n"
                    f"3. {'Urgent clinical attention may be warranted given severity assessment. ' if severity == 'Severe' else ''}"
                    f"Consider follow-up imaging as clinically indicated.\n"
                    f"4. If findings are discordant with clinical presentation, consider "
                    f"alternative diagnoses or additional imaging modalities.\n"
                    f"5. AI classification should not be used as the sole basis for clinical decisions."
                )

        elif scan_type == "brain_mri":
            technique = (
                "TECHNIQUE: Brain MRI was analyzed using the MedoraAI EfficientNetB3 "
                "4-class tumor classifier (Glioma, Meningioma, No Tumor, Pituitary) with "
                "multi-scale Grad-CAM++ explainability. Input preprocessing includes brain "
                "contour cropping and EfficientNet-specific normalization at 260×260 resolution. "
                "Test-Time Augmentation was applied for improved accuracy."
            )

            # Build differential text from all scores
            sorted_scores = sorted(result.all_scores.items(), key=lambda x: -x[1])
            diff_items = [f"{s[0]} ({s[1] * 100:.0f}%)" for s in sorted_scores if s[1] >= 0.05]
            diff_text = ", ".join(diff_items) if diff_items else "No significant scores"

            if label == "No Tumor":
                findings = (
                    f"{technique}\n\n"
                    "FINDINGS: Brain MRI was reviewed. The AI classifier did not identify any "
                    "model-supported intracranial mass lesion. All tumor class probabilities "
                    "(Glioma, Meningioma, Pituitary) remained below the classification threshold. "
                    f"Class distribution: {diff_text}. "
                    "The Grad-CAM++ attention map did not localize a significant region of "
                    "abnormality. This automated result does not exclude all intracranial "
                    "pathology, particularly small, diffuse, or non-enhancing lesions outside "
                    "the model's training distribution."
                )
                impression = (
                    "No evidence of intracranial tumor on AI-assisted MRI analysis "
                    "(4-class EfficientNetB3 classifier). Clinical correlation recommended."
                )
                recommendations = (
                    "1. Routine clinical follow-up as indicated.\n"
                    "2. Radiologist review recommended if clinical symptoms persist.\n"
                    "3. AI classification has limited sensitivity for small, diffuse, or "
                    "non-enhancing lesions.\n"
                    "4. Consider contrast-enhanced MRI if clinical suspicion remains high."
                )
            elif label == "Glioma":
                findings = (
                    f"{technique}\n\n"
                    f"FINDINGS: Brain MRI analysis reveals findings suggestive of a glioma "
                    f"(AI confidence: {conf * 100:.1f}%). Gliomas are primary brain tumors "
                    f"arising from glial cells and may range from low-grade (WHO Grade I-II) "
                    f"to high-grade (WHO Grade III-IV, glioblastoma). "
                    f"The Grad-CAM++ attention map highlights the region contributing most "
                    f"to this classification. The AI model does not determine tumor grade, "
                    f"molecular subtype, or extent of infiltration. "
                    f"Differential scores: {diff_text}. "
                    f"The findings are assessed as {severity.lower()} based on model "
                    f"confidence scoring."
                )
                impression = (
                    f"AI findings suggestive of glioma "
                    f"(confidence: {conf * 100:.1f}%, severity: {severity}). "
                    f"URGENT neurosurgical and neuroradiology consultation recommended. "
                    f"Tumor grading and molecular characterization require histopathological analysis."
                )
                recommendations = (
                    "1. URGENT: Neurosurgical consultation recommended.\n"
                    "2. Formal neuroradiology review with contrast-enhanced MRI (T1 post-Gd, "
                    "FLAIR, DWI, perfusion) for characterization and grading.\n"
                    "3. Correlation with clinical symptoms and neurological examination is essential.\n"
                    "4. Consider advanced imaging (MR spectroscopy, perfusion) for grading.\n"
                    "5. Stereotactic biopsy or surgical planning if lesion is confirmed."
                )
            elif label == "Meningioma":
                findings = (
                    f"{technique}\n\n"
                    f"FINDINGS: Brain MRI analysis reveals findings suggestive of a meningioma "
                    f"(AI confidence: {conf * 100:.1f}%). Meningiomas are typically benign "
                    f"(WHO Grade I) extra-axial tumors arising from the meninges, often "
                    f"well-circumscribed with dural attachment. "
                    f"The Grad-CAM++ attention map highlights the region contributing most "
                    f"to this classification. The AI model does not determine tumor grade, "
                    f"size, or dural involvement. "
                    f"Differential scores: {diff_text}. "
                    f"The findings are assessed as {severity.lower()} based on model "
                    f"confidence scoring."
                )
                impression = (
                    f"AI findings suggestive of meningioma "
                    f"(confidence: {conf * 100:.1f}%, severity: {severity}). "
                    f"Neuroradiology review recommended for confirmation and characterization."
                )
                recommendations = (
                    "1. Neuroradiology review with contrast-enhanced MRI for confirmation.\n"
                    "2. Assess for dural tail sign, calcification, and extra-axial characteristics.\n"
                    "3. Neurosurgical consultation for management planning.\n"
                    "4. Consider observation with serial imaging for small, asymptomatic lesions.\n"
                    "5. Correlate with clinical symptoms and neurological examination."
                )
            elif label == "Pituitary":
                findings = (
                    f"{technique}\n\n"
                    f"FINDINGS: Brain MRI analysis reveals findings suggestive of a pituitary "
                    f"tumor (AI confidence: {conf * 100:.1f}%). Pituitary tumors are typically "
                    f"adenomas located in the sellar/suprasellar region, and may be functioning "
                    f"(hormone-secreting) or non-functioning. "
                    f"The Grad-CAM++ attention map highlights the region contributing most "
                    f"to this classification. The AI model does not determine tumor size, "
                    f"hormonal activity, or suprasellar extension. "
                    f"Differential scores: {diff_text}. "
                    f"The findings are assessed as {severity.lower()} based on model "
                    f"confidence scoring."
                )
                impression = (
                    f"AI findings suggestive of pituitary tumor "
                    f"(confidence: {conf * 100:.1f}%, severity: {severity}). "
                    f"Endocrinology and neuroradiology consultation recommended."
                )
                recommendations = (
                    "1. Endocrinology consultation for hormonal evaluation (prolactin, GH, "
                    "ACTH, TSH, gonadotropins).\n"
                    "2. Dedicated pituitary MRI with thin-section coronal T1 pre/post-contrast.\n"
                    "3. Visual field testing (perimetry) to assess for chiasmal compression.\n"
                    "4. Neurosurgical consultation if mass effect or hormonal excess confirmed.\n"
                    "5. Correlate with clinical symptoms (headache, visual changes, hormonal symptoms)."
                )
            else:
                # Fallback for any unexpected label
                findings = (
                    f"{technique}\n\n"
                    f"FINDINGS: Brain MRI analysis reveals findings classified as {label} "
                    f"(AI confidence: {conf * 100:.1f}%). "
                    f"Differential scores: {diff_text}. "
                    f"The findings are assessed as {severity.lower()} based on model "
                    f"confidence scoring."
                )
                impression = (
                    f"AI findings suggest {label} "
                    f"(confidence: {conf * 100:.1f}%, severity: {severity}). "
                    f"Neuroradiology review recommended."
                )
                recommendations = (
                    "1. Neuroradiology review recommended.\n"
                    "2. Correlate with clinical symptoms and neurological examination.\n"
                    "3. Consider contrast-enhanced MRI for further characterization."
                )
        else:
            findings = f"AI analysis identifies {label} with {conf * 100:.1f}% confidence."
            impression = f"Findings suggestive of {label}. Severity: {severity}."
            recommendations = "Clinical correlation recommended."

        return {
            "findings": findings,
            "impression": impression,
            "recommendations": recommendations,
        }

    @staticmethod
    def _parse_json_report(content: str) -> dict:
        """Parse provider JSON while tolerating accidental code fences."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Report response must be a JSON object")
        fields = (
            "technique", "comparison", "image_quality", "findings", "impression",
            "differential_diagnosis", "recommendations", "critical_communication",
            "patient_explanation",
        )
        report = {field: str(parsed.get(field, "")).strip() for field in fields}
        if not report["findings"] or not report["impression"]:
            raise ValueError("Report response is missing required clinical sections")
        return report

    @staticmethod
    def _complete_report_sections(report: dict, scan_type: str) -> dict:
        """Normalize provider and legacy template output into the clinical schema."""
        default_technique = (
            "Single brain MRI image submitted; sequence, plane, contrast status, and complete series are not provided."
            if scan_type == "brain_mri"
            else "Single chest radiograph submitted; projection, positioning, and additional views are not provided."
        )
        defaults = {
            "technique": default_technique,
            "comparison": "No prior imaging was supplied for comparison.",
            "image_quality": "Diagnostic adequacy is limited by review of a single supplied image.",
            "findings": "Findings are not available.",
            "impression": "No impression was generated.",
            "differential_diagnosis": "None based on the supplied image.",
            "recommendations": "Clinical correlation and direct image review are recommended.",
            "critical_communication": "No critical communication generated.",
            "patient_explanation": "",
        }
        return {
            key: str(report.get(key) or fallback).strip()
            for key, fallback in defaults.items()
        }

    @staticmethod
    def _sanitize_generated_clinical_text(value: str, scan_type: str) -> str:
        """Remove machine-facing and unsupported acquisition claims from generated prose."""
        text = str(value or "").strip()
        if not text:
            return text

        def drop_sentences(source: str, pattern: re.Pattern) -> str:
            cleaned_lines = []
            for line in source.splitlines() or [source]:
                kept = [
                    sentence
                    for sentence in re.split(r"(?<=[.!?])\s+", line.strip())
                    if sentence and not pattern.search(sentence)
                ]
                if kept:
                    cleaned_lines.append(" ".join(kept))
            return "\n".join(cleaned_lines)

        # A provider occasionally appends model agreement to an otherwise useful
        # clinical sentence. Remove the clause while preserving the observation.
        text = re.sub(
            r",?\s*(?:demonstrating|showing|with)?\s*concordance\s+with\s+(?:the\s+)?"
            r"(?:supportive\s+)?(?:classifier|model)(?:\s+(?:finding|output|result))?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r",?\s*(?:as\s+)?(?:supported|identified|predicted)\s+by\s+(?:the\s+)?"
            r"(?:classifier|model|automated analysis)",
            "",
            text,
            flags=re.IGNORECASE,
        )

        if scan_type == "brain_mri":
            # There is no DICOM series metadata at this stage. Keep the lesion
            # description, but strip acquisition-dependent adjectives and claims.
            text = re.sub(
                r"\b(?:avidly|mildly|moderately|strongly|homogeneously|heterogeneously)?\s*enhancing\b",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\bno\s+(?:abnormal\s+)?enhancement\b|\black\s+of\s+enhancement\b",
                "contrast behavior cannot be assessed",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\b(?:post[- ]?contrast|gadolinium(?:-enhanced)?|contrast uptake|enhancement)\b",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\b(?:axial|coronal|sagittal)\s+(?:image|slice|view)\b",
                "supplied image",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"\bmeasur(?:es|ing)\s+(?:approximately\s+)?\d+(?:\.\d+)?\s*(?:mm|cm)\b",
                "cannot be reliably measured on the supplied image",
                text,
                flags=re.IGNORECASE,
            )

            # Drop whole sentences that still assert a sequence-dependent
            # observation. A recommendation may name a future sequence, so this
            # helper is applied only to generated findings/impression/differential.
            unsupported_sequence = re.compile(
                r"\b(?:restricted diffusion|diffusion restriction|ADC|DWI|FLAIR|SWI|"
                r"T1[- ]weighted|T2[- ]weighted|susceptibility|perfusion)\b",
                re.IGNORECASE,
            )
            text = drop_sentences(text, unsupported_sequence)

        # Clinical prose must read like a report, not an explanation of the
        # software. If a residual machine-facing sentence remains, omit it.
        machine_facing = re.compile(
            r"\b(?:classifier|model[- ]supported|model confidence|model agreement|"
            r"automated (?:analysis|signal|result|classification|finding)|AI|"
            r"artificial intelligence|Grad-CAM|attention map|heatmap)\b",
            re.IGNORECASE,
        )
        text = drop_sentences(text, machine_facing)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(
            r",\s+(?=(?:mass|lesion|abnormality|collection|opacity)\b)",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        anatomy_labels = (
            "LUNGS/AIRWAYS|PLEURA|CARDIOMEDIASTINAL SILHOUETTE|HILA|"
            "BONES/SOFT TISSUES|SUPPORT DEVICES|BRAIN PARENCHYMA|"
            "EXTRA-AXIAL SPACES|VENTRICLES/MASS EFFECT|SELLA|"
            "VISIBLE POSTERIOR FOSSA"
        )
        text = re.sub(
            rf"(?<!^)\s+(?=(?:{anatomy_labels}):)",
            "\n",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s+([,.;:])", r"\1", text)
        return text.strip(" ,;")

    @classmethod
    def _ground_report_to_available_input(cls, report: dict, scan_type: str) -> dict:
        """Apply deterministic study metadata and a final clinical grounding gate."""
        grounded = dict(report)
        grounded["comparison"] = "No prior imaging was supplied for comparison."

        if scan_type == "brain_mri":
            grounded["technique"] = (
                "Single uploaded 2D brain MRI image. Imaging plane, pulse sequence, "
                "contrast status, and the complete multiplanar series are not available."
            )
            grounded["image_quality"] = (
                "Limited diagnostic assessment because only one exported image is available. "
                "Full brain coverage, sequence-dependent tissue characteristics, contrast "
                "behavior, hemorrhage, and small lesions cannot be assessed reliably."
            )
        elif scan_type == "chest_xray":
            grounded["technique"] = (
                "Single uploaded frontal chest radiograph. Projection, positioning, exposure "
                "parameters, and additional views are not available."
            )
            grounded["image_quality"] = (
                "Interpretation is limited to one exported radiograph; projection, positioning, "
                "exposure parameters, and the complete examination cannot be independently verified."
            )

        if not str(grounded.get("recommendations") or "").strip():
            grounded["recommendations"] = (
                "Review the complete source examination and correlate with the clinical presentation."
            )
        if not str(grounded.get("critical_communication") or "").strip():
            grounded["critical_communication"] = "No critical communication generated."

        for field in ("findings", "impression", "differential_diagnosis"):
            cleaned = cls._sanitize_generated_clinical_text(
                grounded.get(field, ""), scan_type
            )
            safe_fallbacks = {
                "findings": (
                    "A complete visual interpretation cannot be provided from the available "
                    "single image. Direct review of the source examination is required."
                ),
                "impression": (
                    "1. Limited single-image assessment; definitive interpretation requires "
                    "review of the complete source examination."
                ),
                "differential_diagnosis": (
                    "No reliable differential can be established from the supplied image alone."
                ),
            }
            grounded[field] = cleaned or safe_fallbacks[field]

        return grounded

    @staticmethod
    def _is_chest_report_supported(report: dict, result, allow_visual_details: bool = False) -> bool:
        """Reject chest reports that mention unsupported model labels or invented specifics."""
        try:
            from services.chest_classifier import CLASS_LABELS, NO_FINDING_LABEL
        except Exception:
            return True

        text = " ".join(
            str(report.get(key, ""))
            for key in (
                "findings", "impression", "differential_diagnosis",
                "recommendations", "critical_communication",
            )
        ).lower()

        supported = {result.top_label.lower(), NO_FINDING_LABEL.lower()}
        supported.update(
            label.lower()
            for label, score in result.all_scores.items()
            if score >= 0.20
        )

        for label in CLASS_LABELS:
            normalized = label.lower()
            if normalized in text and normalized not in supported:
                return False

        if allow_visual_details:
            return True

        blocked_terms = [
            "right upper lobe", "right middle lobe", "right lower lobe",
            "left upper lobe", "left lower lobe", "apical", "basilar",
            " cm", " mm", "tube", "line placement", "prior study",
        ]
        return not any(term in text for term in blocked_terms)

    # ============================================================
    # PATIENT-FRIENDLY SUMMARY
    # ============================================================

    PATIENT_SUMMARY_PROMPT = """Convert the clinical imaging draft below into a safe English explanation for the patient.

RULES:
- Use calm, direct, everyday English and short sentences.
- Preserve uncertainty. A suspected finding must remain suspected; never turn it into a confirmed diagnosis.
- Clearly separate: what the image may show, what that could mean, limitations, and the next step.
- Do not add symptoms, prognosis, treatment, urgency, or reassurance that is absent from the report.
- Include urgent-care advice only when the report's critical communication or recommendations support it.
- Do not mention model/provider names, prompts, confidence scores, heatmaps, or technical implementation.
- Explain essential medical terms once in plain language instead of deleting information the patient needs.
- Do not say the scan is normal when the report only says that no trained abnormality was detected.
- Use these four headings exactly: What the scan may show; What this means; What happens next; Important limitation.
- Write 4 short paragraphs, one under each heading. Do not use markdown bullets or JSON.
"""

    LANGUAGE_CODES = {
        "English": "en-IN", "Hindi": "hi-IN", "Tamil": "ta-IN",
        "Telugu": "te-IN", "Marathi": "mr-IN", "Bengali": "bn-IN",
        "Kannada": "kn-IN", "Gujarati": "gu-IN", "Malayalam": "ml-IN",
        "Punjabi": "pa-IN", "Urdu": "ur-IN",
    }

    async def generate_patient_report(
        self,
        report_data: dict,
        language: str = "English",
    ) -> str:
        """
        Generate a patient-friendly summary of the medical report.
        
        Creates a grounded English explanation first, then translates that fixed
        text. Translation is deliberately separated from clinical generation.
        
        Args:
            report_data: The full clinical report data dict
            language: Target language (e.g., "Hindi", "Tamil", "English")
        
        Returns:
            Plain text patient-friendly summary string
        """
        requested_language = language if language in self.LANGUAGE_CODES else "English"
        english = await self._generate_patient_explanation_english(report_data)
        if requested_language == "English":
            return english

        translated = None
        if self.sarvam_key and not self.sarvam_translation_disabled:
            translated = await self._translate_with_sarvam(
                english, self.LANGUAGE_CODES[requested_language]
            )
        if translated is None and self.gemini_key:
            translated = await self._translate_with_gemini(english, requested_language)
        if translated:
            return translated

        return f"[{requested_language} translation is temporarily unavailable.]\n\n{english}"

    async def _generate_patient_explanation_english(self, report_data: dict) -> str:
        stored = str(report_data.get("patient_explanation") or "").strip()
        if stored:
            return stored

        scan_type = report_data.get("scan_type", "medical scan")
        scan_label = "brain MRI image" if scan_type == "brain_mri" else "chest X-ray"
        return self._patient_summary_template(report_data, scan_label)

    async def _translate_with_sarvam(self, text: str, target_code: str) -> Optional[str]:
        """Translate fixed English patient text; scan data is never sent here."""
        try:
            import httpx

            chunks = self._chunk_translation_text(text)
            translated_chunks = []
            async with httpx.AsyncClient(timeout=12.0) as client:
                for chunk in chunks:
                    response = await client.post(
                        "https://api.sarvam.ai/translate",
                        headers={
                            "api-subscription-key": self.sarvam_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "input": chunk,
                            "source_language_code": "en-IN",
                            "target_language_code": target_code,
                            "model": self.sarvam_translate_model,
                            "mode": "formal",
                        },
                    )
                    response.raise_for_status()
                    translated = str(response.json().get("translated_text", "")).strip()
                    if not translated:
                        raise ValueError("Translation response contained no text")
                    translated_chunks.append(translated)
            logger.info("Patient explanation translated to %s", target_code)
            return "\n\n".join(translated_chunks)
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {401, 402, 403}:
                self.sarvam_translation_disabled = True
                logger.warning(
                    "Primary translation disabled until backend restart after HTTP %s",
                    status_code,
                )
            logger.warning("Primary patient translation failed: %s", exc)
            return None

    async def _translate_with_gemini(self, text: str, language: str) -> Optional[str]:
        prompt = f"""Translate the patient explanation below from English into {language}.
Preserve all four headings, meaning, uncertainty, paragraph order, and safety language exactly.
Do not add, remove, summarize, diagnose, or explain anything. Output only the translation.

{text}"""
        return await self._generate_gemini_text(prompt, temperature=0.0, max_output_tokens=1400)

    async def _generate_gemini_text(
        self, prompt: str, temperature: float, max_output_tokens: int,
    ) -> Optional[str]:
        try:
            import httpx

            preferred_models = list(dict.fromkeys([
                "gemini-flash-latest",
                "gemini-2.5-flash",
                self.gemini_model,
            ]))
            async with httpx.AsyncClient(timeout=12.0) as client:
                for model_name in preferred_models[:2]:
                    try:
                        response = await client.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                            headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
                            json={
                                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                "generationConfig": {
                                    "temperature": temperature,
                                    "maxOutputTokens": max_output_tokens,
                                },
                            },
                        )
                        response.raise_for_status()
                        data = response.json()
                        output = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if output:
                            return output
                    except Exception as exc:
                        logger.warning("Patient text generation attempt failed: %s", exc)
        except Exception as exc:
            logger.warning("Patient text service unavailable: %s", exc)
        return None

    @staticmethod
    def _chunk_translation_text(text: str, limit: int = 1900) -> list[str]:
        """Split long text at paragraph/sentence boundaries for the 2,000-char API limit."""
        import re

        if len(text) <= limit:
            return [text]
        units = re.split(r"(?<=\.)\s+|\n\s*\n", text.strip())
        chunks: list[str] = []
        current = ""
        for unit in (part.strip() for part in units if part.strip()):
            if len(unit) > limit:
                pieces = [unit[index:index + limit] for index in range(0, len(unit), limit)]
            else:
                pieces = [unit]
            for piece in pieces:
                candidate = f"{current}\n\n{piece}".strip() if current else piece
                if len(candidate) > limit and current:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _patient_summary_template(report_data: dict, scan_type: str) -> str:
        """Immediate plain-English explanation that preserves diagnostic uncertainty."""
        label = str(report_data.get("top_label") or "Unknown").strip()
        explanations = {
            "No Finding": "No condition from the chest patterns checked by this system was strongly identified.",
            "Atelectasis": "Part of a lung may not be expanding as fully as expected.",
            "Cardiomegaly": "The outline of the heart may look larger than expected on this image.",
            "Effusion": "There may be fluid in the space around a lung.",
            "Pleural Effusion": "There may be fluid in the space around a lung.",
            "Infiltration": "An area of the lung may look denser than expected, which has several possible causes.",
            "Lung Opacity": "An area of the lung may look denser than expected, which has several possible causes.",
            "Mass": "The image may contain a larger focal area that needs direct medical review.",
            "Lung Lesion": "The image may contain a focal area that needs direct medical review.",
            "Nodule": "The image may contain a small rounded spot that needs direct medical review.",
            "Pneumonia": "The image may show a lung pattern that can occur with infection.",
            "Pneumothorax": "There may be air around a lung, which can prevent the lung from fully expanding.",
            "Consolidation": "Part of a lung may be filled with fluid or inflammatory material rather than air.",
            "Edema": "There may be extra fluid within the lungs.",
            "Emphysema": "The lungs may show changes associated with long-term damage to their air spaces.",
            "Fibrosis": "The lungs may show areas of scarring.",
            "Fracture": "A visible bone may show a possible break.",
            "No Tumor": "No pattern from the three brain-tumor groups checked by this system was strongly identified.",
            "Glioma": "The image may show a growth pattern arising from brain tissue, sometimes called a glioma.",
            "Meningioma": "The image may show a growth pattern arising from the covering around the brain, sometimes called a meningioma.",
            "Pituitary": "The image may show a growth near the small hormone-producing gland beneath the brain.",
        }
        finding = explanations.get(
            label,
            "The image contains a possible finding that needs direct review by your treating doctor.",
        )
        critical = str(report_data.get("critical_communication") or "").lower()
        if critical and "no critical" not in critical:
            next_step = (
                "The report marks this for prompt communication. Contact your treating team now so they can "
                "review the scan and tell you what action is appropriate."
            )
        else:
            next_step = (
                "Please discuss the complete scan with your treating doctor. They will compare this result with "
                "your symptoms, examination, and any earlier scans before deciding whether another test is needed."
            )
        limitation = (
            "Only one brain MRI image was available here, not the complete set of MRI images. Important details "
            "may therefore be missing."
            if report_data.get("scan_type") == "brain_mri"
            else "This explanation is based on the supplied chest image and the limited conditions the system checks. "
            "Subtle or unrelated problems may not be represented."
        )
        return (
            f"What the scan may show\n{finding}\n\n"
            f"What this means\nThis is a possible imaging finding, not a confirmed diagnosis. The label “{label}” "
            "does not by itself determine how serious the condition is or what treatment you need.\n\n"
            f"What happens next\n{next_step}\n\n"
            f"Important limitation\n{limitation}"
        )

    async def generate_patient_summary(
        self,
        report_data: dict,
        language: str = "English",
    ) -> str:
        """Backward-compatible alias for older callers."""
        return await self.generate_patient_report(report_data, language)
