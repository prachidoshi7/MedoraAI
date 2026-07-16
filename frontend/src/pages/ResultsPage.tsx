import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getReport } from '../api/client';
import HistorySidebar from '../components/HistorySidebar';
import PatientReport from '../components/PatientReport';
import ReportEditor from '../components/ReportEditor';
import ResultPanel from '../components/ResultPanel';
import ScanViewer from '../components/ScanViewer';
import type { AnalysisResponse, ReportData } from '../types';

type ReportTab = 'doctor' | 'patient';

export default function ResultsPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [tab, setTab] = useState<ReportTab>('doctor');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!scanId) return;
    setLoading(true);
    setError('');
    setTab('doctor');

    getReport(scanId)
      .then(({ report: nextReport }) => {
        setReport(nextReport);
        const stored = sessionStorage.getItem(`analysis_${scanId}`);
        if (stored) {
          try {
            setAnalysis(JSON.parse(stored) as AnalysisResponse);
            return;
          } catch {
            sessionStorage.removeItem(`analysis_${scanId}`);
          }
        }

        setAnalysis({
          scan_id: scanId,
          scan_type: nextReport.scan_type as AnalysisResponse['scan_type'],
          status: 'analyzed',
          classification: {
            top_label: nextReport.top_label || 'Unknown',
            confidence: nextReport.confidence || 0,
            severity: nextReport.severity as AnalysisResponse['classification']['severity'],
            all_scores: nextReport.all_scores || {},
          },
          localization: {
            type: 'heatmap',
            heatmap_url: `/static/heatmaps/${scanId}.png`,
            bounding_boxes: [],
          },
          analysis_time_ms: 0,
          analyzed_at: nextReport.generated_at,
        });
      })
      .catch((requestError) => setError(requestError.response?.data?.detail || 'This report could not be loaded.'))
      .finally(() => setLoading(false));
  }, [scanId]);

  if (loading) {
    return (
      <div className="workspace-page results-loading" aria-label="Loading report">
        <div className="skeleton skeleton--title" />
        <div className="skeleton skeleton--tabs" />
        <div className="results-skeleton-grid"><div className="skeleton" /><div className="skeleton" /></div>
      </div>
    );
  }

  if (error || !analysis || !report || !scanId) {
    return (
      <div className="workspace-page empty-state-page">
        <div className="empty-state-card">
          <span>!</span>
          <p className="eyebrow">Report unavailable</p>
          <h1>We could not open this study.</h1>
          <p>{error || 'The study data is incomplete.'}</p>
          <button className="button button--primary" onClick={() => navigate('/upload')}>Return to dashboard</button>
        </div>
      </div>
    );
  }

  const studyLabel = analysis.scan_type === 'brain_mri' ? 'Brain MRI' : 'Chest X-ray';
  const created = report.generated_at ? new Date(report.generated_at) : null;

  return (
    <div className="workspace-page results-page">
      <header className="case-header">
        <div>
          <button className="back-link" onClick={() => navigate('/upload')}>← Dashboard</button>
          <p className="eyebrow">Case {scanId.slice(0, 8).toUpperCase()}</p>
          <h1>{studyLabel} <em>review.</em></h1>
        </div>
        <dl className="case-header__meta">
          <div><dt>Patient</dt><dd>{report.patient_id}</dd></div>
          <div><dt>Prepared</dt><dd>{created && !Number.isNaN(created.getTime()) ? created.toLocaleDateString('en', { day: '2-digit', month: 'short', year: 'numeric' }) : report.scan_date}</dd></div>
          <div><dt>Status</dt><dd><i className="status-pulse" /> Ready for review</dd></div>
        </dl>
      </header>

      <div className="report-tabbar" role="tablist" aria-label="Report audience">
        <button
          role="tab"
          aria-selected={tab === 'doctor'}
          className={tab === 'doctor' ? 'active' : ''}
          onClick={() => setTab('doctor')}
        >
          <span>01</span><strong>Doctor report</strong><small>Detailed clinical review</small>
        </button>
        <button
          role="tab"
          aria-selected={tab === 'patient'}
          className={tab === 'patient' ? 'active' : ''}
          onClick={() => setTab('patient')}
        >
          <span>02</span><strong>Patient explanation</strong><small>Simple · native language</small>
        </button>
      </div>

      {tab === 'doctor' ? (
        <div className="doctor-report-layout" role="tabpanel">
          <div className="doctor-report-main">
            <ScanViewer
              scanImageUrl={`/static/uploads/${scanId}.png`}
              heatmapUrl={analysis.localization.heatmap_url}
              scanType={analysis.scan_type}
              heatmapTargetLabel={report.heatmap_target_label || analysis.classification.heatmap_target_label}
            />
            <ReportEditor scanId={scanId} report={report} />
          </div>
          <div className="doctor-report-aside">
            <ResultPanel
              classification={analysis.classification}
              scanType={analysis.scan_type}
              analysisTimeMs={analysis.analysis_time_ms}
            />
            <HistorySidebar currentScanId={scanId} />
          </div>
        </div>
      ) : (
        <div role="tabpanel"><PatientReport scanId={scanId} /></div>
      )}
    </div>
  );
}
