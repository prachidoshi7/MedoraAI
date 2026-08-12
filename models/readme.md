# Model Files

This directory stores local model artifacts used by the backend.

Expected files:

```text
chest_xray_efficientnet_b4.pt
chest_xray_efficientnet_b4.labels.json
best_brain_model.keras
cnn_lung_model.pth
cnn_Kidney_Stone_model.pth
```

`.env` should point to them from the repo root:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/best_brain_model.keras
LUNG_MODEL_PATH=./models/cnn_lung_model.pth
KIDNEY_MODEL_PATH=./models/cnn_Kidney_Stone_model.pth
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

All runtime model binaries in this directory are tracked with Git LFS. Run
`git lfs install` before cloning and `git lfs pull` if a checkout contains
pointer files. The incompatible legacy MobileNet artifact is intentionally
excluded from the runnable repository.

## Lung CT and Kidney Ultrasound

The two compact PyTorch state dictionaries are committed under `models/` and
load automatically after a normal clone. Their model architectures live in
`backend/services/lung_classifier.py` and `backend/services/kidney_classifier.py`.

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
