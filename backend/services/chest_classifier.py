"""RAD-DINO chest X-ray classification for MedoraAI.

Microsoft's RAD-DINO is a self-supervised chest-radiograph encoder, not a
diagnostic classifier by itself.  This module loads a CheXpert classifier
fine-tuned on top of that backbone.  The small model architecture is defined
locally so the application never executes mutable Python from the Hub.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from huggingface_hub import hf_hub_download
from PIL import Image
from transformers import AutoImageProcessor, Dinov2Config, Dinov2Model

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "kaan-ylmn/rad-dino-chexpert"
DEFAULT_MODEL_REVISION = "db02e1b7234dd83c6d7c4485963ef5b22df9e5db"
# CheXpert label order stored in the pinned downstream checkpoint.
CLASS_LABELS = [
    "No Finding",
    "Enlarged Cardiomediastinum",
    "Cardiomegaly",
    "Lung Opacity",
    "Lung Lesion",
    "Edema",
    "Consolidation",
    "Pneumonia",
    "Atelectasis",
    "Pneumothorax",
    "Pleural Effusion",
    "Pleural Other",
    "Fracture",
    "Support Devices",
]

NO_FINDING_LABEL = "No Finding"
SUPPORT_DEVICES_LABEL = "Support Devices"
PATHOLOGY_LABELS = [
    label for label in CLASS_LABELS
    if label not in {NO_FINDING_LABEL, SUPPORT_DEVICES_LABEL}
]


@dataclass
class ClassificationResult:
    """Normalized result consumed by the scan and report pipelines."""

    top_label: str
    confidence: float
    all_scores: dict[str, float]
    severity: str
    scan_type: str = "chest_xray"
    is_low_confidence: bool = False
    secondary_findings: list[dict] = field(default_factory=list)
    heatmap_target_label: str = ""
    heatmap_target_idx: int = 0
    model_name: str = "RAD-DINO + CheXpert"


def confidence_to_severity(confidence: float, label: str) -> str:
    """Map a model score to the existing non-clinical UI severity bucket."""
    if label == NO_FINDING_LABEL:
        return "Normal"
    if confidence < 0.60:
        return "Mild"
    if confidence < 0.80:
        return "Moderate"
    return "Severe"


def build_classification_result(
    probabilities: np.ndarray,
    *,
    pathology_threshold: float = 0.50,
    secondary_threshold: float = 0.35,
) -> ClassificationResult:
    """Convert 14 independent CheXpert probabilities into the API contract.

    CheXpert is multi-label, so sigmoid outputs are thresholded independently.
    ``No Finding`` is selected only when no diagnostic pathology crosses the
    configured threshold. Support devices remain an auxiliary finding and are
    never promoted to the primary diagnosis.
    """
    values = np.asarray(probabilities, dtype=np.float32).reshape(-1)
    if values.size != len(CLASS_LABELS):
        raise ValueError(
            f"Expected {len(CLASS_LABELS)} CheXpert scores, received {values.size}."
        )
    if not np.isfinite(values).all():
        raise ValueError("The chest classifier returned a non-finite score.")

    values = np.clip(values, 0.0, 1.0)
    all_scores = {
        label: round(float(score), 4)
        for label, score in zip(CLASS_LABELS, values)
    }

    pathology_indices = [CLASS_LABELS.index(label) for label in PATHOLOGY_LABELS]
    best_pathology_idx = max(pathology_indices, key=lambda idx: float(values[idx]))
    best_pathology_score = float(values[best_pathology_idx])
    no_finding_idx = CLASS_LABELS.index(NO_FINDING_LABEL)

    if best_pathology_score >= pathology_threshold:
        top_idx = best_pathology_idx
    else:
        top_idx = no_finding_idx

    top_label = CLASS_LABELS[top_idx]
    top_confidence = float(values[top_idx])
    secondary_findings = [
        {"label": label, "score": round(float(values[index]), 4)}
        for index, label in enumerate(CLASS_LABELS)
        if label not in {NO_FINDING_LABEL, top_label}
        and float(values[index]) >= secondary_threshold
    ]
    secondary_findings.sort(key=lambda item: item["score"], reverse=True)

    return ClassificationResult(
        top_label=top_label,
        confidence=round(top_confidence, 4),
        all_scores=all_scores,
        severity=confidence_to_severity(top_confidence, top_label),
        is_low_confidence=(
            top_confidence < pathology_threshold
            if top_label == NO_FINDING_LABEL
            else top_confidence < 0.65
        ),
        secondary_findings=secondary_findings,
        heatmap_target_label=top_label,
        heatmap_target_idx=top_idx,
    )


class RadDinoCheXpertModel(nn.Module):
    """Reviewed local equivalent of the checkpoint's 14-label model class."""

    def __init__(self, config: Dinov2Config):
        super().__init__()
        self.config = config
        self.dinov2 = Dinov2Model(config)
        self.dropout = nn.Dropout(float(getattr(config, "classifier_dropout", 0.1)))
        self.classifier = nn.Linear(config.hidden_size, len(CLASS_LABELS))

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        output = self.dinov2(pixel_values=pixel_values, return_dict=True)
        cls_embedding = output.last_hidden_state[:, 0]
        return self.classifier(self.dropout(cls_embedding))


