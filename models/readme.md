# Model Files

This directory contains only the model binaries bundled with MedoraAI:

```text
best_brain_model.keras
cnn_lung_model.pth
cnn_Kidney_Stone_model.pth
```

Configure their repo-relative paths in `.env`:

```env
BRAIN_MODEL_PATH=./models/best_brain_model.keras
LUNG_MODEL_PATH=./models/cnn_lung_model.pth
KIDNEY_MODEL_PATH=./models/cnn_Kidney_Stone_model.pth
```

All three binaries are tracked with Git LFS. Run `git lfs install` before
cloning and `git lfs pull` when a checkout contains pointer files.

## Chest X-Ray

Chest inference no longer uses the local EfficientNet-B4 artifact. It uses a
pinned RAD-DINO ViT-B/14 encoder with a 14-label CheXpert classification head:

```env
CHEST_MODEL_ID=kaan-ylmn/rad-dino-chexpert
CHEST_MODEL_REVISION=db02e1b7234dd83c6d7c4485963ef5b22df9e5db
CHEST_DEVICE=auto
CHEST_PATHOLOGY_THRESHOLD=0.50
CHEST_SECONDARY_THRESHOLD=0.35
```

The first backend startup downloads the approximately 346 MB checkpoint to the
Hugging Face cache. The revision is immutable, and MedoraAI defines the reviewed
model architecture locally instead of executing remote Python. For an offline
deployment, populate the cache first and set:

```env
CHEST_MODEL_LOCAL_FILES_ONLY=true
```

RAD-DINO and this application are research decision-support components, not
certified medical devices. Model scores and attribution maps require clinician
review.

## Brain MRI

- Architecture: EfficientNetB3, four classes
- Classes: Glioma, Meningioma, No Tumor, Pituitary
- Weight format: Keras `.keras`

## Lung CT and Kidney Ultrasound

The compact PyTorch state dictionaries load through the architectures in
`backend/services/lung_classifier.py` and
`backend/services/kidney_classifier.py`.
