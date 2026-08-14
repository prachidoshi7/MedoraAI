"""Two-class kidney ultrasound classifier from the multi-organ prototype."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

CLASS_LABELS = ["Normal", "Stone"]


class CNNKidneyStone(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.25)
        self.fc1 = nn.Linear(64 * 14 * 14, 128)
        self.fc_bn1 = nn.BatchNorm1d(128)
        self.fc2 = nn.Linear(128, 64)
        self.fc_bn2 = nn.BatchNorm1d(64)
        self.fc3 = nn.Linear(64, 32)
        self.fc_bn3 = nn.BatchNorm1d(32)
        self.fc4 = nn.Linear(32, 8)
        self.fc5 = nn.Linear(8, 2)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = x.reshape(x.size(0), -1)
        x = self.dropout(F.relu(self.fc_bn1(self.fc1(x))))
        x = self.dropout(F.relu(self.fc_bn2(self.fc2(x))))
        x = self.dropout(F.relu(self.fc_bn3(self.fc3(x))))
        x = self.dropout(F.relu(self.fc4(x)))
        return self.fc5(x)


@dataclass
class KidneyClassificationResult:
    top_label: str
    confidence: float
    all_scores: dict[str, float]
    severity: str
    scan_type: str = "kidney_us"
    is_low_confidence: bool = False
    secondary_findings: list[dict] = field(default_factory=list)
    heatmap_target_label: str = ""
    heatmap_target_idx: int = 0


class KidneyClassifier:
    def __init__(self, model_path: Optional[str], device: str = "cpu"):
        if not model_path:
            raise FileNotFoundError("Kidney model path is not configured")
        self.device = torch.device(device)
        self.model = CNNKidneyStone()
        weights = torch.load(model_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(weights)
        self.model.to(self.device).eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.inference_lock = threading.RLock()
        self.transform = transforms.Compose([
            transforms.Resize((112, 112)),
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor(),
        ])
        logger.info("Loaded kidney stone weights from %s", model_path)

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        return self.transform(image).unsqueeze(0).to(self.device)

    @torch.no_grad()
    def predict(self, image: Image.Image) -> KidneyClassificationResult:
        with self.inference_lock:
            probabilities = torch.softmax(self.model(self.preprocess(image)), dim=1)[0]
        if probabilities.numel() != len(CLASS_LABELS) or not torch.isfinite(probabilities).all():
            raise RuntimeError("Kidney classifier returned invalid probabilities")
        index = int(probabilities.argmax().item())
        confidence = float(probabilities[index].item())
        label = CLASS_LABELS[index]
        severity = "Normal" if label == "Normal" else (
            "Moderate" if confidence < 0.75 else "Severe"
        )
        scores = {
            name: round(float(probabilities[position].item()), 4)
            for position, name in enumerate(CLASS_LABELS)
        }
        return KidneyClassificationResult(
            top_label=label,
            confidence=confidence,
            all_scores=scores,
            severity=severity,
            is_low_confidence=confidence < 0.60,
            heatmap_target_label=label,
            heatmap_target_idx=index,
        )

    def get_model(self):
        return self.model