class ChestXRayClassifier:
    """RAD-DINO backbone with a pinned, fine-tuned CheXpert classification head."""

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        revision: str = DEFAULT_MODEL_REVISION,
        *,
        device: str = "auto",
        cache_dir: Optional[str] = None,
        local_files_only: bool = False,
        pathology_threshold: float = 0.50,
        secondary_threshold: float = 0.35,
    ):
        self.model_id = model_id
        self.revision = revision
        self.cache_dir = cache_dir
        self.local_files_only = local_files_only
        self.pathology_threshold = pathology_threshold
        self.secondary_threshold = secondary_threshold
        self.device = torch.device(
            "cuda" if device == "auto" and torch.cuda.is_available()
            else "cpu" if device == "auto"
            else device
        )
        self.inference_lock = threading.RLock()

        logger.info(
            "Loading RAD-DINO CheXpert classifier %s@%s on %s...",
            model_id,
            revision[:12],
            self.device,
        )
        self.processor = self._load_processor()
        self.model = self._load_reviewed_checkpoint()
        self.image_size = int(getattr(self.model.config, "image_size", 518))
        self.patch_size = int(getattr(self.model.config, "patch_size", 14))
        self.patch_grid_size = self.image_size // self.patch_size

        logger.info(
            "RAD-DINO chest classifier ready: input=%sx%s patch_grid=%sx%s labels=%s.",
            self.image_size,
            self.image_size,
            self.patch_grid_size,
            self.patch_grid_size,
            len(CLASS_LABELS),
        )

    def _load_processor(self):
        """Prefer the immutable local snapshot and contact the Hub only if absent."""
        common = {
            "pretrained_model_name_or_path": self.model_id,
            "revision": self.revision,
            "cache_dir": self.cache_dir,
        }
        try:
            return AutoImageProcessor.from_pretrained(
                **common,
                local_files_only=True,
            )
        except OSError:
            if self.local_files_only:
                raise
            logger.info("RAD-DINO processor not cached; downloading pinned revision.")
            return AutoImageProcessor.from_pretrained(
                **common,
                local_files_only=False,
            )

    def _download(self, filename: str) -> str:
        common = {
            "repo_id": self.model_id,
            "filename": filename,
            "revision": self.revision,
            "cache_dir": self.cache_dir,
        }
        try:
            return hf_hub_download(**common, local_files_only=True)
        except OSError:
            if self.local_files_only:
                raise
            logger.info("RAD-DINO %s not cached; downloading pinned revision.", filename)
            return hf_hub_download(**common, local_files_only=False)

    def _load_reviewed_checkpoint(self) -> RadDinoCheXpertModel:
        with open(self._download("config.json"), encoding="utf-8") as handle:
            config_data = json.load(handle)

        checkpoint_labels = [
            config_data.get("id2label", {}).get(str(index))
            for index in range(len(CLASS_LABELS))
        ]
        if checkpoint_labels != CLASS_LABELS:
            raise RuntimeError(
                "Pinned RAD-DINO checkpoint labels changed; refusing unsafe label mapping."
            )

        config_data.pop("auto_map", None)
        config_data["model_type"] = "dinov2"
        config = Dinov2Config.from_dict(config_data)
        model = RadDinoCheXpertModel(config)

        state_dict = torch.load(
            self._download("pytorch_model.bin"),
            map_location="cpu",
            weights_only=True,
        )
        if isinstance(state_dict, dict) and "state_dict" in state_dict:
            state_dict = state_dict["state_dict"]
        model.load_state_dict(state_dict, strict=True)
        model.to(self.device)
        model.eval()

        # Attribution only needs gradients for an input/intermediate tensor.
        # Freezing parameters avoids allocating hundreds of MB of parameter grads.
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        return model

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        """Apply the checkpoint's 518px radiograph preprocessing pipeline."""
        inputs = self.processor(
            images=image.convert("RGB"),
            return_tensors="pt",
        )
        return inputs["pixel_values"].to(self.device)

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> ClassificationResult:
        with self.inference_lock:
            logits = self.model(self.preprocess(image))
            probabilities = torch.sigmoid(logits).float().cpu().numpy()[0]
        return build_classification_result(
            probabilities,
            pathology_threshold=self.pathology_threshold,
            secondary_threshold=self.secondary_threshold,
        )

    def get_model(self) -> RadDinoCheXpertModel:
        return self.model

    def get_transform(self):
        """Compatibility accessor for callers that need the HF processor."""
        return self.processor

    def patch_grid_from_token_count(self, token_count: int) -> int:
        """Validate the transformer patch-token geometry."""
        grid = int(math.sqrt(token_count))
        if grid * grid != token_count:
            raise RuntimeError(f"RAD-DINO returned {token_count} non-square patch tokens.")
        return grid
