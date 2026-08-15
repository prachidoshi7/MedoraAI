/**
 * MedoraAI — Types & Configuration
 * Type definitions and scan configuration for the diagnostic platform.
 */

/* ── Auth ── */
export interface LoginRequest { username: string; password: string; }
export type UserRole = 'patient' | 'doctor' | 'lab_tech' | 'pharmacy' | 'admin';
export interface UserSummary {
  id: number;
  username: string;
  role: UserRole;
  full_name: string;
  email: string;
  phone: string;
  avatar_url: string;
  specialization: string;
  qualification: string;
  department_id: number | null;
  department_name: string | null;
  is_active: boolean;
  is_available: boolean;
  availability_note: string;
}
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserSummary;
}
export interface RegisterRequest {
  username: string;
  password: string;
  full_name: string;
  email?: string;
  phone?: string;
}
export interface ProfileUpdateInput { full_name: string; email: string; phone: string; }

/* ── Scan Types ── */
export type ScanType = 'chest_xray' | 'brain_mri' | 'lung_ct' | 'kidney_us';

export interface ScanTypeConfig {
  id: ScanType;
  label: string;
  icon: string;
  model: string;
  description: string;
  classes: string;
}

export const SCAN_TYPES: ScanTypeConfig[] = [
  {
    id: 'chest_xray',
    label: 'Chest X-Ray',
    icon: '🫁',
    model: 'RAD-DINO · 3-class research head',
    description: 'Secondary experimental chest classification; MAIRA-2 drafts the primary image report',
    classes: 'Normal, Pneumonia, Tuberculosis',
  },
  {
    id: 'brain_mri',
    label: 'Brain Tumor Detection',
    icon: '🧠',
    model: 'EfficientNetB3',
    description: '4-class tumor classification with visual explainability',
    classes: 'Glioma, Meningioma, No Tumor, Pituitary',
  },
  {
    id: 'lung_ct',
    label: 'Lung CT',
    icon: '◌',
    model: '5-class CNN',
    description: 'Lung lesion and carcinoma category analysis',
    classes: 'Benign, Normal, Adenocarcinoma, Large Cell Carcinoma, Squamous Cell Carcinoma',
  },
  {
    id: 'kidney_us',
    label: 'Kidney Ultrasound',
    icon: '◇',
    model: 'Renal CNN',
    description: 'Renal stone screening with visual explainability',
    classes: 'Normal, Stone',
  },
];

/* ── Scan Upload ── */
export interface UploadResponse {
  scan_id: string;
  filename: string;
  scan_type: ScanType;
  status: string;
}

/* ── Hospital Workflow ── */
export interface Department {
  id: number;
  name: string;
  description: string;
  icon: string;
}

export interface Doctor extends UserSummary { department: Department | null; }
export interface DoctorCreateInput {
  username: string;
  password: string;
  full_name: string;
  qualification: string;
  specialization: string;
  department_id: number;
  email: string;
  phone: string;
}
export type DoctorUpdateInput = Partial<Omit<DoctorCreateInput, 'username' | 'password'>> & {
  is_available?: boolean;
  availability_note?: string;
  is_active?: boolean;
};
export type AppointmentStatus = 'requested' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled';
export interface Appointment {
  id: number;
  patient: UserSummary;
  doctor: UserSummary;
  department: Department | null;
  status: AppointmentStatus;
  reason: string;
  notes: string;
  scheduled_at: string | null;
  created_at: string | null;
  diagnostic_order_count: number;
}

export type DiagnosticStatus = 'ordered' | 'assigned' | 'in_progress' | 'completed' | 'reviewed';
export interface DiagnosticOrder {
  id: number;
  appointment_id: number;
  patient: UserSummary;
  ordering_doctor: UserSummary;
  assigned_lab_tech: UserSummary | null;
  scan_type: ScanType;
  organ: string;
  priority: 'routine' | 'urgent' | 'stat';
  status: DiagnosticStatus;
  clinical_notes: string;
  scan_id: string | null;
  created_at: string | null;
}

export interface Medication {
  medicine_id: number | null;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  suggested_quantity?: number | null;
  quantity_basis?: string;
}

export interface Prescription {
  id: number;
  appointment_id: number;
  doctor: UserSummary;
  patient: UserSummary;
  scan_id: string | null;
  medications: Medication[];
  instructions: string;
  diagnosis: string;
  created_at: string | null;
}

