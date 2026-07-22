/**
 * MedoraAI — Scan Hooks
 * Upload + Analyze workflow hooks with step-based progress tracking.
 */

import { useState, useCallback } from 'react';
import { uploadScan, analyzeScan } from '../api/client';
import type { ScanType, UploadResponse, AnalysisResponse } from '../types';

export type AnalysisStep =
  | 'idle'
  | 'uploading'
  | 'classifying'
  | 'generating_heatmap'
  | 'generating_report'
  | 'complete'
  | 'error';

const STEP_LABELS: Record<AnalysisStep, string> = {
  idle: '',
  uploading: 'Securely uploading the study',
  classifying: 'Reviewing image patterns',
  generating_heatmap: 'Generating the Grad-CAM heatmap',
  generating_report: 'Preparing the clinical draft',
  complete: 'Study ready for review',
  error: 'Study processing failed',
};

export function useScanAnalysis() {
  const [step, setStep] = useState<AnalysisStep>('idle');
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stepLabel = STEP_LABELS[step];

  const analyze = useCallback(async (file: File, scanType: ScanType) => {
    setStep('uploading');
    setError(null);
    setUploadResult(null);
    setAnalysisResult(null);

    let heatmapTimer: ReturnType<typeof window.setTimeout> | undefined;
    let reportTimer: ReturnType<typeof window.setTimeout> | undefined;

    try {
      // Step 1: Upload
      const upload = await uploadScan(file, scanType);
      setUploadResult(upload);
      setStep('classifying');

      // Steps 2-4: Analyze (classification + heatmap + report all happen server-side)
      // We simulate granular steps with timing
      heatmapTimer = window.setTimeout(() => setStep('generating_heatmap'), 1500);
      reportTimer = window.setTimeout(() => setStep('generating_report'), 3000);

      const analysis = await analyzeScan(upload.scan_id);

      setAnalysisResult(analysis);
      setStep('complete');

      // Store in sessionStorage for ResultsPage to read after navigation
      sessionStorage.setItem(`analysis_${upload.scan_id}`, JSON.stringify(analysis));

      return analysis;
    } catch (err: any) {
      setStep('error');
      const timedOut = err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT';
      const message = err.response?.data?.detail || (timedOut
        ? 'Image verification took too long. No analysis was performed. Upload one original diagnostic image and try again.'
        : 'Analysis failed. Please try again.');
      setError(message);
      throw new Error(message);
    } finally {
      if (heatmapTimer !== undefined) window.clearTimeout(heatmapTimer);
      if (reportTimer !== undefined) window.clearTimeout(reportTimer);
    }
  }, []);

  const reset = useCallback(() => {
    setStep('idle');
    setUploadResult(null);
    setAnalysisResult(null);
    setError(null);
  }, []);

  return {
    step,
    stepLabel,
    uploadResult,
    analysisResult,
    error,
    analyze,
    reset,
    isLoading: step !== 'idle' && step !== 'complete' && step !== 'error',
  };
}
