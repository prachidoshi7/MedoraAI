# MedoraAI Training Notebooks

Use these notebooks in a GPU notebook environment such as RunPod, Colab, or another Jupyter server.

## Chest X-ray

Notebook:

```text
train_chest_xray_effnetb4_colab.ipynb
```

Output:

```text
chest_xray_efficientnet_b4.pt
```

Copy it into:

```text
models/chest_xray_efficientnet_b4.pt
```

Also copy the label manifest:

```text
models/chest_xray_efficientnet_b4.labels.json
```

Set local `.env`:

```env
CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt
```

The current backend expects 15 NIH ChestX-ray14-style labels. The PDFs in `docs/R.P` describe CheXpert-14, which is not label-compatible with the current backend unless `CLASS_LABELS` and the model output head are changed.

### RunPod Notes

The current chest training notebook auto-detects the extracted NIH ChestX-ray14 dataset in this order:

```text
/root/nih_chest_xray14_fast
/workspace/nih_chest_xray14
```

Use `/root/nih_chest_xray14_fast` for faster local-disk training when the dataset has already been extracted there. Keep final exported model files under `/workspace` so they survive pod restarts.

Before closing a pod, download:

```text
/workspace/medoraai_chest_xray_model_export.zip
/workspace/chest_xray_efficientnet_b4.pt
/workspace/chest_xray_efficientnet_b4.labels.json
```

The export zip should contain:

```text
models/chest_xray_efficientnet_b4.pt
models/chest_xray_efficientnet_b4.labels.json
```

After copying the zip into the local repo root, extract it:

```powershell
Expand-Archive -LiteralPath .\medoraai_chest_xray_model_export.zip -DestinationPath . -Force
```

The BCE baseline model should remain the production candidate unless AUC fine-tuning improves validation AUC.

## Brain MRI

Notebook:

```text
train_brain_mri_mobilenetv2_colab.ipynb
```

Output:

```text
brain_tumor_mobilenetv2.h5
```

Copy it into:

```text
models/brain_tumor_mobilenetv2.h5
```

Set local `.env`:

```env
BRAIN_MODEL_PATH=./models/brain_tumor_mobilenetv2.h5
```

## Groq Report Flow

The trained model produces structured output:

```text
top_label
confidence
all_scores
severity
```

That text output is sent to Groq by `backend/services/llm_report_engine.py`. The uploaded image itself is not sent to Groq.