export interface PharmacyBillItem {
  medication_index: number;
  medicine_id: number | null;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface PharmacyBill {
  id: number;
  invoice_number: string;
  prescription: Prescription;
  patient: UserSummary;
  pharmacy: UserSummary;
  items: PharmacyBillItem[];
  subtotal: number;
  tax_percent: number;
  tax_amount: number;
  total: number;
  status: 'billed' | 'dispensed';
  notes: string;
  created_at: string | null;
  dispensed_at: string | null;
}

export interface PharmacyQueueItem {
  prescription: Prescription;
  bill: PharmacyBill | null;
}

export interface Medicine {
  id: number;
  name: string;
  category: string;
}

export interface PharmacyInventoryItem {
  id: number;
  medicine: Medicine;
  current_quantity: number;
  expiry_date: string | null;
  updated_at: string | null;
}

export interface PharmacyRestockResult {
  inventory: PharmacyInventoryItem;
  previous_quantity: number;
  added_quantity: number;
  total_quantity: number;
}

export interface PharmacyCsvImportRow {
  row_number: number;
  medicine: Medicine;
  previous_quantity: number;
  added_quantity: number;
  total_quantity: number;
  expiry_date: string;
}

export interface PharmacyCsvImportResult {
  rows_processed: number;
  medicines_updated: number;
  total_units_added: number;
  rows: PharmacyCsvImportRow[];
}

export interface CaseStudy {
  id: number;
  patient: UserSummary;
  appointment_id: number | null;
  chief_complaint: string;
  clinical_history: string;
  diagnostic_findings: string;
  scan_ids: string[];
  diagnosis: string;
  treatment_plan: string;
  prescriptions: Prescription[];
  follow_up_plan: string;
  doctor_notes: string;
  status: 'draft' | 'preliminary' | 'final';
  preliminary_at: string | null;
  finalized_at: string | null;
  created_at: string | null;
}

/* ── Classification ── */
export interface ClassificationDetail {
  top_label: string;
  confidence: number;
  severity: 'Normal' | 'Mild' | 'Moderate' | 'Severe';
  all_scores: Record<string, number>;
  is_low_confidence?: boolean;
  heatmap_target_label?: string;
}

/* ── Analysis ── */
export interface AnalysisResponse {
  scan_id: string;
  scan_type: ScanType;
  status: string;
  classification: ClassificationDetail;
  localization: {
    type: string;
    heatmap_url: string;
    bounding_boxes: Array<{
      x1: number; y1: number; x2: number; y2: number;
      label: string; confidence: number;
    }>;
  };
  analysis_time_ms: number;
  analyzed_at: string;
}

/* ── Report ── */
export interface ReportData {
  patient_id: string;
  scan_date: string;
  scan_type: string;
  modality: string;
  top_label: string;
  confidence: number;
  all_scores: Record<string, number>;
  clinical_history: string;
  technique: string;
  image_quality: string;
  findings: string;
  impression: string;
  differential_diagnosis: string;
  recommendations: string;
  critical_communication: string;
  severity: string;
  disclaimer: string;
  llm_provider?: string;
  generated_at: string;
  heatmap_target_label?: string;
  is_low_confidence?: boolean;
  methodology?: string;
  limitations?: string;
  doctor_assessment: string;
}

export interface ReportResponse {
  scan_id: string;
  report: ReportData;
}

/* ── Patient Summary ── */
export interface PatientSummaryResponse {
  scan_id: string;
  language: string;
  summary: string;
  supported_languages: string[];
}

export const PATIENT_LANGUAGES = [
  'English', 'Hindi', 'Tamil', 'Telugu', 'Marathi',
  'Bengali', 'Kannada', 'Gujarati', 'Malayalam', 'Punjabi', 'Urdu',
] as const;

/* ── History ── */
export interface HistoryScan {
  scan_id: string;
  filename: string;
  scan_type: ScanType;
  status: string;
  top_label: string;
  confidence: number;
  severity: string;
  uploaded_at: string;
  thumbnail_url: string;
}

export interface HistoryResponse {
  scans: HistoryScan[];
  total: number;
}

export interface DeleteScansResponse {
  deleted: number;
  scan_ids: string[];
}
