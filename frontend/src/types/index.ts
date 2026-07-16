/**
 * MedoraAI — Types & Configuration
 * Type definitions and scan configuration for the diagnostic platform.
 */

/* ── Auth ── */
export interface LoginRequest { username: string; password: string; }
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/* ── Scan Types ── */
export type ScanType = 'chest_xray' | 'brain_mri';

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
    model: 'EfficientNet-B4',
    description: 'Multi-label thoracic disease classification',
    classes: 'Atelectasis, Cardiomegaly, Effusion, Infiltration, Mass, Nodule, Pneumonia, Pneumothorax, Normal',
  },
  {
    id: 'brain_mri',
    label: 'Brain Tumor Detection',
    icon: '🧠',
    model: 'EfficientNetB3',
    description: '4-class tumor classification with visual explainability',
    classes: 'Glioma, Meningioma, No Tumor, Pituitary',
  },
];

/* ── Scan Upload ── */
export interface UploadResponse {
  scan_id: string;
  filename: string;
  scan_type: ScanType;
  status: string;
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
  findings: string;
  impression: string;
  recommendations: string;
  severity: string;
  disclaimer: string;
  generated_at: string;
  heatmap_target_label?: string;
}

export interface ReportResponse {
  scan_id: string;
  report: ReportData;
}

export interface PDFRequest {
  edited_findings?: string;
  edited_impression?: string;
  edited_recommendations?: string;
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
