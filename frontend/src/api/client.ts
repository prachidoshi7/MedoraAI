/**
 * MedoraAI — API Client
 * Axios-based HTTP client with JWT auth.
 */

import axios from 'axios';
import type {
  LoginRequest, LoginResponse, UploadResponse, AnalysisResponse,
  ReportResponse, HistoryResponse, DeleteScansResponse,
  ScanType, PatientSummaryResponse, RegisterRequest, UserSummary, Department,
  Doctor, Appointment, AppointmentStatus, DiagnosticOrder, Prescription,
  Medication, CaseStudy, PharmacyBill, PharmacyQueueItem, Medicine,
  PharmacyInventoryItem, PharmacyRestockResult, PharmacyCsvImportResult,
  DoctorCreateInput, DoctorUpdateInput, ProfileUpdateInput
} from '../types';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

const api = axios.create({
  baseURL: `${API_ORIGIN}/api/v1`,
  timeout: 60000,
});

export function apiAssetUrl(path: string): string {
  if (!path || /^(https?:|blob:|data:)/i.test(path) || !API_ORIGIN) return path;
  return `${API_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`;
}

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    localStorage.setItem('medoraai_token', token);
  } else {
    delete api.defaults.headers.common['Authorization'];
    localStorage.removeItem('medoraai_token');
  }
}

// Restore token from localStorage on load
const savedToken = localStorage.getItem('medoraai_token');
if (savedToken) {
  setAuthToken(savedToken);
}

// ---- Auth ----
export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>('/auth/login', data);
  setAuthToken(res.data.access_token);
  return res.data;
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>('/auth/register', data);
  setAuthToken(res.data.access_token);
  return res.data;
}

export async function getMe(): Promise<UserSummary> {
  return (await api.get<UserSummary>('/auth/me')).data;
}

export async function updateMe(data: ProfileUpdateInput): Promise<UserSummary> {
  return (await api.patch<UserSummary>('/auth/me', data)).data;
}

export async function uploadProfileAvatar(file: File): Promise<UserSummary> {
  const formData = new FormData();
  formData.append('file', file);
  return (await api.post<UserSummary>('/auth/me/avatar', formData, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
}

export function logout() {
  setAuthToken(null);
}

// ---- Scan ----
export async function uploadScan(file: File, scanType: ScanType, diagnosticOrderId?: number): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('scan_type', scanType);
  if (diagnosticOrderId) formData.append('diagnostic_order_id', String(diagnosticOrderId));

  const res = await api.post<UploadResponse>('/scan/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 25000,
  });
  return res.data;
}


// ---- Hospital Directory ----
export async function getDepartments(): Promise<Department[]> {
  return (await api.get<Department[]>('/departments')).data;
}

export async function getDoctors(departmentId?: number): Promise<Doctor[]> {
  return (await api.get<Doctor[]>('/doctors', { params: { department_id: departmentId } })).data;
}

export async function getMedicines(): Promise<Medicine[]> {
  return (await api.get<Medicine[]>('/medicines')).data;
}

export async function getAdminDoctors(): Promise<Doctor[]> {
  return (await api.get<Doctor[]>('/admin/doctors')).data;
}

export async function createDoctor(data: DoctorCreateInput): Promise<Doctor> {
  return (await api.post<Doctor>('/admin/doctors', data)).data;
}

export async function updateDoctor(id: number, data: DoctorUpdateInput): Promise<Doctor> {
  return (await api.patch<Doctor>(`/admin/doctors/${id}`, data)).data;
}

export async function deleteDoctor(id: number): Promise<Doctor> {
  return (await api.delete<Doctor>(`/admin/doctors/${id}`)).data;
}

// ---- Appointments ----
export async function getMyAppointments(): Promise<Appointment[]> {
  return (await api.get<Appointment[]>('/appointments/my')).data;
}

export async function getAppointment(id: number): Promise<Appointment> {
  return (await api.get<Appointment>(`/appointments/${id}`)).data;
}

export async function bookAppointment(data: {
  doctor_id: number; department_id?: number; reason: string; scheduled_at: string;
}): Promise<Appointment> {
  return (await api.post<Appointment>('/appointments/book', data)).data;
}

export async function updateAppointmentStatus(id: number, status: AppointmentStatus): Promise<Appointment> {
  return (await api.patch<Appointment>(`/appointments/${id}/status`, { status })).data;
}

export async function updateAppointmentNotes(id: number, notes: string): Promise<Appointment> {
  return (await api.post<Appointment>(`/appointments/${id}/notes`, { notes })).data;
}

// ---- Diagnostics ----
export async function getMyDiagnosticOrders(): Promise<DiagnosticOrder[]> {
  return (await api.get<DiagnosticOrder[]>('/diagnostic/my')).data;
}

export async function getPendingDiagnosticOrders(): Promise<DiagnosticOrder[]> {
  return (await api.get<DiagnosticOrder[]>('/diagnostic/pending')).data;
}

export async function createDiagnosticOrder(data: {
  appointment_id: number; scan_type: ScanType; priority: string; clinical_notes: string;
}): Promise<DiagnosticOrder> {
  return (await api.post<DiagnosticOrder>('/diagnostic/order', data)).data;
}

export async function claimDiagnosticOrder(id: number): Promise<DiagnosticOrder> {
  return (await api.patch<DiagnosticOrder>(`/diagnostic/${id}/assign`)).data;
}

// ---- Prescriptions ----
export async function getMyPrescriptions(): Promise<Prescription[]> {
  return (await api.get<Prescription[]>('/prescriptions/mine')).data;
}

