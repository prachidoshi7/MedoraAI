"""
Audit MedoraAI chest Grad-CAM behavior and score calibration.

This script intentionally works with the local app data first. If a labeled
NIH/SIIM-style CSV is supplied, it also creates reliability diagrams and
temperature-scaled calibration output for the Pneumothorax class.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.chest_classifier import CLASS_LABELS, ChestXRayClassifier  # noqa: E402
from services.chest_gradcam import ChestGradCAM  # noqa: E402


PNEUMOTHORAX_IDX = CLASS_LABELS.index("Pneumothorax")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit chest Grad-CAM and calibration.")
    parser.add_argument("--model", type=Path, default=REPO_ROOT / "models" / "chest_xray_efficientnet_b4.pt")
    parser.add_argument("--image", type=Path, default=None, help="Optional image to use for visual comparisons.")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / ".tmp" / "gradcam_audit")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-score-images", type=int, default=10)
    parser.add_argument(
        "--labels-csv",
        type=Path,
        default=None,
        help="Optional CSV with image path/name and labels for calibration/sanity testing.",
    )
    parser.add_argument("--data-root", type=Path, default=None, help="Image root used with --labels-csv.")
    return parser.parse_args()


def local_chest_images() -> list[Path]:
    db_path = BACKEND_DIR / "data" / "app.db"
    if not db_path.exists():
        return []
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    rows = cur.execute(
        "select file_path from scans where scan_type='chest_xray' order by uploaded_at"
    ).fetchall()
    paths: list[Path] = []
    for (file_path,) in rows:
        path = Path(str(file_path).replace("\\", "/"))
        if not path.is_absolute():
            candidates = [BACKEND_DIR / path, REPO_ROOT / path]
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate.exists():
                paths.append(candidate)
                break
    return paths


def pil_grid(items: list[tuple[str, Image.Image]], columns: int = 3, cell: int = 512) -> Image.Image:
    rows = int(np.ceil(len(items) / columns))
    header = 28
    grid = Image.new("RGB", (columns * cell, rows * (cell + header)), "white")
    draw = ImageDraw.Draw(grid)
    for idx, (label, image) in enumerate(items):
        row = idx // columns
        col = idx % columns
        x = col * cell
        y = row * (cell + header)
        draw.text((x + 8, y + 7), label, fill=(0, 0, 0))
        grid.paste(image.resize((cell, cell), Image.Resampling.BILINEAR), (x, y + header))
    return grid


def mask_to_rgb(mask: np.ndarray) -> Image.Image:
    rgb = np.zeros((*mask.shape, 3), dtype=np.uint8)
    rgb[:, :, 1] = np.clip(mask * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(rgb)


def module_by_name(model: torch.nn.Module, name: str) -> torch.nn.Module:
    modules = dict(model.named_modules())
    if name not in modules:
        raise KeyError(name)
    return modules[name]


def cam_summary(cam: np.ndarray) -> dict[str, float | list[int]]:
    yy, xx = np.indices(cam.shape)
    total = float(cam.sum())
    if total <= 1e-8:
        center_x = center_y = float("nan")
    else:
        center_x = float((xx * cam).sum() / total / max(cam.shape[1] - 1, 1))
        center_y = float((yy * cam).sum() / total / max(cam.shape[0] - 1, 1))
    high = cam >= max(float(np.quantile(cam, 0.90)), 1e-8)
    return {
        "shape": [int(cam.shape[0]), int(cam.shape[1])],
        "min": float(cam.min()),
        "max": float(cam.max()),
        "mean": float(cam.mean()),
        "center_x_norm": center_x,
        "center_y_norm": center_y,
        "top10_area_fraction": float(high.mean()),
    }


def verify_raw_logit_gradient(
    classifier: ChestXRayClassifier,
    gradcam: ChestGradCAM,
    input_tensor: torch.Tensor,
    target_idx: int,
) -> dict[str, float | int | list[int]]:
    model = classifier.get_model()
    captured: dict[str, torch.Tensor] = {}

    def forward_hook(_module, _inputs, output):
        output.retain_grad()
        captured["activation"] = output

    handle = gradcam.target_layer.register_forward_hook(forward_hook)
    model.zero_grad(set_to_none=True)
    logits = model(input_tensor)
    raw_logit = logits[0, target_idx]
    raw_logit.backward()
    handle.remove()

    activation = captured["activation"]
    grad = activation.grad
    return {
        "target_idx": int(target_idx),
        "raw_logit": float(raw_logit.detach().cpu()),
        "activation_shape": [int(v) for v in activation.shape],
        "gradient_shape": [int(v) for v in grad.shape],
        "gradient_abs_mean": float(grad.abs().mean().detach().cpu()),
        "gradient_abs_max": float(grad.abs().max().detach().cpu()),
    }


def collect_scores(
    classifier: ChestXRayClassifier,
    image_paths: list[Path],
    max_images: int,
) -> list[dict]:
    rows = []
    model = classifier.get_model()
    for path in image_paths[:max_images]:
        image = Image.open(path).convert("RGB")
        tensor = classifier.preprocess(image)
        with torch.no_grad():
            logits = model(tensor)[0].detach().cpu().numpy()
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))
        top_idx = int(np.argmax(probs))
        rows.append({
            "image": str(path),
            "top_label_by_raw_score": CLASS_LABELS[top_idx],
            "top_confidence_by_raw_score": round(float(probs[top_idx]), 6),
            "pneumothorax_score": round(float(probs[PNEUMOTHORAX_IDX]), 6),
            "scores": {label: round(float(score), 6) for label, score in zip(CLASS_LABELS, probs)},
            "logits": {label: round(float(score), 6) for label, score in zip(CLASS_LABELS, logits)},
        })
    return rows


def read_label_csv(labels_csv: Path, data_root: Path | None) -> list[tuple[Path, int]]:
    rows: list[tuple[Path, int]] = []
    with labels_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_value = row.get("path") or row.get("image") or row.get("Image Index") or row.get("filename")
            if not image_value:
                continue
            labels_text = "|".join([
                str(row.get("Finding Labels", "")),
                str(row.get("label", "")),
                str(row.get("labels", "")),
            ])
            explicit = row.get("Pneumothorax") or row.get("pneumothorax")
            if explicit is not None and str(explicit).strip() != "":
                y = int(float(explicit) > 0)
            else:
                y = int("Pneumothorax" in labels_text)
            path = Path(image_value)
            if not path.is_absolute() and data_root is not None:
                candidate = data_root / path
                if not candidate.exists():
                    matches = list(data_root.rglob(path.name))
                    candidate = matches[0] if matches else candidate
                path = candidate
            if path.exists():
                rows.append((path, y))
    return rows


def reliability_bins(confidences: np.ndarray, labels: np.ndarray, bins: int = 10) -> list[dict]:
    out = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (confidences >= lo) & (confidences < hi if i < bins - 1 else confidences <= hi)
        if mask.any():
            out.append({
                "bin_start": float(lo),
                "bin_end": float(hi),
                "count": int(mask.sum()),
                "confidence": float(confidences[mask].mean()),
                "accuracy": float(labels[mask].mean()),
            })
        else:
            out.append({
                "bin_start": float(lo),
                "bin_end": float(hi),
                "count": 0,
                "confidence": None,
                "accuracy": None,
            })
    return out


def save_reliability_plot(path: Path, bins: list[dict], title: str) -> None:
    canvas = np.full((640, 720, 3), 255, dtype=np.uint8)
    margin_left, margin_bottom = 90, 570
    plot_size = 460
    cv2.rectangle(canvas, (margin_left, margin_bottom - plot_size), (margin_left + plot_size, margin_bottom), (0, 0, 0), 1)
    cv2.line(canvas, (margin_left, margin_bottom), (margin_left + plot_size, margin_bottom - plot_size), (180, 180, 180), 2)
    for item in bins:
        if item["confidence"] is None:
            continue
        x0 = margin_left + int(item["bin_start"] * plot_size)
        x1 = margin_left + int(item["bin_end"] * plot_size)
        y = margin_bottom - int(item["accuracy"] * plot_size)
        cv2.rectangle(canvas, (x0 + 2, y), (x1 - 2, margin_bottom), (70, 130, 220), -1)
        cv2.rectangle(canvas, (x0 + 2, y), (x1 - 2, margin_bottom), (30, 70, 140), 1)
    cv2.putText(canvas, title, (50, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Predicted confidence", (190, 625), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Accuracy", (10, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas)


def temperature_scale(logits: np.ndarray, labels: np.ndarray) -> float:
    best_temp = 1.0
    best_loss = float("inf")
    for temp in np.linspace(0.5, 8.0, 151):
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits / temp, -60.0, 60.0)))
        eps = 1e-7
        loss = -np.mean(labels * np.log(probs + eps) + (1 - labels) * np.log(1 - probs + eps))
        if loss < best_loss:
            best_loss = float(loss)
            best_temp = float(temp)
    return best_temp


def run_calibration(
    classifier: ChestXRayClassifier,
    labeled_rows: list[tuple[Path, int]],
    output_dir: Path,
) -> dict:
    logits = []
    labels = []
    model = classifier.get_model()
    for path, label in labeled_rows:
        image = Image.open(path).convert("RGB")
        tensor = classifier.preprocess(image)
        with torch.no_grad():
            logit = float(model(tensor)[0, PNEUMOTHORAX_IDX].detach().cpu())
        logits.append(logit)
        labels.append(label)
    logits_np = np.asarray(logits, dtype=np.float32)
    labels_np = np.asarray(labels, dtype=np.float32)
    probs = 1.0 / (1.0 + np.exp(-np.clip(logits_np, -60.0, 60.0)))
    before_bins = reliability_bins(probs, labels_np)
    save_reliability_plot(output_dir / "calibration_before.png", before_bins, "Pneumothorax calibration: before")

    temp = temperature_scale(logits_np, labels_np)
    scaled_probs = 1.0 / (1.0 + np.exp(-np.clip(logits_np / temp, -60.0, 60.0)))
    after_bins = reliability_bins(scaled_probs, labels_np)
    save_reliability_plot(output_dir / "calibration_after.png", after_bins, f"Pneumothorax calibration: T={temp:.2f}")
    return {
        "images": len(labeled_rows),
        "positive": int(labels_np.sum()),
        "negative": int((1 - labels_np).sum()),
        "temperature": temp,
        "before_bins": before_bins,
        "after_bins": after_bins,
    }


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    images = local_chest_images()
    if args.image is not None:
        sample_path = args.image.resolve()
    elif images:
        sample_path = images[min(1, len(images) - 1)]
    else:
        raise RuntimeError("No local chest image found. Pass --image.")

    classifier = ChestXRayClassifier(model_path=str(args.model), device=args.device)
    gradcam = ChestGradCAM(classifier)
    model = classifier.get_model()
    sample = Image.open(sample_path).convert("RGB")
    result = classifier.predict(sample)
    tensor = classifier.preprocess(sample)

    print("SECTION 1: Grad-CAM implementation audit")
    print(f"Current target layer: {gradcam.target_layer_name} -> {gradcam.target_layer}")
    print(f"Global pooling layer: {getattr(model, 'global_pool', None)}")
    print(f"Predicted class: {result.top_label} ({result.confidence:.4f})")
    print(f"Grad-CAM target class: {result.heatmap_target_label} index={result.heatmap_target_idx}")
    grad_info = verify_raw_logit_gradient(classifier, gradcam, tensor, result.heatmap_target_idx)
    print("Raw-logit gradient check:", json.dumps(grad_info, indent=2))

    raw_cam = gradcam.generate_raw_cam(tensor, result.heatmap_target_idx, sample, apply_lung_mask=False)
    print("Raw CAM stats before colorization:", gradcam.last_raw_stats)
    print("Normalized raw CAM summary:", json.dumps(cam_summary(raw_cam), indent=2))

    crop, _ = gradcam._classifier_crop(sample, gradcam.HEATMAP_SIZE)
    unmasked = Image.fromarray(gradcam.generate_heatmap(sample, tensor, result.heatmap_target_idx, result.heatmap_target_label, apply_lung_mask=False))
    masked = Image.fromarray(gradcam.generate_heatmap(sample, tensor, result.heatmap_target_idx, result.heatmap_target_label, apply_lung_mask=True))
    mask = gradcam.create_lung_mask(sample, (gradcam.HEATMAP_SIZE, gradcam.HEATMAP_SIZE))
    before_after = pil_grid([
        ("classifier crop", crop),
        ("Grad-CAM unmasked", unmasked),
        ("Grad-CAM lung-masked", masked),
        ("lung mask", mask_to_rgb(mask)),
    ], columns=4)
    before_after.save(args.output_dir / "mask_before_after.png")
    print(f"Saved mask comparison: {args.output_dir / 'mask_before_after.png'}")
    print("Lung mask stats:", json.dumps(gradcam.last_mask_stats, indent=2))

    layer_names = ["conv_head", "blocks.6", "blocks.4"]
    layer_items = []
    layer_metrics = {}
    for name in layer_names:
        try:
            layer = module_by_name(model, name)
        except KeyError:
            continue
        cam = gradcam.generate_raw_cam(tensor, result.heatmap_target_idx, apply_lung_mask=False, target_layers=[layer])
        overlay = Image.fromarray(gradcam.generate_heatmap(sample, tensor, result.heatmap_target_idx, result.heatmap_target_label, apply_lung_mask=False, target_layers=[layer]))
        layer_items.append((name, overlay))
        layer_metrics[name] = cam_summary(cam)
    pil_grid(layer_items, columns=max(1, len(layer_items))).save(args.output_dir / "target_layer_compare.png")
    print(f"Saved layer comparison: {args.output_dir / 'target_layer_compare.png'}")
    print("Layer metrics:", json.dumps(layer_metrics, indent=2))

    method_items = []
    method_metrics = {}
    method_cams = {}
    for method in ["gradcam", "gradcam++", "eigencam"]:
        cam = gradcam.generate_raw_cam(tensor, result.heatmap_target_idx, apply_lung_mask=False, method=method)
        overlay = Image.fromarray(gradcam.generate_heatmap(sample, tensor, result.heatmap_target_idx, result.heatmap_target_label, apply_lung_mask=False, method=method))
        method_items.append((method, overlay))
        method_metrics[method] = cam_summary(cam)
        method_cams[method] = cam
    diffs = {}
    for left in method_cams:
        for right in method_cams:
            if left < right:
                diffs[f"{left}_vs_{right}"] = float(np.mean(np.abs(method_cams[left] - method_cams[right])))
    pil_grid(method_items, columns=3).save(args.output_dir / "saliency_method_compare.png")
    print(f"Saved saliency comparison: {args.output_dir / 'saliency_method_compare.png'}")
    print("Method metrics:", json.dumps(method_metrics, indent=2))
    print("Method mean absolute differences:", json.dumps(diffs, indent=2))

    score_rows = collect_scores(classifier, images, args.max_score_images)
    scores_path = args.output_dir / "raw_scores_10.json"
    scores_path.write_text(json.dumps(score_rows, indent=2), encoding="utf-8")
    print(f"Saved raw score dump: {scores_path}")
    print("Raw score summary:")
    for row in score_rows:
        print(f"  {Path(row['image']).name}: top={row['top_label_by_raw_score']} conf={row['top_confidence_by_raw_score']:.4f} pneumothorax={row['pneumothorax_score']:.4f}")

    calibration_report = {
        "status": "skipped",
        "reason": "No --labels-csv was supplied; local app DB has predictions but no ground-truth labels.",
    }
    if args.labels_csv is not None:
        labeled_rows = read_label_csv(args.labels_csv, args.data_root)
        if labeled_rows:
            calibration_report = run_calibration(classifier, labeled_rows, args.output_dir)
        else:
            calibration_report["reason"] = "The supplied label CSV did not resolve to local image files."
    (args.output_dir / "calibration_report.json").write_text(json.dumps(calibration_report, indent=2), encoding="utf-8")
    print("Calibration:", json.dumps(calibration_report, indent=2))

    training_report = {
        "dataset": "NIH ChestX-ray14-style labels",
        "label_type": "image-level weak labels from Finding Labels",
        "notebook": str(REPO_ROOT / "notebooks" / "train_chest_xray_effnetb4_colab.ipynb"),
        "training_config_observed": {
            "architecture": "timm efficientnet_b4",
            "num_classes": 15,
            "epochs": 3,
            "max_images": 20000,
            "split": "random train/validation split; notebook notes patient-level split is preferred for publication-grade training",
        },
    }
    (args.output_dir / "training_review.json").write_text(json.dumps(training_report, indent=2), encoding="utf-8")
    print("Training review:", json.dumps(training_report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
