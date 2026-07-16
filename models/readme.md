# Model Files

This directory stores local model artifacts used by the backend.

Expected files:

```text
chest_xray_efficientnet_b4.pt
chest_xray_efficientnet_b4.labels.json
brain_tumor_mobilenetv2.h5
```

`.env` should point to them from the repo root:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
BRAIN_MODEL_PATH=./models/brain_tumor_mobilenetv2.h5
```

## Chest X-Ray Model

- Architecture: `timm` EfficientNet-B4
- Backend constructor: `timm.create_model("efficientnet_b4", pretrained=True, num_classes=15)`
- Weight format: PyTorch `state_dict`
- Label manifest: `chest_xray_efficientnet_b4.labels.json`

The label order must match `backend/services/chest_classifier.py`.

## Brain MRI Model

- Architecture: MobileNetV2
- Weight format: Keras `.h5`
- Loaded by `backend/services/brain_classifier.py`

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
