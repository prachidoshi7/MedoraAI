# Model Evaluation Guide

Use this guide when predictions look inaccurate. Prompt changes can reduce report hallucination, but they cannot improve model accuracy. Accuracy must be measured against labeled images.

## Chest X-Ray Evaluation

The chest model expects NIH ChestX-ray14-style labels and the backend label order in `backend/services/chest_classifier.py`.

Run from the repo root:

```powershell
python tools/evaluate_chest_model.py --data-root C:\path\to\nih_chest_xray14 --max-images 2000
```

For the full dataset:

```powershell
python tools/evaluate_chest_model.py --data-root C:\path\to\nih_chest_xray14 --output-json chest_eval.json
```

The script reports:

```text
macro_auc
exact_match_accuracy
macro_f1
micro_f1
per-label precision, recall, f1, AUC, and support
```

Use `--max-images` for a quick smoke test. Use the full dataset for real conclusions.

## Thresholds

The backend does not report a chest pathology unless the best pathology score is at least:

```text
0.35
```

This is defined as `MIN_PATHOLOGY_CONFIDENCE` in:

```text
backend/services/chest_classifier.py
```

If the model produces many false positives, increase this threshold. If it misses too many true cases, lower it after checking evaluation metrics.

## Input Validation

The backend rejects obvious scan-type mismatches before inference. For chest X-ray uploads, it checks:

```text
- minimum image size
- DICOM modality is not MRI/CT/ultrasound/nuclear medicine
- image is approximately grayscale
- image has enough radiograph-like contrast
- image does not look like a centered brain/MRI slice
- image has a coarse paired lung-field pattern
```

This prevents the chest classifier from producing confident-looking labels for arbitrary photos or screenshots. It is still a heuristic; a dedicated out-of-distribution detector would be needed for robust production validation.

## Heatmap Notes

Grad-CAM is an attention map, not a radiologist-confirmed lesion location.

For chest X-rays, the backend now suppresses lesion-style boxes when:

```text
top_label == "No Finding"
confidence < MIN_PATHOLOGY_CONFIDENCE
```

In those cases, the app returns a neutral image instead of a misleading heatmap.

## Report Hallucination Controls

The report engine has chest-specific guardrails:

- Gemini is tried first when `GEMINI_API_KEY` is configured. It receives the uploaded image and the ML output.
- LLM prompt only exposes model-supported chest scores above 20%.
- The prompt forbids invented anatomy, laterality, measurements, devices, and unsupported diseases.
- LLM temperature is set to `0.0`.
- If an LLM chest report mentions unsupported chest labels or invented specifics, the backend falls back to the deterministic template report.

If reports still overstate findings, disable external LLM keys in `.env` and use the template fallback.
