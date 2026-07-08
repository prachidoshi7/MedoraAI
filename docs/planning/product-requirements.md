# Product Requirements Document
## Multi-Modal Medical Image Diagnosis and Automated Clinical Reporting Engine

**Version:** 1.0  
**Date:** 2026-06-27  
**Status:** Draft — Hackathon Scope  
**Team:** _[to be filled by team]_

---

## 1. Executive Summary

This product is a web-based AI diagnostic assistant that enables radiologists to upload medical scans (chest X-rays, CT slices), receive real-time AI-powered pathology classification with visual explanations (Grad-CAM heatmaps and bounding boxes), automated severity assessment, and a structured draft clinical report — all within a single browser-based portal. The primary users are radiologists and clinical staff who currently spend 15–20 minutes per study on routine reads. According to the Association of University Radiologists, the United States faces a projected shortfall of **5,000 radiologists by 2033**, while global imaging volumes grow 5–8% annually. This tool directly addresses diagnostic delay and radiologist fatigue by automating triage, anomaly flagging, and first-draft reporting, allowing clinicians to focus expert attention on complex cases.

---

## 2. Problem Statement

### 2.1 Clinical Context

The current diagnostic imaging workflow is sequential and labor-intensive:

1. **Image Acquisition** — Technician captures the scan (X-ray, CT, MRI) and stores it in a PACS (Picture Archiving and Communication System).
2. **Manual Review** — A radiologist opens the study in a PACS viewer, scrolls through slices (CTs can have 500+ slices), identifies abnormalities, and mentally synthesizes findings.
3. **Report Dictation** — The radiologist dictates or types a structured free-text report, which goes through transcription, review, and signing.
4. **Communication** — Critical findings must be verbally communicated to the referring physician; non-urgent reports are released into the EMR.

**Failure modes in this workflow:**

- **Missed findings:** Satisfaction-of-search errors occur in 20–30% of cases where a secondary finding is missed after a primary abnormality is detected (Berbaum et al., *Radiology*, 2010).
- **Report turnaround time:** Average radiology report turnaround in emergency settings is 1–4 hours; overnight reads may take 8–12 hours. Delays in stroke and hemorrhage detection directly correlate with worse patient outcomes.
- **Radiologist fatigue:** A study in the *Journal of the American College of Radiology* found that radiologists who read more than 100 studies per day show a statistically significant increase in error rates during the final quarter of their shift.

**AI-assisted radiology evidence:**

- CheXNet (Rajpurkar et al., 2017) demonstrated radiologist-level performance on 14-class chest X-ray pathology detection using DenseNet-121.
- A 2020 *Nature Medicine* study showed that AI-assisted reads reduced false negatives by 11% and false positives by 5% compared to unassisted radiologist reads.
- Google Health's LYNA system achieved 99% accuracy in detecting metastatic breast cancer in lymph node biopsies, outperforming pathologists with a 38% lower miss rate.

### 2.2 The Gap

- **Commercial solutions are inaccessible for most:** Aidoc, Viz.ai, and Zebra Medical require enterprise contracts ($50K–$500K/year), deep EMR/PACS integration, and FDA 510(k) clearance before deployment. These are out of reach for smaller clinics, academic centers in developing countries, and research teams.
- **Existing open-source efforts are fragmented:** CheXNet repos exist but lack a clinical UI, report generation, severity mapping, or deployment packaging. There is no integrated open pipeline from scan upload to PDF report.
- **Hackathon opportunity:** Build an open, modular, explainable pipeline that demonstrates the full AI-assisted radiology workflow end-to-end — from image upload to downloadable clinical report — in a single deployable package. The system prioritizes **explainability** (every AI decision has a visual explanation) and **usability** (a clinician can operate it without training).

---

## 3. Goals & Non-Goals

### 3.1 Goals (MVP — must be working at demo time)

