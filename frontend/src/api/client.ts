/**
 * MedoraAI — API Client
 * Axios-based HTTP client with JWT auth.
 */

import axios from 'axios';
import type {
  LoginRequest, LoginResponse, UploadResponse, AnalysisResponse,
  ReportResponse, PDFRequest, HistoryResponse, DeleteScansResponse,
  ScanType, PatientSummaryResponse
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
});

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

export function logout() {
  setAuthToken(null);
}

// ---- Scan ----
export async function uploadScan(file: File, scanType: ScanType): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('scan_type', scanType);

  const res = await api.post<UploadResponse>('/scan/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 25000,
  });
  return res.data;
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

export async function downloadPdf(
  scanId: string,
  edits?: PDFRequest,
): Promise<Blob> {
  const res = await api.post(`/report/${scanId}/pdf`, edits || {}, {
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
