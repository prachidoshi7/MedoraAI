"""
MedoraAI — LLM-Powered Clinical Report Engine
Generates professional radiology reports by sending model output to LLM APIs.

Flow: Image + Model Output → Clinical Prompt → LLM API → Structured Report
Provider priority: Gemini multimodal → Groq → Claude → OpenAI → Template fallback
"""

import asyncio
import base64
import io
import json
import logging
from datetime import datetime
from typing import Optional, Union

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


SYSTEM_PROMPT = """You are MedoraAI's image-aware clinical report assistant.
Behave like a careful senior radiologist writing a preliminary decision-support draft.
You receive:
1. the uploaded medical image when a multimodal provider is available,
2. the local ML classifier output,
3. model confidence scores and severity metadata.

RULES:
- Treat the uploaded image as primary visual context and the ML output as supporting context.
- Write in professional radiology report language with clear clinical reasoning.
- Use hedging language: "consistent with", "suggestive of", "cannot exclude", "findings may represent".
- Do NOT make definitive diagnoses; this is a decision-support draft.
- Do NOT claim board-certified radiologist review has occurred.
- Do NOT fabricate patient history, symptoms, comparisons, measurements, or prior studies.
- Do NOT invent anatomical locations, laterality, lobes, measurements, devices, comparisons, or clinical history
- Do NOT mention a disease, finding, or complication unless supported by the image or the ML output.
- If the ML confidence is low, explicitly state uncertainty and avoid strong conclusions.
- Explain how the image appearance and ML output relate, but never overrule safety uncertainty.
- Keep each section detailed but concise: 4-7 well-constructed sentences.
- Findings should describe visual observations, ML context, uncertainty, and limitations.
- Impression should be a prioritized summary with differential-style wording when appropriate.
- Recommendations should be practical: radiologist review, clinical correlation, follow-up imaging, or urgent care only when justified.

You MUST output ONLY valid JSON with exactly these three keys:
{
  "findings": "Detailed radiological findings text with image-aware reasoning...",
  "impression": "Prioritized clinical impression summary...",
  "recommendations": "Recommended follow-up actions and safety notes..."
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

        logger.info(f"LLMReportEngine initialized. Available providers: {providers}")

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
            return f"""SCAN TYPE: Chest X-Ray (single uploaded image)
IMAGING MODALITY: Digital Radiography

AI MODEL OUTPUT:
- Primary Finding: {result.top_label} (Confidence: {result.confidence * 100:.1f}%)
- Severity Assessment: {result.severity}
- Supported Classification Scores (20% or higher only):
{scores_text}

STRICT CHEST REPORTING RULES:
- If image input is available, use it to describe visible radiographic patterns and whether they agree with the ML output.
- If image input is not available, do not name any chest disease that is not listed above.
- Do not state precise location, side, lobe, size, tubes, lines, cardiomediastinal enlargement, effusion, or pneumothorax unless directly supported by the image or ML output.
- If the primary finding is "No Finding", state that no model-supported acute abnormality is identified.
- Mention that Grad-CAM localization is an AI attention map, not a radiologist-confirmed lesion.
- Clearly separate "model-supported" statements from visual uncertainty.

Generate a detailed but conservative structured radiology report that integrates the uploaded image when available and the ML output above."""

        elif scan_type == "brain_mri":
            # Format all 4-class scores for context
            scores_text = "\n".join(
                f"  - {label}: {score * 100:.1f}%"
                for label, score in sorted(result.all_scores.items(), key=lambda x: -x[1])
            )
            tumor_type = getattr(result, 'tumor_type', result.top_label.lower())
            return f"""SCAN TYPE: Brain MRI
IMAGING MODALITY: Magnetic Resonance Imaging

AI MODEL OUTPUT (EfficientNetB3, 4-class classifier):
- Primary Finding: {result.top_label} (Confidence: {result.confidence * 100:.1f}%)
- Severity Assessment: {result.severity}
- All Classification Scores:
{scores_text}