export async function createPrescription(data: {
  appointment_id: number; scan_id?: string; medications: Medication[];
  instructions: string; diagnosis: string;
}): Promise<Prescription> {
  return (await api.post<Prescription>('/prescriptions', data)).data;
}

// ---- Pharmacy ----
export async function getPharmacyQueue(): Promise<PharmacyQueueItem[]> {
  return (await api.get<PharmacyQueueItem[]>('/pharmacy/queue')).data;
}

export async function getPharmacyInventory(): Promise<PharmacyInventoryItem[]> {
  return (await api.get<PharmacyInventoryItem[]>('/pharmacy/inventory')).data;
}

export async function restockPharmacyInventory(medicineId: number, newQuantity: number, expiryDate?: string): Promise<PharmacyRestockResult> {
  return (await api.post<PharmacyRestockResult>('/pharmacy/inventory/restock', {
    medicine_id: medicineId,
    new_quantity: newQuantity,
    expiry_date: expiryDate || null,
  })).data;
}

export async function uploadPharmacyInventoryCsv(file: File): Promise<PharmacyCsvImportResult> {
  const formData = new FormData();
  formData.append('file', file);
  return (await api.post<PharmacyCsvImportResult>('/pharmacy/inventory/import-csv', formData)).data;
}

export async function getMyPharmacyBills(): Promise<PharmacyBill[]> {
  return (await api.get<PharmacyBill[]>('/pharmacy/bills/mine')).data;
}

export async function createPharmacyBill(data: {
  prescription_id: number;
  items: Array<{ medication_index: number; quantity: number; unit_price: number }>;
  tax_percent: number;
  notes: string;
}): Promise<PharmacyBill> {
  return (await api.post<PharmacyBill>('/pharmacy/bills', data)).data;
}

export async function getPharmacyBill(id: number): Promise<PharmacyBill> {
  return (await api.get<PharmacyBill>(`/pharmacy/bills/${id}`)).data;
}

export async function markPharmacyBillDispensed(id: number): Promise<PharmacyBill> {
  return (await api.patch<PharmacyBill>(`/pharmacy/bills/${id}/dispense`)).data;
}

// ---- Case studies ----
export async function getMyCaseStudies(): Promise<CaseStudy[]> {
  return (await api.get<CaseStudy[]>('/case-study/mine')).data;
}

export async function getCaseStudy(id: number): Promise<CaseStudy> {
  return (await api.get<CaseStudy>(`/case-study/${id}`)).data;
}

export async function generateCaseStudy(data: {
  appointment_id: number; clinical_history?: string; diagnosis?: string;
  treatment_plan?: string; follow_up_plan?: string;
}): Promise<CaseStudy> {
  return (await api.post<CaseStudy>('/case-study/generate', data)).data;
}

export async function finalizeCaseStudy(id: number): Promise<CaseStudy> {
  return (await api.post<CaseStudy>(`/case-study/${id}/finalize`)).data;
}

export async function downloadCaseStudyPdf(id: number): Promise<Blob> {
  return (await api.get(`/case-study/${id}/pdf`, { responseType: 'blob' })).data;
}

export async function analyzeScan(scanId: string): Promise<AnalysisResponse> {
  const res = await api.post<AnalysisResponse>(`/scan/analyze/${scanId}`, undefined, {
    timeout: 180000,
  });
  return res.data;
}

// ---- Report ----
export async function getReport(scanId: string): Promise<ReportResponse> {
  const res = await api.get<ReportResponse>(`/report/${scanId}`);
  return res.data;
}

export async function regenerateReport(scanId: string): Promise<ReportResponse> {
  const res = await api.post<ReportResponse>(`/report/${scanId}/regenerate`, undefined, {
    timeout: 180000,
  });
  return res.data;
}

export async function reviewReport(scanId: string, data: {
  doctor_notes?: string; approve?: boolean;
}): Promise<ReportResponse> {
  return (await api.post<ReportResponse>(`/report/${scanId}/doctor-review`, data)).data;
}

export async function downloadPdf(
  scanId: string,
): Promise<Blob> {
  const res = await api.post(`/report/${scanId}/pdf`, {}, {
    responseType: 'blob',
  });
  return res.data;
}

export function triggerPdfDownload(blob: Blob, scanId: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `MedoraAI_Report_${scanId.slice(0, 8)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// ---- Patient Summary ----
export async function getPatientSummary(
  scanId: string,
  language: string,
): Promise<PatientSummaryResponse> {
  const res = await api.post<PatientSummaryResponse>(
    `/report/${scanId}/patient-summary`,
    { language },
    { timeout: 60000 },
  );
  return res.data;
}

// ---- History ----
export async function getHistory(): Promise<HistoryResponse> {
  const res = await api.get<HistoryResponse>('/history');
  return res.data;
}

export async function deleteSelectedScans(scanIds: string[]): Promise<DeleteScansResponse> {
  const res = await api.post<DeleteScansResponse>('/history/delete', {
    scan_ids: scanIds,
  });
  return res.data;
}

export async function deleteHistoryScan(scanId: string): Promise<DeleteScansResponse> {
  const res = await api.delete<DeleteScansResponse>(`/history/${scanId}`);
  return res.data;
}

export async function clearHistory(): Promise<DeleteScansResponse> {
  const res = await api.delete<DeleteScansResponse>('/history');
  return res.data;
}

// ---- Interceptors: handle 401 ----
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setAuthToken(null);
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;
