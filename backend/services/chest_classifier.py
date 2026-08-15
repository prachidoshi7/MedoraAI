"""MedoraAI chest X-ray classifier, ported from the madora reference."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "microsoft/rad-dino"
INPUT_SIZE = 518
HIDDEN_SIZE = 768
CLASS_LABELS = ["Normal", "Pneumonia", "Tuberculosis"]
NO_FINDING_LABEL = "Normal"
PATHOLOGY_LABELS = [label for label in CLASS_LABELS if label != NO_FINDING_LABEL]
MIN_PATHOLOGY_CONFIDENCE = 0.30
LOW_CONFIDENCE_CEILING = 0.50
SECONDARY_FINDING_THRESHOLD = 0.20
_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]


@dataclass
class ClassificationResult:
    top_label: str
    confidence: float
    all_scores: dict[str, float]
    severity: str
    scan_type: str = "chest_xray"
    is_low_confidence: bool = False
    secondary_findings: list[dict] = field(default_factory=list)
    heatmap_target_label: str = ""
    heatmap_target_idx: int = 0


def confidence_to_severity(confidence: float, label: str) -> str:
    if label == NO_FINDING_LABEL:
        return "Normal"
    if confidence < 0.50:
        return "Mild"
    if confidence < 0.75:
        return "Moderate"
    return "Severe"


class RadDinoClassifier(nn.Module):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, num_classes: int = 3):
        super().__init__()
        from transformers import AutoModel

        logger.info("Initializing RadDinoClassifier backbone: %s", model_name)
        self.backbone = AutoModel.from_pretrained(model_name)
        self.classifier = nn.Sequential(
            nn.LayerNorm(HIDDEN_SIZE),
            nn.Dropout(0.1),
            nn.Linear(HIDDEN_SIZE, num_classes),
        )

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        outputs = self.backbone(pixel_values=pixel_values)
        return self.classifier(outputs.last_hidden_state[:, 0])


class ChestXRayClassifier:
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.device = torch.device(
            device if torch.cuda.is_available() and device == "cuda" else "cpu"
        )
        self._model: Optional[RadDinoClassifier] = None
        self.classes = CLASS_LABELS
        self.input_size = INPUT_SIZE
        self.transform = transforms.Compose([
            transforms.Resize(
                self.input_size,
                interpolation=transforms.InterpolationMode.BICUBIC,
            ),
            transforms.CenterCrop(self.input_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ])
        self._load_model(model_path)

    def _load_model(self, model_path: Optional[str]):
        candidate_paths = [
            model_path,
            "models/rad_dino_chest_xray_classifier.pth",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "..", "models", "rad_dino_chest_xray_classifier.pth",
            ),
        ]
        resolved_path = next(
            (os.path.abspath(path) for path in candidate_paths if path and os.path.isfile(path)),
            None,
        )
        if not resolved_path:
            logger.warning("RAD-DINO checkpoint not found: %s", candidate_paths)
            return

        try:
            config_path = os.path.join(os.path.dirname(resolved_path), "model_config.json")
            model_name = DEFAULT_MODEL_NAME
            num_classes = len(CLASS_LABELS)
            if os.path.isfile(config_path):
                with open(config_path, "r", encoding="utf-8") as handle:
                    config = json.load(handle)
                model_name = config.get("model_name", DEFAULT_MODEL_NAME)
                num_classes = config.get("num_classes", len(CLASS_LABELS))
                self.input_size = config.get("image_size", INPUT_SIZE)

            self._model = RadDinoClassifier(model_name=model_name, num_classes=num_classes)
            checkpoint = torch.load(resolved_path, map_location="cpu", weights_only=False)
            if isinstance(checkpoint, dict) and "classifier_state_dict" in checkpoint:
                self._model.classifier.load_state_dict(checkpoint["classifier_state_dict"])
                val_acc = checkpoint.get("val_accuracy")
                logger.info(
                    "Loaded chest weights from %s%s",
                    resolved_path,
                    f" (validation accuracy: {val_acc:.2%})" if val_acc else "",
                )
            elif isinstance(checkpoint, dict):
                self._model.load_state_dict(checkpoint, strict=False)
            else:
                logger.warning("Unexpected chest checkpoint format: %s", resolved_path)
            self._model.to(self.device)
            self._model.eval()
        except Exception:
            logger.exception("Failed to load reference RAD-DINO chest classifier")
            self._model = None

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        if image.mode != "RGB":
            image = image.convert("RGB")
        tensor = self.transform(image)
        if tensor.ndim == 3:
            tensor = tensor.unsqueeze(0)
        return tensor.to(self.device)

    @torch.no_grad()
    def predict(self, image: Image.Image) -> ClassificationResult:
        if self._model is None:
            return ClassificationResult(
                top_label=NO_FINDING_LABEL,
                confidence=0.0,
                all_scores={label: 0.0 for label in CLASS_LABELS},
                severity="Normal",
                is_low_confidence=True,
            )

        probabilities = torch.softmax(
            self._model(self.preprocess(image)), dim=-1
        ).cpu().numpy()[0]
        all_scores = {
            label: round(float(probabilities[index]), 4)
            if index < len(probabilities) else 0.0
            for index, label in enumerate(CLASS_LABELS)
        }
        top_idx = int(np.argmax(probabilities))
        top_label = CLASS_LABELS[top_idx]
        top_confidence = float(probabilities[top_idx])

        if top_label != NO_FINDING_LABEL and top_confidence < MIN_PATHOLOGY_CONFIDENCE:
            top_label = NO_FINDING_LABEL
            top_confidence = float(all_scores.get(NO_FINDING_LABEL, 0.0))
            top_idx = CLASS_LABELS.index(NO_FINDING_LABEL)

        is_low_confidence = (
            top_label != NO_FINDING_LABEL
            and top_confidence < LOW_CONFIDENCE_CEILING
        )
        secondary_findings = [
            {"label": label, "score": round(all_scores[label], 4)}
            for label in PATHOLOGY_LABELS
            if label != top_label and all_scores[label] >= SECONDARY_FINDING_THRESHOLD
        ]
        secondary_findings.sort(key=lambda item: item["score"], reverse=True)

        return ClassificationResult(
            top_label=top_label,
            confidence=round(top_confidence, 4),
            all_scores=all_scores,
            severity=confidence_to_severity(top_confidence, top_label),
            is_low_confidence=is_low_confidence,
            secondary_findings=secondary_findings,
            heatmap_target_label=top_label,
            heatmap_target_idx=top_idx,
        )

    def get_model(self) -> Optional[nn.Module]:
        return self._model

    def get_transform(self):
        return self.transform

    def get_processor(self):
        return self.preprocess
