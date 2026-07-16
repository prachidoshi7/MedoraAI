# MedoraAI Dashboard Redesign — Doctor-Focused Editorial UI + Patient Reports

## Background

Complete redesign of MedoraAI's frontend from the current dark glassmorphic theme to a premium **warm editorial aesthetic** (off-white/bone background, terracotta red accents, Bodoni + Helvetica Neue typography). The dashboard is purpose-built for **radiologists and doctors** to quickly upload scans, get AI-assisted reports, and share simplified patient-friendly summaries.

### New Features
1. **Editorial warm-tone design** matching the design spec (bone `#E6E2DA` bg, rust `#A6412B` accent, Bodoni serif + clean sans-serif)
2. **Patient-friendly report** — simplified, non-technical summary in the patient's chosen language (powered by Gemini but never mentioned)
3. **Remove all LLM/API branding** — no "Gemini", "Groq", "GPT" references anywhere in the frontend
4. **Improved clinical report layout** — cleaner, more professional for doctors

## User Review Required

> [!IMPORTANT]
> **Design Direction**: The editorial warm-tone design (bone + terracotta + serif typography) is a dramatic departure from the current dark glassmorphic UI. This will be a complete visual overhaul. The design spec you shared is fashion/luxury-oriented — I'll adapt it for a medical context while keeping the warmth, typography, and editorial feel.

> [!IMPORTANT]
> **Patient Languages**: For the patient-friendly report, I'll add a language dropdown. Which languages do you want supported? I'll start with: **English, Hindi, Tamil, Telugu, Marathi, Bengali, Kannada, Gujarati, Malayalam, Punjabi, Urdu**. The Gemini API will translate.

> [!WARNING]  
> **Complete Frontend Rewrite**: Every CSS file and component will be rewritten. The existing dark theme will be replaced entirely.

## Open Questions

> [!IMPORTANT]
> 1. **Patient report languages** — Should I include any additional languages beyond the major Indian languages + English?
> 2. **Doctor login** — Should the login page also get the new design, or just the dashboard?
> 3. **History sidebar** — Keep it, or replace with a separate history page?

---

## Proposed Changes

### Backend — Patient Report Endpoint

#### [MODIFY] [llm_report_engine.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/services/llm_report_engine.py)
- Add `generate_patient_report()` method that sends a separate Gemini prompt:
  - "Explain this medical finding to a patient in simple, non-technical language in {language}"
  - Returns plain-language summary (no medical jargon)
  - Never mentions AI model names, confidence scores, or technical details
- Remove any LLM provider name exposure in the report response (keep internally for logging)

#### [MODIFY] [scan.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/routers/scan.py) or [NEW] patient report endpoint
- Add `POST /api/v1/report/{scan_id}/patient-summary` endpoint
  - Takes `language` parameter (e.g., "hindi", "english", "tamil")
  - Calls Gemini to generate patient-friendly explanation
  - Returns simple text summary

#### [MODIFY] [report.py](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/backend/routers/report.py)
- Add the patient summary endpoint here

---

### Frontend — Complete Design System Rewrite

#### [MODIFY] [globals.css](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/styles/globals.css)
Complete rewrite with new design tokens:
```css
:root {
  --color-bg: #E6E2DA;           /* warm bone */
  --color-bg-card: #F2EEEA;      /* slightly lighter card bg */
  --color-accent: #A6412B;       /* terracotta rust */
  --color-accent-hover: #8B3522;
  --color-text: #2C2C2C;
  --color-text-muted: #7A7268;
  --color-border: #D4CFC7;
  --color-border-dark: #1A1A1A;
  --font-display: 'Bodoni Moda', 'Didot', serif;
  --font-body: 'Inter', 'Helvetica Neue', sans-serif;
}
```
- Thin black border frame (top + bottom of viewport)
- Generous whitespace, editorial negative space
- Subtle hover transitions
- Print-friendly report sections

---

### Frontend — Components (Complete Rewrite)

#### [MODIFY] [App.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/App.tsx)
- Redesigned navbar: warm tones, serif logo, minimal editorial nav
- Remove theme toggle (single warm light theme)
- Clean doctor-focused navigation

#### [MODIFY] [LoginPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/LoginPage.tsx)
- Warm editorial login with Bodoni wordmark
- Terracotta accent buttons
- "Doctor's Portal" framing

#### [MODIFY] [UploadPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/UploadPage.tsx)
- Clean upload zone with warm styling
- Scan type selection with editorial cards
- Remove any mention of model names in user-facing text (keep internally)

#### [MODIFY] [ResultsPage.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/pages/ResultsPage.tsx)
- Two-tab layout: **Doctor Report** | **Patient Summary**
- Doctor tab: clinical findings, Grad-CAM heatmap, classification scores
- Patient tab: language selector dropdown + simple explanation
- Remove "llm_provider" display from UI

#### [MODIFY] [ResultPanel.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ResultPanel.tsx)
- Warm editorial styling
- Remove "Report By" section that shows "Google Gemini Vision" / "Groq" etc.
- Keep model name (EfficientNetB3 / EfficientNet-B4) but as small metadata, not prominently

#### [MODIFY] [ReportEditor.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ReportEditor.tsx)
- Better formatted clinical report
- Warm theme styling
- Remove LLM provider mentions

#### [MODIFY] [ScanViewer.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/ScanViewer.tsx)
- Warm-themed scan/heatmap viewer
- Clean overlay toggle

#### [MODIFY] [HistorySidebar.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/HistorySidebar.tsx)
- Warm editorial history cards

#### [NEW] PatientReport.tsx
- Language selector dropdown (English, Hindi, Tamil, etc.)
- "Generate Patient Summary" button
- Displays simplified report in chosen language
- Copy/print/share options

#### [MODIFY] [LoadingSpinner.tsx](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/components/LoadingSpinner.tsx)
- Warm-themed loading animation

---

### Frontend — Types & API

#### [MODIFY] [index.ts](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/types/index.ts)
- Add `PatientSummaryResponse` type
- Add language options list
- Remove `llm_provider` from user-facing types (keep in internal types)

#### [MODIFY] [client.ts](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/src/api/client.ts)
- Add `getPatientSummary(scanId, language)` API function

#### [MODIFY] [index.html](file:///c:/Users/gamin/Desktop/INTELLFIY/WINNING_IT/MedoraAI/frontend/index.html)
- Update Google Fonts link to include Bodoni Moda + Inter
- Update title/meta

---

### Frontend — Remove LLM Branding

Files that currently expose "Gemini", "Groq", "Claude", "OpenAI":
- `ResultPanel.tsx` — "Report By: Google Gemini Vision" → Remove entire section
- `ReportEditor.tsx` — Check for any LLM mentions
- `types/index.ts` — `llm_provider` field still exists internally but hidden from UI

---

## Verification Plan

### Manual Verification
1. Start backend + frontend, login as doctor
2. Upload brain MRI → verify warm-themed results with clean clinical report
3. Switch to Patient Summary tab → select Hindi → verify simplified report generates
4. Verify NO mention of "Gemini", "Groq", "API", "LLM" anywhere in the UI
5. Upload chest X-ray → verify full flow works
6. Check responsive design on different screen sizes

### Visual Checks
- Warm bone background with terracotta accents throughout
- Bodoni serif headings, Inter body text
- Thin black frame border at top/bottom
- Editorial negative space
- Professional doctor-focused dashboard feel
