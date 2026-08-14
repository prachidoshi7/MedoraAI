# MedoraAI UX, Doctor Administration, Report, and Pharmacy Implementation

## Goal

Improve dashboard readability and make doctor selection, doctor administration, report editing, medicine selection, and pharmacy stock management operational without removing existing patient, doctor, lab, prescription, billing, or report workflows.

## Requested outcomes and acceptance checklist

### 1. Dashboard readability and orientation

- [x] Increase small interface text to a consistently readable size across authenticated dashboards.
- [x] Add a clear page/workspace label such as **Doctor dashboard**, **Patient dashboard**, **Lab dashboard**, or **Pharmacy dashboard** in the application frame.
- [x] Preserve all existing navigation and dashboard content.
- [x] Keep the layout usable at desktop and responsive breakpoints.

### 2. Doctor identity shown to patients

- [x] Add a `qualification`/degree field (for example, MBBS, MD, BS Med) to doctor records.
- [x] Continue to store and show the doctor's specialization.
- [x] Display doctor name, qualification, specialization, department, and availability during appointment selection.
- [x] Show temporarily unavailable doctors to patients with a clear status, but prevent selecting them for a new appointment.
- [x] Revalidate availability on the server when an appointment is submitted.

### 3. Doctor administration panel

- [x] Add an admin-only Doctors panel.
- [x] Allow an admin to create a doctor login with name, username, initial password, qualification, specialization, department, email, and phone.
- [x] Allow an admin to edit doctor profile details.
- [x] Allow an admin to mark a doctor temporarily unavailable/available and provide an optional patient-facing note.
- [x] Allow an admin to deactivate (“delete”) and restore a doctor safely without destroying linked clinical records.
- [x] Enforce every doctor-management permission on the API, not only in the UI.

### 4. Doctor edit boundaries in reports

- [x] Keep generated clinical report sections visible but read-only.
- [x] Make only **Doctor clinical assessment / sign-off note** editable by doctors/admins.
- [x] Prevent report-field overrides in the PDF endpoint and doctor review API.
- [x] Keep approve/release and PDF download workflows.
- [x] Remove the **Comparison** section from report UI, report editing contracts, and generated PDF output.

### 5. Medicine catalog dropdown

- [x] Add a centrally seeded medicine catalog with a broad set of common medicine names, strengths, and forms.
- [x] Add an authenticated catalog API.
- [x] Replace free-text prescription medicine-name entry with a catalog dropdown.
- [x] Store the selected catalog medicine ID and its display-name snapshot in the prescription.
- [x] Retain dosage, frequency, duration, diagnosis, instructions, and multi-line prescription support.
- [x] Validate catalog selections on the server while retaining compatibility with older prescription records.

### 6. Pharmacy store management

- [x] Add a pharmacy/admin-only Store management page.
- [x] Provide a medicine dropdown and a three-column stock intake row:
  1. **New stock** — editable positive quantity.
  2. **Current available** — grey/read-only.
  3. **Total after add** — automatically calculated, grey/read-only.
- [x] Add the new quantity to current stock on confirmation (for example, 300 + 230 = 530).
- [x] Show current inventory in a readable stock table with low/out-of-stock states.
- [x] Record stock movements for traceability.
- [x] Enforce store-management permissions on the API.

### 7. Billing and automatic inventory updates

- [x] Show current availability while pharmacy staff prepares a bill.
- [x] Prevent billing more units than are available.
- [x] Deduct billed quantities automatically when the bill is generated.
- [x] Perform bill creation and stock deduction in one database transaction.
- [x] Keep the existing itemized invoice, patient bill visibility, tax calculation, and dispense status.
- [x] Make repeat bill requests idempotently fail without double-deducting stock.

### 8. Database compatibility and verification

- [x] Add backward-compatible SQLite migrations for doctor fields and new pharmacy tables.
- [x] Seed qualifications for demo doctors and seed a pharmacy/admin demo identity where needed.
- [x] Add/update backend tests for doctor administration, availability booking rules, inventory restocking, insufficient stock, and automatic billing deductions.
- [x] Run backend focused tests.
- [x] Run frontend typecheck/production build.
- [x] Reconcile every checkbox above with the implemented result.

## Data model design

- `users.qualification`: patient-facing medical degree/credential.
- `users.is_available`: temporary booking availability independent of account activity.
- `users.availability_note`: optional explanation such as “Available from Monday”.
- `medicine_catalog`: canonical selectable medicines (`id`, display name, category, active state).
- `pharmacy_inventory`: one quantity per pharmacy and catalog medicine.
- `pharmacy_stock_movements`: append-only restock/sale audit entries linked to a bill when applicable.
- Prescription medication JSON adds `medicine_id` while keeping the name snapshot for historical accuracy.

## API design

- `GET /api/v1/medicines` — authenticated active medicine catalog.
- `GET /api/v1/admin/doctors` — all doctors, including inactive doctors (admin only).
- `POST /api/v1/admin/doctors` — create doctor (admin only).
- `PATCH /api/v1/admin/doctors/{id}` — profile, availability, and active-state update (admin only).
- `DELETE /api/v1/admin/doctors/{id}` — safe deactivation (admin only).
- `GET /api/v1/pharmacy/inventory` — current inventory (pharmacy/admin only).
- `POST /api/v1/pharmacy/inventory/restock` — add stock and return the new total (pharmacy/admin only).
- Existing bill creation endpoint validates and deducts inventory transactionally.

## Permission summary

| Capability | Patient | Doctor | Lab | Pharmacy | Admin |
| --- | --- | --- | --- | --- | --- |
| View bookable doctor directory | Yes | Yes | Yes | Yes | Yes |
| Manage doctors | No | No | No | No | Yes |
| Edit generated report sections | No | No | No | No | No |
| Add doctor assessment and approve report | No | Assigned doctor | No | No | Yes |
| Select medicines for prescription | No | Assigned doctor | No | No | Admin-as-doctor workflow |
| Manage pharmacy stock | No | No | No | Yes | Yes |
| Generate medicine bill | No | No | No | Yes | Yes |

## Implementation order

1. Add data models, compatibility migrations, seed data, schemas, and serialization.
2. Add medicine catalog and doctor administration APIs.
3. Add pharmacy inventory APIs and transactional billing deduction.
4. Add frontend types/client calls and admin/store routes.
5. Update appointment selection, prescription dropdown, dashboards, and report restrictions.
6. Improve authenticated dashboard typography and workspace labels.
7. Add tests, run verification, and mark this checklist complete.

## Verification completed

- Backend: `python -m pytest backend/tests -q` — **36 passed, 6 subtests passed**.
- Frontend lint: `npm run lint` — **passed**.
- Frontend production build: `npm run build` — **passed**.
- Legacy SQLite migration smoke test — **passed** for doctor columns and pharmacy inventory tables.
- Environment note: the installed Node.js is 20.17.0; Vite recommends 20.19+ or 22.12+, although the production build completes successfully.
