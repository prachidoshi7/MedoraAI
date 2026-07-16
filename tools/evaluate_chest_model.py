r"""
Evaluate the MedoraAI chest X-ray model on NIH ChestX-ray14-style data.

Example:
    python tools/evaluate_chest_model.py ^
      --data-root C:\path\to\nih_chest_xray14 ^
      --model models\chest_xray_efficientnet_b4.pt ^
      --max-images 2000
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.chest_classifier import CLASS_LABELS, ChestXRayClassifier, MIN_PATHOLOGY_CONFIDENCE  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate chest X-ray model accuracy/AUC.")
    parser.add_argument("--data-root", required=True, type=Path, help="Root containing Data_Entry_2017.csv and PNG files.")
    parser.add_argument("--model", default=REPO_ROOT / "models" / "chest_xray_efficientnet_b4.pt", type=Path)
    parser.add_argument("--max-images", type=int, default=None, help="Optional limit for a quick evaluation.")
    parser.add_argument("--threshold", type=float, default=MIN_PATHOLOGY_CONFIDENCE)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def find_csv(data_root: Path) -> Path:
    candidates = list(data_root.rglob("Data_Entry_2017.csv"))
    if not candidates:
        raise FileNotFoundError(f"Could not find Data_Entry_2017.csv under {data_root}")
    return candidates[0]


def load_rows(csv_path: Path, image_paths: dict[str, Path], max_images: int | None) -> list[dict]:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = row.get("Image Index")
            if image_name in image_paths:
                rows.append(row)
                if max_images is not None and len(rows) >= max_images:
                    break
    return rows


def encode_labels(label_text: str) -> list[float]:
    labels = set(str(label_text).split("|"))
    return [1.0 if label in labels else 0.0 for label in CLASS_LABELS]


def main() -> int:
    args = parse_args()
    data_root = args.data_root.resolve()
    model_path = args.model.resolve()

    image_paths = {p.name: p for p in data_root.rglob("*.png")}
    csv_path = find_csv(data_root)
    rows = load_rows(csv_path, image_paths, args.max_images)

    if not rows:
        raise RuntimeError("No CSV rows matched PNG files.")

    classifier = ChestXRayClassifier(model_path=str(model_path), device=args.device)
    model = classifier.get_model()
    transform = classifier.get_transform()

    y_true = []
    y_prob = []

    for row in tqdm(rows, desc="Evaluating"):
        image = Image.open(image_paths[row["Image Index"]]).convert("RGB")
        tensor = transform(image).unsqueeze(0).to(classifier.device)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.sigmoid(logits).cpu().numpy()[0]

        y_true.append(encode_labels(row["Finding Labels"]))
        y_prob.append(probs.tolist())

    y_true_np = np.array(y_true, dtype=np.float32)
    y_prob_np = np.array(y_prob, dtype=np.float32)
    y_pred_np = (y_prob_np >= args.threshold).astype(np.float32)

    per_label = {}
    aucs = []
    for i, label in enumerate(CLASS_LABELS):
        label_true = y_true_np[:, i]
        label_prob = y_prob_np[:, i]
        label_pred = y_pred_np[:, i]
        metrics = {
            "support": int(label_true.sum()),
            "precision": float(precision_score(label_true, label_pred, zero_division=0)),
            "recall": float(recall_score(label_true, label_pred, zero_division=0)),
            "f1": float(f1_score(label_true, label_pred, zero_division=0)),
        }
        if len(np.unique(label_true)) > 1:
            metrics["auc"] = float(roc_auc_score(label_true, label_prob))
            aucs.append(metrics["auc"])
        else:
            metrics["auc"] = None
        per_label[label] = metrics

    exact_match = float(accuracy_score(y_true_np, y_pred_np))
    macro_f1 = float(f1_score(y_true_np, y_pred_np, average="macro", zero_division=0))
    micro_f1 = float(f1_score(y_true_np, y_pred_np, average="micro", zero_division=0))

    report = {
        "data_root": str(data_root),
        "csv_path": str(csv_path),
        "model_path": str(model_path),
        "images_evaluated": len(rows),
        "threshold": args.threshold,
        "macro_auc": float(np.mean(aucs)) if aucs else None,
        "exact_match_accuracy": exact_match,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "per_label": per_label,
    }

    print(json.dumps(report, indent=2))
    if args.output_json:
        args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
