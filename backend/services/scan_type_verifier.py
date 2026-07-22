"""Fail-closed scan type verification before diagnostic model inference."""

import asyncio
import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanTypeVerification:
    category: str
    confidence: float
    is_single_diagnostic_image: bool
    anatomy_complete_enough: bool
    reason: str


class ScanTypeVerifier:
    """Classify scan anatomy/modality independently from disease models."""

    PROMPT = """Inspect the supplied image only to verify its medical image type.
Do not diagnose disease and do not use filenames or user claims.

Category describes the underlying imaging modality/anatomy, independently from layout:
- chest_xray: the predominant diagnostic content is a frontal AP/PA chest radiograph showing the thorax and both lungs.
- brain_mri: the predominant diagnostic content is an intracranial brain MRI slice (axial, coronal, or sagittal), not a head CT.
- other: the predominant content is not a chest radiograph or brain MRI. This includes a photograph, illustration, CT, ultrasound, non-brain MRI, non-chest radiograph, lateral-only chest image, web page, or document.
- uncertain: use when the modality or anatomy cannot be identified confidently.

Set is_single_diagnostic_image=false for posters, collages, report pages, multiple panels, screenshots dominated by application/browser UI, or images where the diagnostic scan is only a small inset.
Set anatomy_complete_enough=false when the relevant anatomy is too cropped, obscured, tiny, or low quality for the selected workflow.
PANEL RULE: Your vision encoder may internally create resized crops or tiles. Those internal tiles are not part of the uploaded image and must be ignored. Call the original upload multi-panel only when separator borders or spacing are visibly present inside the original image itself. Anatomical regions, lung fields, an inset marker, or areas within one continuous radiographic field are not separate panels.
Be conservative. If unsure, return uncertain rather than guessing.

Output only JSON with exactly these fields:
{
  "category": "chest_xray|brain_mri|other|uncertain",
  "confidence": 0.0,
  "is_single_diagnostic_image": true,
  "anatomy_complete_enough": true,
  "reason": "brief non-diagnostic reason"
}"""

    VALID_CATEGORIES = {"chest_xray", "brain_mri", "other", "uncertain"}

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        min_confidence: float = 0.85,
        groq_api_key: Optional[str] = None,
        groq_model: str = "qwen/qwen3.6-27b",
    ):
        self.api_key = api_key
        self.model = model
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        from services.local_scan_type_model import LocalScanTypeModel
        self.local_model = LocalScanTypeModel()
        self.min_confidence = min(max(float(min_confidence), 0.0), 1.0)
        # Type verification is a small visual classification task. Prefer the
        # stable fast endpoint and keep one fallback so uploads cannot hang while
        # several unavailable model names time out sequentially.
        self.models = list(dict.fromkeys([
            "gemini-flash-latest",
            model,
            "gemini-2.5-flash",
        ]))[:1]

    async def verify(self, image: Image.Image) -> ScanTypeVerification:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._verify_sync, image),
                timeout=16.0,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Image-type verification timed out") from exc

    def _verify_sync(self, image: Image.Image) -> ScanTypeVerification:
        prepared = image.convert("RGB")
        local_result = self._verify_locally(prepared)
        if local_result is not None:
            self._log_success(local_result, "local verifier")
            return local_result

        prepared.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        prepared.save(buffer, format="JPEG", quality=92, optimize=True)
        image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        last_error: Optional[Exception] = None

        # Use the separately provisioned high-throughput vision endpoint first.
        # This keeps image validation independent from report-generation quota.
        if self.groq_api_key:
            try:
                verification = self._verify_with_groq(image_b64)
                verification = self._normalize_provider_layout(verification, prepared)
                self._log_success(verification, "primary vision verifier")
                return verification
            except Exception as exc:
                last_error = exc
                logger.warning("Primary scan-type verifier unavailable: %s", exc)

        if self.api_key:
            for model_name in self.models:
                try:
                    verification = self._verify_with_gemini(image_b64, model_name)
                    verification = self._normalize_provider_layout(
                        verification, prepared
                    )
                    self._log_success(verification, "secondary vision verifier")
                    return verification
                except Exception as exc:
                    last_error = exc
                    logger.warning("Secondary scan-type verifier unavailable: %s", exc)

        raise RuntimeError("Image-type verification is temporarily unavailable") from last_error

    def _verify_locally(
        self,
        image: Image.Image,
    ) -> Optional[ScanTypeVerification]:
        """Resolve only high-confidence cases locally; defer ambiguous images."""
        import numpy as np

        width, height = image.size
        aspect = width / max(float(height), 1.0)
        rgb = np.asarray(
            image.resize((256, 256)).convert("RGB"), dtype=np.float32
        ) / 255.0
        channel_delta = float(
            np.mean(
                np.abs(rgb[:, :, 0] - rgb[:, :, 1])
                + np.abs(rgb[:, :, 1] - rgb[:, :, 2])
                + np.abs(rgb[:, :, 0] - rgb[:, :, 2])
            ) / 3.0
        )
        gray_u8 = np.asarray(
            image.resize((256, 256)).convert("L"), dtype=np.uint8
        )
        histogram = np.bincount(gray_u8.reshape(-1), minlength=256).astype(np.float64)
        histogram /= max(float(histogram.sum()), 1.0)
        nonzero = histogram[histogram > 0]
        entropy = float(-(nonzero * np.log2(nonzero)).sum())

        if self._has_visible_panel_separators(gray_u8):
            return ScanTypeVerification(
                category="other",
                confidence=0.99,
                is_single_diagnostic_image=False,
                anatomy_complete_enough=False,
                reason="Multiple diagnostic image panels are separated inside the uploaded image.",
            )

        if (
            min(width, height) < 128
            or aspect < 0.60
            or aspect > 1.80
            or channel_delta > 0.14
            or entropy < 3.8
        ):
            return ScanTypeVerification(
                category="other",
                confidence=0.99,
                is_single_diagnostic_image=False,
                anatomy_complete_enough=False,
                reason="The image has non-diagnostic screenshot, document, color, or layout characteristics.",
            )

        gray = gray_u8.astype(np.float32) / 255.0
        low, high = np.quantile(gray, [0.01, 0.99])
        if high > low:
            gray = np.clip((gray - low) / (high - low), 0.0, 1.0)

        brain_probability = self.local_model.brain_probability(image)
        chest_like = self._has_chest_pattern(gray)
        brain_like = self._has_brain_pattern(gray)

        if brain_probability >= 0.75 and (brain_like or not chest_like):
            return ScanTypeVerification(
                category="brain_mri",
                confidence=max(0.86, brain_probability),
                is_single_diagnostic_image=True,
                anatomy_complete_enough=True,
                reason="Local anatomy and texture features support a single brain MRI image.",
            )
        if brain_probability <= 0.12 and chest_like:
            return ScanTypeVerification(
                category="chest_xray",
                confidence=max(0.86, 1.0 - brain_probability),
                is_single_diagnostic_image=True,
                anatomy_complete_enough=True,
                reason="Local anatomy and texture features support a single frontal chest radiograph.",
            )
        return None

    @staticmethod
    def _has_visible_panel_separators(gray_u8) -> bool:
        """Detect broad interior divider bands without treating anatomy as panels."""
        import numpy as np

        gray = gray_u8.astype(np.float32) / 255.0
        height, width = gray.shape
        row_mean = gray.mean(axis=1)
        row_std = gray.std(axis=1)
        col_mean = gray.mean(axis=0)
        col_std = gray.std(axis=0)

        row_candidates = (
            (row_std < 0.018)
            & ((row_mean < 0.035) | (row_mean > 0.965))
        )
        col_candidates = (
            (col_std < 0.018)
            & ((col_mean < 0.035) | (col_mean > 0.965))
        )
        # Ignore broad black scanner canvas around a centered MRI slice. True
        # collage separators generally cross the central half of the upload.
        row_candidates[: max(2, int(height * 0.24))] = False
        row_candidates[int(height * 0.76):] = False
        col_candidates[: max(2, int(width * 0.24))] = False
        col_candidates[int(width * 0.76):] = False

        def longest_run(values) -> int:
            best = current = 0
            for value in values:
                current = current + 1 if value else 0
                best = max(best, current)
            return best

        return bool(
            longest_run(row_candidates) >= max(3, int(height * 0.008))
            or longest_run(col_candidates) >= max(3, int(width * 0.008))
        )

    @classmethod
    def _normalize_provider_layout(
        cls,
        verification: ScanTypeVerification,
        image: Image.Image,
    ) -> ScanTypeVerification:
        """Ignore provider-internal vision tiles when the original has no divider."""
        if verification.category not in {"chest_xray", "brain_mri"}:
            return verification
        reason = verification.reason.lower()
        tile_claim = any(
            term in reason
            for term in ("panel", "collage", "zoomed", "crop")
        )
        if verification.is_single_diagnostic_image or not tile_claim:
            return verification

        import numpy as np

        gray = np.asarray(
            image.resize((256, 256)).convert("L"), dtype=np.uint8
        )
        if cls._has_visible_panel_separators(gray):
            return verification
        return ScanTypeVerification(
            category=verification.category,
            confidence=verification.confidence,
            is_single_diagnostic_image=True,
            anatomy_complete_enough=verification.anatomy_complete_enough,
            reason=(
                "A single continuous diagnostic image is present; provider-internal "
                "vision tiles were ignored."
            ),
        )

    @staticmethod
    def _has_brain_pattern(gray) -> bool:
        import cv2
        import numpy as np

        mask = (gray > max(0.12, float(np.quantile(gray, 0.30)))).astype(np.uint8)
        count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if count <= 1:
            return False
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, width, height, area = stats[largest]
        area_ratio = float(area) / float(gray.size)
        fill = float(area) / max(float(width * height), 1.0)
        shape_ratio = float(width) / max(float(height), 1.0)
        center_x, center_y = centroids[largest]
        centered = (
            abs(center_x - gray.shape[1] / 2.0) < gray.shape[1] * 0.17
            and abs(center_y - gray.shape[0] / 2.0) < gray.shape[0] * 0.20
        )
        border = np.concatenate([
            gray[:16, :].reshape(-1), gray[-16:, :].reshape(-1),
            gray[:, :16].reshape(-1), gray[:, -16:].reshape(-1),
        ])
        return bool(
            centered
            and float(border.mean()) < 0.18
            and 0.16 <= area_ratio <= 0.72
            and 0.58 <= shape_ratio <= 1.55
            and fill >= 0.38
        )

    @staticmethod
    def _has_chest_pattern(gray) -> bool:
        import numpy as np

        body_mask = gray > max(0.08, float(np.quantile(gray, 0.18)))
        if float(body_mask.mean()) < 0.42:
            return False
        left_lung = gray[70:190, 34:108]
        right_lung = gray[70:190, 148:222]
        center = gray[65:195, 110:146]
        lower_center = gray[150:225, 82:174]
        lung_mean = float((left_lung.mean() + right_lung.mean()) / 2.0)
        threshold = (
            float(np.quantile(gray[body_mask], 0.38))
            if body_mask.any() else 0.38
        )
        left_dark = float((left_lung < threshold).mean())
        right_dark = float((right_lung < threshold).mean())
        paired = (
            left_dark > 0.18
            and right_dark > 0.18
            and min(left_dark, right_dark) / max(left_dark, right_dark) > 0.35
        )
        central_density = float(center.mean()) > lung_mean + 0.025
        lower_coverage = float(lower_center.mean()) > lung_mean - 0.08
        return bool(paired and central_density and lower_coverage)

    def _verify_with_groq(self, image_b64: str) -> ScanTypeVerification:
        import httpx

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.groq_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                    ],
                }],
                "temperature": 0.1,
                "max_completion_tokens": 500,
                "response_format": {"type": "json_object"},
                "reasoning_effort": "none",
            },
            timeout=httpx.Timeout(
                8.0, connect=3.0, read=8.0, write=8.0, pool=3.0
            ),
        )
        response.raise_for_status()
        text = (
            response.json().get("choices", [{}])[0]
            .get("message", {}).get("content", "")
        )
        if not text:
            raise RuntimeError("Primary vision verifier returned no result")
        return self._parse_response(text)

    def _verify_with_gemini(
        self,
        image_b64: str,
        model_name: str,
    ) -> ScanTypeVerification:
        import httpx

        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [{
                    "parts": [
                        {"text": self.PROMPT},
                        {"inlineData": {"mimeType": "image/jpeg", "data": image_b64}},
                    ]
                }],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 300,
                },
            },
            timeout=httpx.Timeout(
                6.0, connect=3.0, read=6.0, write=6.0, pool=3.0
            ),
        )
        response.raise_for_status()
        text = (
            response.json().get("candidates", [{}])[0]
            .get("content", {}).get("parts", [{}])[0].get("text", "")
        )
        if not text:
            raise RuntimeError("Secondary vision verifier returned no result")
        return self._parse_response(text)

    @staticmethod
    def _log_success(verification: ScanTypeVerification, source: str) -> None:
        logger.info(
            "Scan type verified by %s: category=%s confidence=%.2f single=%s adequate=%s",
            source,
            verification.category,
            verification.confidence,
            verification.is_single_diagnostic_image,
            verification.anatomy_complete_enough,
        )

    @classmethod
    def _parse_response(cls, content: str) -> ScanTypeVerification:
        cleaned = (content or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        payload = json.loads(cleaned)
        category = str(payload.get("category", "uncertain")).strip().lower()
        if category not in cls.VALID_CATEGORIES:
            category = "uncertain"
        confidence = min(max(float(payload.get("confidence", 0.0)), 0.0), 1.0)
        return ScanTypeVerification(
            category=category,
            confidence=confidence,
            is_single_diagnostic_image=payload.get("is_single_diagnostic_image") is True,
            anatomy_complete_enough=payload.get("anatomy_complete_enough") is True,
            reason=str(payload.get("reason", "Unable to verify the image type.")).strip()[:240],
        )
