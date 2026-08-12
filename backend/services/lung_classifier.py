"""Five-class lung CT classifier ported from the multi-organ prototype."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

CLASS_LABELS = [
    "Benign",
    "Normal",
    "Adenocarcinoma",
    "Large Cell Carcinoma",
    "Squamous Cell Carcinoma",
]


class CNNLung(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.conv4 = nn.Conv2d(64, 128, 3, padding=1)
        self.bn4 = nn.BatchNorm2d(128)
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.2)
        self.fc1 = nn.Linear(128 * 8 * 8, 128)
        self.fc_bn1 = nn.BatchNorm1d(128)
        self.fc2 = nn.Linear(128, 64)
        self.fc_bn2 = nn.BatchNorm1d(64)
        self.fc3 = nn.Linear(64, 15)
        self.fc_bn3 = nn.BatchNorm1d(15)
        self.fc4 = nn.Linear(15, 5)

    def forward(self, x):
        x = self.pool(F.relu(self.bn1(self.conv1(x))))
        x = self.pool(F.relu(self.bn2(self.conv2(x))))
        x = self.pool(F.relu(self.bn3(self.conv3(x))))
        x = self.pool(F.relu(self.bn4(self.conv4(x))))
        x = x.reshape(x.size(0), -1)
        x = self.dropout(F.relu(self.fc_bn1(self.fc1(x))))
        x = self.dropout(F.relu(self.fc_bn2(self.fc2(x))))
        x = self.dropout(F.relu(self.fc_bn3(self.fc3(x))))
        return self.fc4(x)


@dataclass
class LungClassificationResult:
    top_label: str
    confidence: float
    all_scores: dict[str, float]
    severity: str
    scan_type: str = "lung_ct"
    is_low_confidence: bool = False
    secondary_findings: list[dict] = field(default_factory=list)
    heatmap_target_label: str = ""
    heatmap_target_idx: int = 0


class LungClassifier:
    def __init__(self, model_path: Optional[str], device: str = "cpu"):
        if not model_path:
            raise FileNotFoundError("Lung model path is not configured")
        self.device = torch.device(device)
        self.model = CNNLung()
        weights = torch.load(model_path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(weights)
        self.model.to(self.device).eval()
        self.transform = transforms.Compose([
            transforms.Resize((128, 128)),
            transforms.ToTensor(),
            transforms.Grayscale(num_output_channels=1),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])
        logger.info("Loaded five-class lung CT weights from %s", model_path)

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        return self.transform(image.convert("RGB")).unsqueeze(0).to(self.device)

    @torch.no_grad()
    def predict(self, image: Image.Image) -> LungClassificationResult:
        probabilities = torch.softmax(self.model(self.preprocess(image)), dim=1)[0]
        index = int(probabilities.argmax().item())
        confidence = float(probabilities[index].item())
        label = CLASS_LABELS[index]
        severity = "Normal" if label in {"Normal", "Benign"} else (
            "Moderate" if confidence < 0.75 else "Severe"
        )
        scores = {
            name: round(float(probabilities[position].item()), 4)
            for position, name in enumerate(CLASS_LABELS)
        }
        return LungClassificationResult(
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