| # | Goal | Measurable Outcome |
|---|------|--------------------|
| G1 | Upload a medical scan and receive a classification result in real time | JPEG/PNG upload → classification result displayed within 5 seconds on CPU |
| G2 | Anomaly localization rendered visually on the scan | Grad-CAM heatmap overlaid on the original image with toggle control |
| G3 | Confidence score per prediction | Numerical score (0–100%) displayed alongside the top classification label |
| G4 | Automated severity assessment | Severity label (Normal / Mild / Moderate / Severe) derived from model confidence and displayed in the results panel |
| G5 | Structured draft clinical report auto-generated | Report includes patient ID placeholder, scan type, findings, impression, severity, and disclaimer — generated with zero manual input |
| G6 | Secure clinician-facing web portal | Browser-based (Chrome/Firefox), session-authenticated, no installation required |
| G7 | PDF report export | Clinician can download a formatted PDF of the AI-generated report |
| G8 | One-command deployment | Entire system starts with `docker compose up` on any machine with Docker installed |

### 3.2 Non-Goals (explicitly out of scope)

- **HIPAA / HL7 FHIR compliance** — Noted as critical for production but not required for hackathon demo. No real patient data is used.
- **EMR/PACS integration** — No HL7 messaging, DICOM networking (C-STORE/C-FIND), or FHIR resource exchange.
- **Training a model from scratch** — Use pretrained weights (ImageNet + CheXNet-style); fine-tuning is a stretch goal.
- **Real patient data** — Demo uses only public datasets (NIH ChestX-ray14, RSNA ICH).
- **Mobile application** — Web portal only; responsive design is P2.
- **Multi-user concurrent access** — Single-user demo; no load balancing or session management for multiple clinicians.
- **FDA/CE regulatory submission** — The prototype is a research/demo tool, not a regulated medical device.

---

## 4. Users & Personas

### Persona 1: Dr. Radha M. — Staff Radiologist, District Hospital

| Attribute | Detail |
|-----------|--------|
| **Role** | General radiologist, solo practice covering ER and outpatient |
| **Daily volume** | 80–100 studies/day (70% chest X-rays, 20% CT, 10% other) |
| **Tech comfort** | Uses PACS daily, comfortable with web apps, does not code |
| **Primary want** | Fast triage — flag abnormal studies so she can prioritize complex cases |
| **Secondary want** | Draft report she can edit and sign, saving 5–10 min per study |
| **Pain point** | Repetitive normal chest X-rays consume 40% of her time; fatigue-induced errors increase after 3pm |
| **Demo expectation** | Upload a scan, see the AI's opinion with a heatmap, edit and download a report |

### Persona 2: Prof. James K. — Hackathon Judge / Clinical Informatics Faculty

| Attribute | Detail |
|-----------|--------|
| **Role** | Evaluator assessing technical merit, clinical plausibility, and demo quality |
| **Primary want** | Working end-to-end demo; clear AI output that is clinically reasonable |
| **Secondary want** | Evidence that the system handles edge cases (normal scans, ambiguous findings) |
| **Pain point** | Vague prototypes that only work on one pre-loaded image; systems that crash on upload |
| **Demo expectation** | Upload 3–5 different images, see varied results, verify the heatmap highlights plausible regions |

---

## 5. Functional Requirements

### 5.1 Image Ingestion

| ID | Requirement | Acceptance Criterion | Priority |
|----|-------------|----------------------|----------|
| FR-01 | User can upload a medical image via drag-and-drop or file picker | File appears in preview within 2s of upload | P0 |
| FR-02 | System accepts JPEG, PNG, and DICOM (.dcm) formats | All three formats render correctly in the image viewer | P0 |
| FR-03 | Image is validated on upload (not corrupted, readable, within size limits) | Invalid files show a descriptive error message, not a crash; max file size 20MB | P1 |
| FR-04 | DICOM metadata (modality, patient ID placeholder, study date) is extracted and displayed | Metadata fields populate the results panel when a DICOM file is uploaded | P1 |

### 5.2 AI Inference Pipeline

| ID | Requirement | Acceptance Criterion | Priority |
|----|-------------|----------------------|----------|
| FR-05 | System classifies scan into at least 5 pathology classes + Normal | Classification result returned within 5s on CPU, 2s on GPU | P0 |
| FR-06 | System generates a Grad-CAM heatmap over anomalous regions | Heatmap overlay renders correctly on top of the original image with a toggle to show/hide | P0 |
| FR-07 | Confidence score (0–100%) returned per prediction | Score displayed in the UI alongside the top class label; all class scores visible in expanded view | P0 |
| FR-08 | Severity level assigned: Normal / Mild / Moderate / Severe | Severity maps to confidence thresholds defined in config; color-coded badge displayed | P0 |
| FR-09 | Multi-modal support: at minimum X-ray; CT as stretch | X-ray produces valid classification + heatmap output | P0 (X-ray) / P1 (CT) |
| FR-10 | Bounding boxes drawn over detected anomaly regions (YOLOv8) | Boxes render on the scan viewer canvas with label and confidence | P2 |