CLASS DEFINITIONS:
- Glioma: Primary brain tumor arising from glial cells; includes astrocytomas, oligodendrogliomas, glioblastomas
- Meningioma: Typically benign tumor arising from meninges; usually well-circumscribed, extra-axial
- No Tumor: No model-supported mass lesion identified
- Pituitary: Tumor of the pituitary gland (sellar/suprasellar region); usually adenoma

STRICT BRAIN MRI REPORTING RULES:
- If image input is available, use it to describe visible MRI patterns and whether they agree with the ML output.
- The model classifies into exactly 4 categories. Do not speculate about tumor grade, molecular subtype, or histology beyond what the class label implies.
- Do not invent exact size, sequence findings, enhancement patterns, diffusion restriction, edema, or mass effect unless visually supported by the image.
- If the primary finding is "No Tumor", state that no model-supported mass lesion is identified, while recommending radiologist review.
- If a specific tumor type is suggested (Glioma, Meningioma, or Pituitary), use cautious language appropriate to that tumor type and recommend formal neuroradiology review.
- Mention the differential — note the scores for other tumor types if they are significant (>10%).

Generate a detailed but conservative structured neuroradiology report that integrates the uploaded image when available and the ML output above."""

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
            "(3) Grad-CAM attention maps indicate model focus areas but do not constitute "
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
            "findings": llm_report.get("findings", "Findings not available."),
            "impression": llm_report.get("impression", "Impression not available."),
            "recommendations": llm_report.get("recommendations", "Clinical correlation recommended."),
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
        return await asyncio.to_thread(self._call_gemini_sync, user_prompt, image)

    def _call_gemini_sync(self, user_prompt: str, image) -> Optional[dict]:
        try:
            import httpx

            image_rgb = image.convert("RGB")
            buffer = io.BytesIO()
            image_rgb.save(buffer, format="JPEG", quality=90)
            image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            prompt = f"""{SYSTEM_PROMPT}

ADDITIONAL SAFETY REQUIREMENTS:
- You are not replacing a clinician or radiologist.
- If the image does not match the selected scan type, state that the image is not suitable for this workflow.
- Use the uploaded image to enrich the report, but keep the ML model output visible in your reasoning.
- Return only the required JSON object.

{user_prompt}"""

            model_candidates = [
                self.gemini_model,
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-2.0-flash",
                "gemini-2.5-flash",
            ]
            seen = set()
            model_candidates = [m for m in model_candidates if m and not (m in seen or seen.add(m))]

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
                        },
                    }
                    response = httpx.post(
                        url,
                        headers={
                            "x-goog-api-key": self.gemini_key,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=8.0,
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
                max_tokens=500,
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
                        "max_tokens": 500,
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
                max_tokens=500,
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
        return {
            "findings": str(parsed.get("findings", "")).strip(),
            "impression": str(parsed.get("impression", "")).strip(),
            "recommendations": str(parsed.get("recommendations", "")).strip(),
        }

    @staticmethod
    def _is_chest_report_supported(report: dict, result, allow_visual_details: bool = False) -> bool:
        """Reject chest reports that mention unsupported model labels or invented specifics."""
        try:
            from services.chest_classifier import CLASS_LABELS, NO_FINDING_LABEL
        except Exception:
            return True

        text = " ".join(
            str(report.get(key, ""))
            for key in ("findings", "impression", "recommendations")
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

    PATIENT_SUMMARY_PROMPT = """You are a compassionate medical communicator.
Your job is to explain medical findings to a patient in simple, clear language.

RULES:
- Write in {language} language.
- Use simple, everyday words. No medical jargon.
- Be empathetic and reassuring but honest.
- Do NOT mention AI, machine learning, neural networks, model names, or confidence scores.
- Do NOT mention specific technical terms like "EfficientNet", "Grad-CAM", "softmax", etc.
- Explain what the finding means for the patient's health in practical terms.
- If the finding is serious, gently explain why they should see a doctor soon.
- If no problem was found, reassure them but recommend regular checkups.
- Keep it concise: 3-5 short paragraphs.
- Write directly to the patient using "you/your" language.
- End with a brief, kind encouragement.

