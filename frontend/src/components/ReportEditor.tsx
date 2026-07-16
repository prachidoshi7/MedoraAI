import { useEffect, useState } from 'react';
import { downloadPdf, triggerPdfDownload } from '../api/client';
import type { ReportData } from '../types';

interface ReportEditorProps {
  scanId: string;
  report: ReportData;
}

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en', { day: '2-digit', month: 'long', year: 'numeric' }).format(date);
};

export default function ReportEditor({ scanId, report }: ReportEditorProps) {
  const [findings, setFindings] = useState(report.findings);
  const [impression, setImpression] = useState(report.impression);
  const [recommendations, setRecommendations] = useState(report.recommendations);
  const [edited, setEdited] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setFindings(report.findings);
    setImpression(report.impression);
    setRecommendations(report.recommendations);
    setEdited(false);
  }, [report]);

  const change = (setter: (value: string) => void, value: string) => {
    setter(value);
    setEdited(true);
  };

  const reset = () => {
    setFindings(report.findings);
    setImpression(report.impression);
    setRecommendations(report.recommendations);
    setEdited(false);
  };

  const download = async () => {
    setDownloading(true);
    setError('');
    try {
      const blob = await downloadPdf(scanId, {
        edited_findings: findings,
        edited_impression: impression,
        edited_recommendations: recommendations,
      });
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
          <p className="eyebrow">Clinical report</p>
          <h2>Review the preliminary draft.</h2>
          <p>Edit any section before saving the report to the patient record.</p>
        </div>
        {edited && <button className="text-button" onClick={reset}>Reset draft</button>}
      </header>

      <dl className="report-demographics">
        <div><dt>Patient ID</dt><dd>{report.patient_id}</dd></div>
        <div><dt>Study date</dt><dd>{formatDate(report.scan_date)}</dd></div>
        <div><dt>Modality</dt><dd>{report.modality}</dd></div>
        <div><dt>Study</dt><dd>{report.scan_type === 'brain_mri' ? 'Brain MRI' : 'Chest X-ray'}</dd></div>
      </dl>

      <div className="report-sections">
        <label>
          <span><b>01</b> Findings</span>
          <textarea
            value={findings}
            onChange={(event) => change(setFindings, event.target.value)}
            aria-label="Clinical findings"
          />
        </label>
        <label>
          <span><b>02</b> Impression</span>
          <textarea
            className="report-textarea--compact"
            value={impression}
            onChange={(event) => change(setImpression, event.target.value)}
            aria-label="Clinical impression"
          />
        </label>
        <label>
          <span><b>03</b> Recommendations</span>
          <textarea
            className="report-textarea--compact"
            value={recommendations}
            onChange={(event) => change(setRecommendations, event.target.value)}
            aria-label="Clinical recommendations"
          />
        </label>
      </div>

      <div className="clinical-notice">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5m0 3h.01M10 3.5 2.6 17a2 2 0 0 0 1.8 3h15.2a2 2 0 0 0 1.8-3L14 3.5a2.3 2.3 0 0 0-4 0Z" /></svg>
        <p>{report.disclaimer}</p>
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}
      <footer className="report-actions">
        <span>{edited ? 'Draft has unsaved edits' : 'Draft matches the prepared report'}</span>
        <button className="button button--primary" onClick={() => void download()} disabled={downloading}>
          <span>{downloading ? 'Preparing PDF…' : 'Download clinical PDF'}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0 4-4m-4 4-4-4M5 20h14" /></svg>
        </button>
      </footer>
    </section>
  );
}