### 5.3 Clinical Report Generation

| ID | Requirement | Acceptance Criterion | Priority |
|----|-------------|----------------------|----------|
| FR-11 | System generates a structured draft report per scan | Report includes: patient ID placeholder, scan date, modality, findings, impression, severity, and disclaimer | P0 |
| FR-12 | Report is editable by the clinician before download | Text area in the UI allows editing of the findings and impression sections | P1 |
| FR-13 | Report downloadable as PDF | PDF renders correctly with all fields, formatted with report header and disclaimer | P1 |
| FR-14 | LLM-enhanced report prose (if API key available) | Findings section uses clinical radiology language; fallback to template if no API key | P2 |

### 5.4 Clinician Portal

| ID | Requirement | Acceptance Criterion | Priority |
|----|-------------|----------------------|----------|
| FR-15 | Web portal accessible via modern browser (Chrome/Firefox/Edge) | No installation required; page loads in < 3s | P0 |
| FR-16 | Portal displays scan + heatmap + classification + severity + report in a unified view | All 5 elements visible without scrolling on a 1920×1080 display | P0 |
| FR-17 | Session-based authentication (username/password) | Unauthenticated requests are rejected with HTTP 401; demo credentials work on first attempt | P1 |
| FR-18 | Scan history: list of previously uploaded scans in the current session | Up to 10 scans listed with thumbnail, top label, severity, and timestamp | P2 |
| FR-19 | Dark mode UI with medical-grade color scheme | UI uses dark backgrounds with high-contrast text, suitable for dimly-lit reading rooms | P1 |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | Inference completes in < 5 seconds on CPU (no GPU assumed for demo environment); UI remains responsive during inference (loading state shown) |
| **Availability** | Service runs locally via Docker Compose; no uptime SLA for hackathon. System should not crash during demo (target: 10 consecutive uploads without failure) |
| **Security** | No real patient data used. JWT-based session authentication. HTTPS if deployed to cloud (not required for localhost). File upload validated by magic bytes, not just extension. |
| **Explainability** | Every AI classification decision is accompanied by a Grad-CAM visual explanation. Confidence scores are always shown. Disclaimer on every report. |
| **Portability** | Entire system starts with `docker compose up`. Works on macOS, Linux, and Windows (WSL2). No GPU driver required (CPU inference). |
| **Scalability** | Not a requirement for hackathon. Single-user, single-machine deployment. |
| **Accessibility** | Keyboard navigable; sufficient color contrast (WCAG AA) for all text elements. |

---

## 7. User Journey — Happy Path

```
Step 1:  Clinician opens browser → navigates to http://localhost:3000
Step 2:  Sees login screen → enters demo credentials (demo / demo123)
Step 3:  Authenticated → redirected to Upload page
Step 4:  Sees drag-and-drop upload zone → drags in a chest X-ray PNG file
Step 5:  File preview appears → clicks "Analyze Scan" button
Step 6:  Loading spinner appears → "Analyzing scan..." with progress animation
Step 7:  Results page loads (< 5 seconds after clicking Analyze):
         ├── Left panel (60%): Original scan with Grad-CAM heatmap overlay
         │   └── Toggle button: "Original" / "Heatmap" / "Side-by-Side"
         ├── Right panel (40%):
         │   ├── Classification: "Pneumonia" (large, red badge for Severe)
         │   ├── Confidence: 87% (horizontal progress bar)
         │   ├── Severity: "Severe" (color-coded badge)
         │   ├── All class scores (expandable list)
         │   └── Editable draft report (auto-populated textarea)
         └── Action bar: "Download PDF" button, "New Scan" button
Step 8:  Clinician reviews heatmap → sees highlighted right lower lobe
Step 9:  Clinician edits the report findings (optional)
Step 10: Clicks "Download PDF" → formatted report saved to local Downloads
Step 11: Scan appears in the History sidebar (thumbnail + result summary)
Step 12: Clinician clicks "New Scan" → returns to Upload page for next study
```

---

