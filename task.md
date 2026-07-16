# Task Checklist — MedoraAI Editorial Redesign

## Backend — Patient Report
- [ ] Add `generate_patient_report()` to `llm_report_engine.py`
- [ ] Add patient summary endpoint to report router
- [ ] Remove LLM provider exposure from API responses

## Frontend — Design System
- [ ] Update `index.html` — Google Fonts (Bodoni Moda + Inter), meta tags
- [ ] Rewrite `globals.css` — warm editorial design tokens, layout, animations

## Frontend — Core
- [ ] Rewrite `App.tsx` — editorial navbar, remove dark theme toggle
- [ ] Update `types/index.ts` — patient summary types, language list
- [ ] Update `api/client.ts` — patient summary API function
- [ ] Remove ThemeProvider/useTheme (single light theme)

## Frontend — Pages
- [ ] Rewrite `LoginPage.tsx` — warm editorial doctor portal
- [ ] Rewrite `UploadPage.tsx` — clean upload with editorial styling
- [ ] Rewrite `ResultsPage.tsx` — doctor/patient tab layout

## Frontend — Components
- [ ] Rewrite `ResultPanel.tsx` — warm styling, remove LLM provider display
- [ ] Rewrite `ReportEditor.tsx` — better clinical report layout
- [ ] Rewrite `ScanViewer.tsx` — warm theme viewer
- [ ] Rewrite `HistorySidebar.tsx` — editorial history cards
- [ ] Create `PatientReport.tsx` — language selector + simplified report
- [ ] Rewrite `LoadingSpinner.tsx` — warm themed spinner

## Verification
- [ ] Visual check — warm editorial aesthetic
- [ ] Brain MRI flow — upload → results → patient report
- [ ] No Gemini/LLM branding visible in UI
