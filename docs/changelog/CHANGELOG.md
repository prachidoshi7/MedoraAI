# Changelog

All notable project changes should be recorded here.

## 2026-07-10

- Imported trained chest X-ray EfficientNet-B4 model export into `models/`.
- Added `chest_xray_efficientnet_b4.labels.json` with the backend-compatible 15-label order.
- Verified backend loads both chest X-ray and brain MRI models.
- Updated local setup, model, frontend, backend, and notebook documentation with current run commands.
- Updated `.env.example` to use the current model artifact paths.
- Added chest evaluation tooling and stricter report/heatmap safeguards for low-confidence predictions.
- Added Gemini image-aware reporting support with uploaded-image context and ML context.

## 2026-07-08

- Organized documentation into planning, guides, changelog, team, and references folders.
- Moved project abstract, PRD, and TDD into `planning/`.