## 8. Success Metrics (Demo Day)

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| End-to-end time (upload → results displayed) | < 5 seconds on CPU | Timed during live demo |
| Classification accuracy on demo dataset | > 80% top-1 accuracy on selected NIH ChestX-ray14 test images | Pre-validated before demo |
| Heatmap highlights clinically correct region | Qualitative assessment | Judge visual inspection; confirmed against known pathology location |
| Report generated without manual input | 100% of uploads produce a report | Tested with all 10 demo images |
| System stability | 5 consecutive uploads without crash | Tested during live demo |
| PDF download succeeds | 100% of generated reports downloadable | Tested during live demo |
| Login → result in under 30 seconds | < 30 seconds total user workflow | Timed during live demo |

---

## 9. Demo Dataset

### Primary Dataset: NIH ChestX-ray14
- **Source:** National Institutes of Health Clinical Center
- **Size:** 112,120 frontal-view chest X-ray images from 30,805 unique patients
- **Labels:** 14 disease labels (Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass, Nodule, Pneumonia, Pneumothorax, Consolidation, Edema, Emphysema, Fibrosis, Pleural Thickening, Hernia) + "No Finding"
- **Download:** https://nihcc.app.box.com/v/ChestXray-NIHCC
- **License:** CC0 1.0 (public domain)

### Secondary Dataset (stretch — CT support): RSNA Intracranial Hemorrhage Detection
- **Source:** Kaggle (RSNA 2019 competition)
- **Size:** ~750,000 CT slice images with 5 hemorrhage subtypes
- **Use:** Demonstrate CT modality support if time permits

### Demo Image Bundle (`demo_data/` folder)
Pre-select **10 representative images** bundled with the repository:

| # | Filename | Pathology | Purpose |
|---|----------|-----------|---------|
| 1 | `normal_01.png` | No Finding | Baseline normal scan |
| 2 | `normal_02.png` | No Finding | Second normal for variety |
| 3 | `pneumonia_01.png` | Pneumonia | Classic right lower lobe consolidation |
| 4 | `pneumonia_02.png` | Pneumonia | Left-sided, less obvious |
| 5 | `effusion_01.png` | Pleural Effusion | Clear meniscus sign |
| 6 | `cardiomegaly_01.png` | Cardiomegaly | Enlarged cardiac silhouette |
| 7 | `mass_01.png` | Mass/Nodule | Solitary pulmonary nodule |
| 8 | `pneumothorax_01.png` | Pneumothorax | Visible pleural line |
| 9 | `atelectasis_01.png` | Atelectasis | Lobar collapse |
| 10 | `multi_finding_01.png` | Effusion + Infiltration | Multi-label case for robustness |

> [Assumption] Demo images will be sourced from the NIH ChestX-ray14 dataset under its CC0 license and resized to 1024×1024 PNG for fast loading.

---

## 10. Open Questions

These decisions should be resolved by the team before or during the first 2 hours of the hackathon:

| # | Question | Impact | Recommended Default |
|---|----------|--------|---------------------|
| 1 | Is a GPU available in the demo/judging environment? | Affects model size choice. EfficientNet-B4 runs ~1.5s on CPU vs ~0.2s on GPU. | Assume CPU only; use EfficientNet-B4 which is fast enough. |
| 2 | Will judges test with their own images or only the bundled demo images? | Determines how robust preprocessing needs to be. | Build to handle arbitrary PNG/JPEG uploads; pre-validate with 10 demo images. |
| 3 | Is DICOM (.dcm) support P0 or can we defer to P1? | DICOM parsing adds ~2 hours of dev time (pydicom, metadata extraction, windowing). | Make it P1 — PNG/JPEG is P0, DICOM is implemented if time permits. |
| 4 | LLM for report generation — use local model or API call? | Local (Ollama) adds Docker complexity + RAM requirements. API (Anthropic/OpenAI) requires a key and has latency. | Use Jinja2 template as P0 (zero dependencies). Add LLM enhancement as P2 if API key is available. |
| 5 | Should the system support multi-label classification (multiple findings per scan)? | Multi-label is more clinically realistic but harder to display clearly. | Yes — use sigmoid output with per-class thresholds. Show top finding prominently, all findings in expandable list. |
| 6 | Is the History feature (past scans) P0 or P2? | Requires database persistence and UI sidebar. | P2 — nice for demo polish but not core to the AI pipeline. |
