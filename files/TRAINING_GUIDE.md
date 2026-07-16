# MedoraAI — Multi-Task CXR Model Training Guide
### CheXpert backbone + SIIM-ACR/CANDID-PTX pneumothorax segmentation head

This guide walks through fixing the pneumothorax localization problem by fine-tuning
a shared backbone with an auxiliary segmentation head, using pixel-level pneumothorax
masks instead of only image-level labels.

---

## 1. Problem Recap

- Current model produces **bilateral, symmetric, rib-edge-hugging** Grad-CAM heatmaps
  for pneumothorax instead of a focal, unilateral pleural-line signature.
- Root cause: image-level-only labels (e.g. NIH ChestX-ray14 style) let the model learn
  a shortcut ("lung boundary texture present") instead of the real pathology location.
- Fix: add **pixel-level segmentation supervision** for the pneumothorax class so the
  shared conv features are forced to encode *where* the finding is, not just *that*
  it's present.

---

## 2. Datasets

| Stage | Dataset | Role | Access |
|---|---|---|---|
| 1 | **CheXpert** | Base 14-class multi-label classifier | Stanford AIMI — free registration, manual download (no direct wget) |
| 2 | **MIMIC-CXR** *(optional)* | Extra pretraining scale | PhysioNet — requires credentialing (CITI training) |
| 3 | **SIIM-ACR Pneumothorax Segmentation** | Pneumothorax **pixel masks** — fixes localization | Kaggle — `kaggle competitions download -c siim-acr-pneumothorax-segmentation` |
| 4 | **CANDID-PTX** | More pneumothorax masks + chest-tube labels (decouples tube shortcut) | Available via Zenodo / Edinburgh DataShare — registration form |
| 5 | Your own verified images | Final calibration / real-world test set | Internal |

> **CheXpert / MIMIC-CXR require manual, authenticated download** — they cannot be
> fetched with a plain script due to data use agreements. Register first, download
> the zip manually, then point the notebook's `CHEXPERT_ROOT` path at it.
>
> **SIIM-ACR** is retrievable via the Kaggle API if you have a `kaggle.json` API
> token — this is scripted in the notebook.

---

## 3. Architecture

```
                ┌─────────────────────┐
   Image ────►  │  Shared Backbone    │  (DenseNet-121, ImageNet or
                │  (feature extractor)│   CXR-pretrained init)
                └─────────┬───────────┘
                          │
             ┌────────────┴─────────────┐
             ▼                          ▼
   ┌───────────────────┐      ┌─────────────────────┐
   │ Classification head │      │ Segmentation head    │
   │ (14-class, BCE)     │      │ (pneumothorax only,  │
   │ GAP + FC            │      │  Dice+BCE, decoder)  │
   └───────────────────┘      └─────────────────────┘
```

- **Classification loss**: BCEWithLogits across all 14 CheXpert labels, applied to
  every batch.
- **Segmentation loss**: Dice + BCE, applied **only** to batches drawn from
  SIIM-ACR/CANDID-PTX (which have masks). Weight this loss so it doesn't dominate.
- **Total loss** = `cls_loss + λ * seg_loss` (start with `λ = 1.0`, tune if seg loss
  dominates/underfits).

---

## 4. Training Plan

| Phase | Data | Epochs | What's frozen |
|---|---|---|---|
| A — Base classifier | CheXpert | 10–15 | Nothing (train backbone + cls head from scratch/ImageNet init) |
| B — Multi-task fine-tune | CheXpert (cls) + SIIM-ACR/CANDID (cls+seg) | 10–20 | Optionally freeze early backbone layers for first few epochs |
| C — Calibration | Held-out verified set | — | Everything frozen; just evaluate + temperature scale |

Use **early stopping** on validation AUROC (classification) and validation Dice
(segmentation) — stop if both plateau for 3 consecutive epochs.

---

## 5. Smoke Test (before trusting the .pt file)

Before deploying `final_model.pt`, the notebook runs an automated smoke test:

1. Loads the checkpoint fresh (not from in-memory training state).
2. Runs inference on 3 held-out images (ideally: 1 known-positive pneumothorax with
   known laterality, 1 known-negative/normal, 1 arbitrary demo image).
3. Asserts:
   - Output shape and class count match expectations (14 classes).
   - Probabilities are in `[0, 1]`, no NaNs/Infs.
   - Segmentation output produces a non-trivial mask (not all-zero, not all-one) on
     the known-positive case.
   - Grad-CAM on the known-positive case has its centroid of mass inside the
     lung mask and skewed toward the labeled side (left/right), not symmetric.
4. Prints a pass/fail summary table.

If the smoke test fails on the laterality check, do **not** ship the checkpoint —
go back to Phase B and check segmentation loss curves / mask alignment first.

---

## 6. Files Produced

- `checkpoints/epoch_XX.pt` — per-epoch checkpoints (for resuming / rollback)
- `checkpoints/final_model.pt` — best checkpoint by validation Dice + AUROC
- `logs/training_log.csv` — per-epoch losses/metrics
- `smoke_test_report.json` — output of the final smoke test

---

## 7. Next Steps After This Notebook

1. Run the **laterality + normal-image control test** described earlier (known
   unilateral case vs. known normal case) using the newly trained model.
2. If Grad-CAM still activates both lungs equally, increase `λ` (segmentation loss
   weight) or add more SIIM-ACR/CANDID examples — the model needs stronger
   location supervision relative to classification supervision.
3. Build a small (100–200 image) clinician-verified test set for final calibration
   before any real deployment claim.