Do NOT output JSON. Output plain text only."""

    async def generate_patient_report(
        self,
        report_data: dict,
        language: str = "English",
    ) -> str:
        """
        Generate a patient-friendly summary of the medical report.
        
        Creates a simplified, non-technical explanation in the patient's
        chosen language, with a safe local fallback.
        
        Args:
            report_data: The full clinical report data dict
            language: Target language (e.g., "Hindi", "Tamil", "English")
        
        Returns:
            Plain text patient-friendly summary string
        """
        findings = report_data.get("findings", "")
        impression = report_data.get("impression", "")
        top_label = report_data.get("top_label", "Unknown")
        severity = report_data.get("severity", "")
        scan_type = report_data.get("scan_type", "medical scan")
        
        scan_type_label = "brain MRI scan" if scan_type == "brain_mri" else "chest X-ray"

        user_prompt = f"""The patient had a {scan_type_label}. Here are the clinical findings:

FINDING: {top_label}
SEVERITY: {severity}

CLINICAL REPORT:
{findings}

IMPRESSION:
{impression}

Please explain these findings to the patient in {language} language, using simple everyday words they can understand. 
Be compassionate but honest. Do not use any medical terminology or technical language."""

        prompt_with_lang = self.PATIENT_SUMMARY_PROMPT.replace("{language}", language)

        # Try Gemini first (text-only for patient summary)
        if self.gemini_key:
            try:
                import httpx
                
                for model_name in self.gemini_models:
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                        payload = {
                            "contents": [
                                {"role": "user", "parts": [{"text": prompt_with_lang + "\n\n" + user_prompt}]}
                            ],
                            "generationConfig": {
                                "temperature": 0.4,
                                "maxOutputTokens": 800,
                            },
                        }
                        
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.post(
                                url,
                                json=payload,
                                params={"key": self.gemini_key},
                            )
                            resp.raise_for_status()
                            data = resp.json()
                        
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        logger.info(f"Patient summary generated in {language} via {model_name}")
                        return text.strip()
                    
                    except Exception as e:
                        logger.warning(f"Patient summary via {model_name} failed: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"All Gemini models failed for patient summary: {e}")

        # Template fallback
        return self._patient_summary_template(top_label, severity, scan_type_label, language)

    @staticmethod
    def _patient_summary_template(
        top_label: str, severity: str, scan_type: str, language: str,
    ) -> str:
        """Fallback template when no LLM is available."""
        if language.lower() != "english":
            prefix = f"[A {language} version is temporarily unavailable. Showing English.]\n\n"
        else:
            prefix = ""

        if top_label.lower() in ("no tumor", "normal"):
            return (
                f"{prefix}"
                f"Your {scan_type} results are in, and the good news is that no significant "
                f"problems were detected. The analysis did not find any signs of a tumor or "
                f"other concerning findings.\n\n"
                f"While this is reassuring, please remember that no test is perfect. "
                f"If you are experiencing any symptoms or have concerns, it is always a good "
                f"idea to discuss them with your doctor.\n\n"
                f"We recommend continuing with your regular health checkups. "
                f"Take care of yourself!"
            )
        else:
            severity_text = {
                "Mild": "The findings appear to be mild",
                "Moderate": "The findings appear to be moderate in nature",
                "Severe": "The findings require prompt medical attention",
            }.get(severity, "The findings need further evaluation")

            return (
                f"{prefix}"
                f"Your {scan_type} has been analyzed, and the results suggest a finding "
                f"that your doctor will want to review with you. "
                f"The analysis indicates a possible condition called '{top_label}'.\n\n"
                f"{severity_text}. This does not mean a final diagnosis — "
                f"your doctor will need to examine the results carefully and may recommend "
                f"additional tests to get a clearer picture.\n\n"
                f"Please schedule an appointment with your doctor to discuss these results. "
                f"They will be able to explain what this means for you personally and "
                f"guide you on the next steps.\n\n"
                f"Remember, early detection and proper medical guidance are the best "
                f"steps you can take for your health. We are here to support you."
            )

    async def generate_patient_summary(
        self,
        report_data: dict,
        language: str = "English",
    ) -> str:
        """Backward-compatible alias for older callers."""
        return await self.generate_patient_report(report_data, language)
