import { useEffect, useMemo, useState } from 'react';
import { downloadPdf, regenerateReport, triggerPdfDownload } from '../api/client';
import type { PDFRequest, ReportData } from '../types';

interface ReportEditorProps {
  scanId: string;
  report: ReportData;
  onReportChange?: (report: ReportData) => void;
}

type DraftKey =
  | 'clinical_history'
  | 'technique'
  | 'comparison'
  | 'image_quality'
  | 'findings'
  | 'impression'
  | 'differential_diagnosis'
  | 'recommendations'
  | 'critical_communication';

type ReportDraft = Record<DraftKey, string>;

const reportSections: Array<{
  key: DraftKey;
  title: string;
  compact?: boolean;
  prominent?: boolean;
}> = [
  { key: 'clinical_history', title: 'Clinical information', compact: true },
  { key: 'technique', title: 'Technique' },
  { key: 'comparison', title: 'Comparison', compact: true },
  { key: 'image_quality', title: 'Study quality and limitations' },
  { key: 'findings', title: 'Findings' },
  { key: 'impression', title: 'Impression', prominent: true },
  { key: 'differential_diagnosis', title: 'Differential considerations', compact: true },
  { key: 'recommendations', title: 'Recommendations' },
  { key: 'critical_communication', title: 'Communication', compact: true },
];

const makeDraft = (report: ReportData): ReportDraft => ({
  clinical_history: report.clinical_history || 'Not provided.',
  technique: report.technique || '',
  comparison: report.comparison || 'No prior imaging was supplied for comparison.',
  image_quality: report.image_quality || '',
  findings: report.findings || '',
  impression: report.impression || '',
  differential_diagnosis: report.differential_diagnosis || 'None based on the supplied image.',
  recommendations: report.recommendations || '',
  critical_communication: report.critical_communication || 'No critical communication generated.',
});

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en', { day: '2-digit', month: 'long', year: 'numeric' }).format(date);
};

export default function ReportEditor({ scanId, report, onReportChange }: ReportEditorProps) {
  const original = useMemo(() => makeDraft(report), [report]);
  const [draft, setDraft] = useState<ReportDraft>(original);
  const [downloading, setDownloading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => setDraft(original), [original]);

  const edited = (Object.keys(original) as DraftKey[]).some((key) => draft[key] !== original[key]);

  const change = (key: DraftKey, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const regenerate = async () => {
    setRegenerating(true);
    setError('');
    try {
      const result = await regenerateReport(scanId);
      onReportChange?.(result.report);
    } catch {
      setError('The report could not be regenerated. Confirm the clinical text service is configured and try again.');
    } finally {
      setRegenerating(false);
    }
  };

  const download = async () => {
    setDownloading(true);
    setError('');
    const edits: PDFRequest = {
      edited_clinical_history: draft.clinical_history,
      edited_technique: draft.technique,
      edited_comparison: draft.comparison,
      edited_image_quality: draft.image_quality,
      edited_findings: draft.findings,
      edited_impression: draft.impression,
      edited_differential_diagnosis: draft.differential_diagnosis,
      edited_recommendations: draft.recommendations,
      edited_critical_communication: draft.critical_communication,
    };
    try {
      const blob = await downloadPdf(scanId, edits);
      triggerPdfDownload(blob, scanId);
    } catch {
      setError('The PDF could not be prepared. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section className="report-editor">
      <header className="report-editor__header">
        <div>
          <p className="eyebrow">Radiology report</p>
          <h2>Preliminary imaging interpretation</h2>
          <p>Review and edit this draft against the source examination before signing.</p>
        </div>
        <div className="report-header-actions">
          {edited && <button className="text-button" onClick={() => setDraft(original)}>Discard edits</button>}
          <button className="button button--secondary" onClick={() => void regenerate()} disabled={regenerating || downloading}>
            {regenerating ? 'Regenerating…' : 'Regenerate report'}
          </button>
        </div>
      </header>

      <dl className="report-demographics">
        <div><dt>Patient ID</dt><dd>{report.patient_id}</dd></div>
        <div><dt>Study date</dt><dd>{formatDate(report.scan_date)}</dd></div>
        <div><dt>Modality</dt><dd>{report.modality}</dd></div>
        <div><dt>Examination</dt><dd>{report.scan_type === 'brain_mri' ? 'Limited brain MRI image' : 'Chest radiograph'}</dd></div>
      </dl>

      <div className="report-document">
        {reportSections.map((section) => (
          <label
            className={`report-field${section.prominent ? ' report-field--prominent' : ''}`}
            key={section.key}
          >
            <span className="report-field__label">
              <strong>{section.title}</strong>
            </span>
            <textarea
              className={section.compact ? 'report-textarea--compact' : ''}
              value={draft[section.key]}
              onChange={(event) => change(section.key, event.target.value)}
              aria-label={section.title}
            />
          </label>
        ))}
      </div>

      <details className="report-provenance">
        <summary>Method and known limitations</summary>
        <div>
          <p><strong>Method</strong>{report.methodology || 'Automated image classification with Grad-CAM heatmap explainability.'}</p>
          <p><strong>Limitations</strong>{report.limitations || 'The output is limited by the supplied image and the trained finding categories.'}</p>
        </div>
      </details>

      <div className="clinical-notice">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5m0 3h.01M10 3.5 2.6 17a2 2 0 0 0 1.8 3h15.2a2.3 2.3 0 0 0-4 0Z" /></svg>
        <p>{report.disclaimer}</p>
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}
      <footer className="report-actions">
        <span>{edited ? 'Edited draft · changes will be included in the PDF' : 'Generated draft · verification required'}</span>
        <button className="button button--primary" onClick={() => void download()} disabled={downloading || regenerating}>
          <span>{downloading ? 'Preparing PDF…' : 'Download clinical PDF'}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0 4-4m-4 4-4-4M5 20h14" /></svg>
        </button>
      </footer>
    </section>
  );
}
