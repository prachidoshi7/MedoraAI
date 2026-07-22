# Model Files

This directory stores local model artifacts used by the backend.

Expected files:

```text
chest_xray_efficientnet_b4.pt
chest_xray_efficientnet_b4.labels.json
best_brain_model.keras
```

`.env` should point to them from the repo root:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/best_brain_model.keras
```

## Chest X-Ray Model

- Architecture: `timm` EfficientNet-B4
- Backend constructor: `timm.create_model("efficientnet_b4", pretrained=True, num_classes=15)`
- Weight format: PyTorch `state_dict`
- Label manifest: `chest_xray_efficientnet_b4.labels.json`

The label order must match `backend/services/chest_classifier.py`.

## Brain MRI Model

- Architecture: EfficientNetB3, four classes
- Classes: Glioma, Meningioma, No Tumor, Pituitary
- Weight format: Keras `.keras`
- Loaded by `backend/services/brain_classifier.py`

`best_brain_model.keras` is ignored because it exceeds GitHub's normal file-size limit. Supply it locally, use Git LFS, or distribute it through a private release. `brain_tumor_mobilenetv2.h5` is retained only as a legacy artifact.

## Importing A Chest Export Zip

If `medoraai_chest_xray_model_export.zip` exists in the repo root:

```powershell
Expand-Archive -LiteralPath .\medoraai_chest_xray_model_export.zip -DestinationPath . -Force
```

Then verify:

```powershell
Get-ChildItem .\models
```

Do not commit large model artifacts unless the team explicitly decides to version them.
