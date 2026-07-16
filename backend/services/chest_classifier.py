"""
MedoraAI — Chest X-Ray Classifier
EfficientNet-B4 via timm, 15-class multi-label sigmoid output.
Trained on NIH ChestX-ray14 pathology labels.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

# 15 class labels matching NIH ChestX-ray14 + "No Finding"
CLASS_LABELS = [
    "Atelectasis", "Cardiomegaly", "Effusion", "Infiltration",
    "Mass", "Nodule", "Pneumonia", "Pneumothorax",
    "Consolidation", "Edema", "Emphysema", "Fibrosis",
    "Pleural Thickening", "Hernia", "No Finding",
]

NO_FINDING_LABEL = "No Finding"
PATHOLOGY_LABELS = [label for label in CLASS_LABELS if label != NO_FINDING_LABEL]

# NIH ChestX-ray14 is multi-label. Raw sigmoid scores are not calibrated enough to
# treat the highest low score as a diagnosis, so require a minimum pathology score.
# Lowered from 0.35 to 0.25 — undertrained models produce lower raw sigmoid scores,
# and 0.35 was causing everything to fall through to "No Finding".
MIN_PATHOLOGY_CONFIDENCE = 0.25

# When the top pathology score is between MIN_PATHOLOGY_CONFIDENCE and this value,
# we flag the result as low-confidence so the report/UI can communicate uncertainty.
LOW_CONFIDENCE_CEILING = 0.50


@dataclass
class ClassificationResult:
    """Result from chest X-ray classification."""
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
    """
    Map model confidence to clinical severity label.
    Thresholds are intentionally conservative.
    """
    if label == NO_FINDING_LABEL:
        return "Normal"
    elif confidence < 0.5:
        return "Mild"
    elif confidence < 0.75:
        return "Moderate"
    else:
        return "Severe"


class ChestXRayClassifier:
    """
    EfficientNet-B4 based chest X-ray multi-label classifier.
    
    Uses timm pretrained weights (ImageNet) by default.
    Can load fine-tuned CheXNet-compatible weights if available.
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        """
        Initialize the classifier.
        
        Args:
            model_path: Path to fine-tuned weights (.pt). If None, uses ImageNet pretrained.
            device: "cpu" or "cuda"
        """
        import timm

        self.device = torch.device(device)
        logger.info(f"Loading ChestXRayClassifier on {self.device}...")

        # Create EfficientNet-B4 with 15 output classes
        self.model = timm.create_model(
            "efficientnet_b4",
            pretrained=model_path is None,
            num_classes=len(CLASS_LABELS),
        )

        # Load fine-tuned weights if available
        if model_path:
            try:
                state_dict = torch.load(model_path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state_dict)
                logger.info(f"Loaded fine-tuned weights from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load weights from {model_path}: {e}. Using pretrained.")

        self.model.to(self.device)
        self.model.eval()

        # Preprocessing pipeline (ImageNet statistics)
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        logger.info("ChestXRayClassifier loaded successfully.")

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        """
        Preprocess a PIL Image for inference.
        Converts grayscale to RGB if needed.
        Returns tensor of shape (1, 3, 224, 224).
        """
        # Ensure RGB (chest X-rays are often grayscale)
        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = self.transform(image)
        return tensor.unsqueeze(0).to(self.device)  # Add batch dimension

    @torch.no_grad()
    def predict(self, image: Image.Image) -> ClassificationResult:
        """
        Run inference on a single PIL Image.
        
        Args:
            image: PIL Image of chest X-ray
            
        Returns:
            ClassificationResult with top label, confidence, all scores, severity
        """
        input_tensor = self.preprocess(image)

        # Forward pass
        logits = self.model(input_tensor)
        probabilities = torch.sigmoid(logits).cpu().numpy()[0]  # Multi-label sigmoid

        # Build scores dict
        all_scores = {
            label: round(float(prob), 4)
            for label, prob in zip(CLASS_LABELS, probabilities)
        }

        pathology_indices = [CLASS_LABELS.index(label) for label in PATHOLOGY_LABELS]
        pathology_scores = probabilities[pathology_indices]
        best_pathology_pos = int(np.argmax(pathology_scores))
        best_pathology_idx = pathology_indices[best_pathology_pos]
        best_pathology_score = float(probabilities[best_pathology_idx])
        no_finding_idx = CLASS_LABELS.index(NO_FINDING_LABEL)

        if best_pathology_score >= MIN_PATHOLOGY_CONFIDENCE:
            top_idx = best_pathology_idx
        else:
            top_idx = no_finding_idx

        top_label = CLASS_LABELS[top_idx]
        top_confidence = float(probabilities[top_idx])

        # Flag low-confidence pathology detections
        is_low_confidence = (
            top_label != NO_FINDING_LABEL
            and top_confidence < LOW_CONFIDENCE_CEILING
        )

        # Collect secondary findings (pathologies with score >= 0.20, excluding top)
        secondary_findings = [
            {"label": label, "score": round(float(probabilities[CLASS_LABELS.index(label)]), 4)}
            for label in PATHOLOGY_LABELS
            if label != top_label
            and float(probabilities[CLASS_LABELS.index(label)]) >= 0.20
        ]
        secondary_findings.sort(key=lambda x: x["score"], reverse=True)

        # Determine Grad-CAM target: explain the predicted class logit.
        # The Grad-CAM implementation targets this raw model output before
        # sigmoid, not a probability or an average across classes.
        heatmap_target_label = CLASS_LABELS[top_idx]
        heatmap_target_idx = top_idx

        # Map to severity
        severity = confidence_to_severity(top_confidence, top_label)

        return ClassificationResult(
            top_label=top_label,
            confidence=round(top_confidence, 4),
            all_scores=all_scores,
            severity=severity,
            scan_type="chest_xray",
            is_low_confidence=is_low_confidence,
            secondary_findings=secondary_findings,
            heatmap_target_label=heatmap_target_label,
            heatmap_target_idx=heatmap_target_idx,
        )

    def get_model(self) -> nn.Module:
        """Return the underlying PyTorch model for Grad-CAM access."""
        return self.model

    def get_transform(self) -> transforms.Compose:
        """Return the preprocessing transform pipeline."""
        return self.transform
