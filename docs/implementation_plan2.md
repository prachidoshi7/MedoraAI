# Fix Chest X-Ray Classification, Heatmap, and Report Generation

## Root Cause Analysis

After thorough investigation, I found **three core problems**:

### Problem 1: Chest X-Ray Model Loads Fine-Tuned Weights But Likely Fails Silently

The `.env` has `CHEST_MODEL_PATH=./models/chest_xray_efficientnet_b4.pt` and a 67MB `.pt` file exists. The model loads fine. **However**, the training notebook uses `MAX_IMAGES = 20000` (out of 112K images) and only `EPOCHS = 3` — this is a quick smoke-test configuration, not a production training run. With only 18% of the dataset and 3 epochs, the model is severely undertrained.

**The real classification issue**: When the model's fine-tuned weights are weak or partially trained, `torch.sigmoid()` produces near-uniform low probabilities across all 15 classes. Since `MIN_PATHOLOGY_CONFIDENCE = 0.35`, the classifier often falls through to "No Finding" even for obvious pathology — or picks the wrong pathology due to poorly calibrated scores. **This is why it "hallucinates" — the model scores are essentially random noise from undertrained weights.**

> [!IMPORTANT]
> **We cannot retrain the model from here** (no GPU, no dataset). But we CAN make the inference pipeline more robust and honest about its limitations, and ensure the Grad-CAM and report generation work correctly with whatever the model produces.

### Problem 2: Heatmap is Already Real Grad-CAM But Has Issues

The [chest_gradcam.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/chest_gradcam.py) uses `pytorch-grad-cam` library with **real** Grad-CAM computation — it's not fake. However:
- When the model produces "No Finding" or low confidence, the code returns `generate_neutral_overlay()` which is just the plain image with **no heatmap at all** — so the user sees no Grad-CAM visualization
- Even when a pathology IS detected, the heatmap quality is poor because the undertrained model's gradient activations are noisy/diffuse
- The heatmap is resized to only 224×224 during generation then upscaled to 512×512 when saved — losing resolution

### Problem 3: Report Template Is Basic and Missing Key Sections

The [report.html](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/templates/report.html) template:
- Has **no heatmap image** embedded in the PDF report
- Has **no Grad-CAM methodology section** explaining what the heatmap shows
- Doesn't include model architecture details or training provenance  
- The template fallback report text is generic and doesn't feel like a real radiology report
- Missing a "Limitations" section that would be expected in AI-generated medical reports

---

## Proposed Changes

### Classifier Robustness & Honesty

#### [MODIFY] [chest_classifier.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/chest_classifier.py)
- **Lower `MIN_PATHOLOGY_CONFIDENCE` from `0.35` to `0.25`** — An undertrained model produces lower raw sigmoid scores. Setting the threshold too high causes everything to be classified as "No Finding" even when the model is weakly pointing at a real pathology. 0.25 is still conservative enough to avoid pure noise.
- **Add an `is_low_confidence` flag** to `ClassificationResult` when the top pathology score is between 0.25–0.50, so downstream code (report, heatmap) can indicate uncertainty
- **Add a `secondary_findings` list** to `ClassificationResult` containing all pathologies with score ≥ 0.20, so reports can mention differential considerations

---

### Heatmap — Make It Always Show Real Grad-CAM

#### [MODIFY] [chest_gradcam.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/chest_gradcam.py)
- **Always generate a real Grad-CAM heatmap**, even for "No Finding" — target the highest-scoring pathology class so the user can see what the model is "looking at" (and understand why it found nothing significant)
- Add a `heatmap_target_label` field to indicate which class the Grad-CAM was generated for
- Increase the heatmap overlay resolution — generate at input resolution, upscale smoothly

#### [MODIFY] [scan.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/routers/scan.py) — `_analyze_chest_xray()`
- Remove the "No Finding → neutral overlay" branch — always call `gradcam.generate_heatmap()` targeting the highest-scoring pathology
- Pass `heatmap_target_label` through to the analysis response so the frontend and report can show what the Grad-CAM is targeting
- Save the heatmap at a higher resolution (512×512 generation rather than 224→512 upscale)

---

### Report Generation — Complete Clinical Template

#### [MODIFY] [report.html](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/templates/report.html)
- **Add Grad-CAM Heatmap Image Section** — Embed the heatmap image directly in the PDF with a caption explaining "AI Attention Map (Grad-CAM) — Target: {label}"
- **Add AI Methodology Section** — Brief section explaining the model architecture (EfficientNet-B4 / MobileNetV2), Grad-CAM methodology, and that the heatmap represents actual gradient-weighted class activation
- **Add Limitations Section** — Standard clinical AI limitations paragraph  
- **Add Differential Considerations** — When secondary findings exist, list them
- **Improve visual design** — Better severity color coding, score visualization bars in the PDF, professional medical report formatting

#### [MODIFY] [llm_report_engine.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/llm_report_engine.py)
- Update `_generate_template_report()` to be more detailed and clinically structured (the fallback template is what runs when LLM keys fail/are missing)
- Add `is_low_confidence` handling — when the model is uncertain, the template report should clearly state this
- Add methodology text to the report data dict so the PDF template can render it
- Include `heatmap_target_label` in the report data

#### [MODIFY] [pdf_generator.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/pdf_generator.py)
- Pass the heatmap image path to the HTML template for embedding
- Update `render_html()` to include new template variables (methodology, limitations, heatmap path, secondary findings)

---

### Frontend — Better Communication of Heatmap Meaning

#### [MODIFY] [ScanViewer.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ScanViewer.tsx)
- Add a caption below the heatmap showing "Grad-CAM Target: {label}" so users understand what the heatmap is highlighting
- Add a subtitle explaining "This is an actual gradient-weighted class activation map computed from the model, not a simulated overlay"

#### [MODIFY] [ResultPanel.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ResultPanel.tsx)
- Show a "Low Confidence" warning badge when `is_low_confidence` is true
- Better visual distinction for the low-confidence state

---

## Open Questions

> [!IMPORTANT]
> **Model quality**: The trained model uses only 20K images and 3 epochs. If you want better accuracy, you would need to retrain with `MAX_IMAGES = None` (full 112K dataset) and `EPOCHS = 10-15` on a GPU. Do you have access to Colab/RunPod to retrain?

> [!IMPORTANT]
> **Heatmap embedding in PDF**: WeasyPrint (used for PDF generation) needs the heatmap as a file path or base64 data URI. I'll use base64 embedding so it works without a running server. Is this acceptable?

## Verification Plan

### Manual Verification
- Run the backend and upload a chest X-ray image
- Verify the Grad-CAM heatmap is always shown (even for "No Finding" cases)
- Verify the report PDF includes the heatmap, methodology section, and limitations
- Verify the frontend shows heatmap attribution labels
- Check that the template fallback report produces clinically structured text
