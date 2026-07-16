# Upgrade Brain Tumor Classifier: MobileNetV2 → EfficientNetB3 (4-Class)

## Background

The current MedoraAI backend uses a **MobileNetV2 binary classifier** (Tumor / No Tumor) at 128×128 resolution with a 21MB `.h5` model. Your new notebook in `brainnn/` trained a far superior **EfficientNetB3 4-class classifier** (Glioma, Meningioma, No Tumor, Pituitary) at 260×260 resolution using progressive 3-phase fine-tuning, achieving 90%+ accuracy with TTA.

### Files in `brainnn/`:
| File | Size | Purpose |
|---|---|---|
| `brain-tumor-mri-90plus-upgraded (1).ipynb` | 34KB | Training notebook — EfficientNetB3, 3-phase fine-tuning, TTA, full diagnostics |
| `best_brain_model.keras` | 208MB | Best checkpoint by `val_accuracy` during training (ModelCheckpoint) |
| `brain_tumor_efficientnetb3_final.keras` | 231MB | Final model saved after loading best weights — **designated deployment model** |

### Key Differences (Old → New)

| Aspect | Old (MobileNetV2) | New (EfficientNetB3) |
|---|---|---|
| Architecture | MobileNetV2 (Sequential) | EfficientNetB3 (Functional API) |
| Input Size | 128×128 | 260×260 |
| Classes | 2 (Tumor / No Tumor) | 4 (Glioma, Meningioma, No Tumor, Pituitary) |
| Output | Sigmoid (binary) | Softmax (4-class) |
| Preprocessing | Normalize 0–1 (`/255`) | `efficientnet.preprocess_input` (ImageNet scaling) |
| Brain Cropping | None | Contour-based crop (from notebook) |
| Model Format | `.h5` | `.keras` |
| Model Size | 21MB | ~208MB |

## User Review Required

> [!IMPORTANT]
> **Model Selection**: The notebook produces two models. I recommend using `best_brain_model.keras` (208MB) — it's the best checkpoint by validation accuracy and is smaller. The `brain_tumor_efficientnetb3_final.keras` (231MB) contains the same weights but includes optimizer state (extra ~23MB of overhead). Both will produce identical predictions.

> [!WARNING]
> **Breaking Change**: The brain classifier will now output 4 classes instead of 2. Any saved analysis results in the database from the old model won't match the new label set. Existing history entries will show old labels ("Tumor"/"No Tumor") but new scans will show specific tumor types.

> [!IMPORTANT]
> **TTA at Inference**: The notebook uses Test-Time Augmentation (TTA) at inference for extra accuracy. I'll implement an optional TTA mode — enabled by default but with a toggle, since TTA is ~5× slower than single-pass inference (runs 5 forward passes per image). For real-time web usage, single-pass may be preferred.

## Open Questions

> [!IMPORTANT]
> 1. **Which model to use?** `best_brain_model.keras` (208MB, recommended) or `brain_tumor_efficientnetb3_final.keras` (231MB)? Both have the same weights; the smaller one skips optimizer state.
> 2. **TTA default?** Should Test-Time Augmentation be ON by default (slower but more accurate) or OFF (faster, ~92%+ accuracy still)?

## Proposed Changes

### Model File Setup

#### Copy model to deployment location
- Copy the selected `.keras` model from `brainnn/` to `models/` directory (where the backend loads from)

---

### Backend Core — Brain Classifier

#### [MODIFY] [brain_classifier.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/brain_classifier.py)
**Complete rewrite** to support EfficientNetB3 4-class classification:

- **Labels**: `["Glioma", "Meningioma", "No Tumor", "Pituitary"]` (matching notebook's `LABELS` list)
- **Input**: 260×260 RGB with `efficientnet.preprocess_input` scaling
- **Brain Cropping**: Port `crop_brain_contour()` from notebook for preprocessing
- **Prediction**: 4-class softmax output → top class + all class probabilities
- **TTA**: Optional Test-Time Augmentation (average over flips + small rotations)
- **Severity Mapping**: Updated for 4 specific tumor types (Glioma/Meningioma more severe than Pituitary)
- **Fallback**: If model file missing, log warning (no fresh MobileNetV2 build — the old fallback was useless clinically)

---

### Backend Core — Brain Grad-CAM

#### [MODIFY] [brain_gradcam.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/brain_gradcam.py)
**Rewrite** for EfficientNetB3 Functional API model:

- **Model structure**: EfficientNetB3 Functional model (not `model.layers[0]` Sequential access)
- **Target layers**: `top_activation` (~8×8, 1536ch) + `block6a_expand_activation` (~16×16) for EfficientNetB3
- **Grad-CAM++ output**: Target predicted class index via softmax (not `predictions[:, 0]` sigmoid)
- **Input size**: 260×260 preprocessing pipeline
- **Multi-scale fusion**: Keep existing weighted fusion approach, just retarget layers
- **Dynamic layer discovery**: Auto-detect best conv layers if expected names aren't found

---

### Backend Configuration

#### [MODIFY] [config.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/config.py)
- Update `BRAIN_MODEL_PATH` description from `.h5` → `.keras`, MobileNetV2 → EfficientNetB3

#### [MODIFY] [.env](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/.env)
- Change `BRAIN_MODEL_PATH` from `./models/brain_tumor_mobilenetv2.h5` to `./models/best_brain_model.keras`

#### [MODIFY] [main.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/main.py)
- Update startup log message: `MobileNetV2` → `EfficientNetB3 (4-class)`

---

### Backend — LLM Report Engine

#### [MODIFY] [llm_report_engine.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/llm_report_engine.py)
- **Brain MRI prompt**: Update to include 4-class labels (Glioma, Meningioma, No Tumor, Pituitary) with tumor-type-specific reporting rules
- **Template reports**: Add tumor-type-specific findings/impression/recommendations for each of the 4 classes
- **Methodology text**: Update from MobileNetV2 → EfficientNetB3, binary → 4-class, mention progressive fine-tuning

---

### Backend — Scan Router

#### [MODIFY] [scan.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/routers/scan.py)
- No structural changes needed — it delegates to `classifier.predict()` and `gradcam.generate_heatmap()`, which we're rewriting. The interface contract (result object with `top_label`, `confidence`, `all_scores`, `severity`) stays the same.

---

### Frontend Types

#### [MODIFY] [index.ts](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/types/index.ts)
- Update brain MRI `ScanTypeConfig`:
  - `model`: `'MobileNetV2'` → `'EfficientNetB3'`
  - `description`: Binary → 4-class tumor classification
  - `classes`: `'Tumor / No Tumor'` → `'Glioma, Meningioma, No Tumor, Pituitary'`

---

### Frontend Components

#### [MODIFY] [ResultPanel.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ResultPanel.tsx)
- Minor: ensure 4 classes render properly in the score bars (currently dynamic, should work, but verify)

---

## Verification Plan

### Automated Tests
```bash
# 1. Start backend and check model loads without errors
cd backend && python -c "from services.brain_classifier import BrainTumorClassifier; c = BrainTumorClassifier(model_path='../models/best_brain_model.keras'); print('OK')"

# 2. Health check
curl http://localhost:8000/health
```

### Manual Verification
1. Start backend with `uvicorn main:app --reload` and verify EfficientNetB3 loads in logs
2. Upload a brain MRI through the frontend and verify:
   - 4-class classification results appear (Glioma/Meningioma/No Tumor/Pituitary)
   - Grad-CAM heatmap renders correctly
   - LLM report mentions specific tumor type
   - All score bars show 4 classes
3. Upload a chest X-ray to verify chest pipeline is unaffected
