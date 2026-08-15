import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getReport } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import PatientReport from '../components/PatientReport';
import PatientFinalReport from '../components/PatientFinalReport';
import ReportEditor from '../components/ReportEditor';
import ResultPanel from '../components/ResultPanel';
import ScanViewer from '../components/ScanViewer';
import type { AnalysisResponse, ReportData } from '../types';

type ReportTab = 'doctor' | 'patient';

const REPORT_POLL_INTERVAL_MS = 1000;
const REPORT_POLL_TIMEOUT_MS = 180000;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function ResultsPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [tab, setTab] = useState<ReportTab>(user?.role === 'patient' ? 'patient' : 'doctor');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;

    setLoading(true);
    setError('');
    setTab(user?.role === 'patient' ? 'patient' : 'doctor');

    const stored = sessionStorage.getItem(`analysis_${scanId}`);
    let storedAnalysis: AnalysisResponse | null = null;
    if (stored) {
      try {
        storedAnalysis = JSON.parse(stored) as AnalysisResponse;
        setAnalysis(storedAnalysis);
      } catch {
        sessionStorage.removeItem(`analysis_${scanId}`);
      }
    }

    const loadReport = async () => {
      const deadline = Date.now() + REPORT_POLL_TIMEOUT_MS;

      try {
        while (!cancelled) {
          try {
            const { report: nextReport } = await getReport(scanId);
            if (cancelled) return;

            setReport(nextReport);
            if (!storedAnalysis) {
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
            }
            return;
          } catch (requestError: any) {
            const detail = requestError.response?.data?.detail;
            const reportPending = requestError.response?.status === 404
              && typeof detail === 'string'
              && detail.startsWith('Report generation is still in progress');

            if (reportPending && Date.now() < deadline) {
              await wait(REPORT_POLL_INTERVAL_MS);
              continue;
            }
            throw requestError;
          }
        }
        throw new Error('Report generation did not finish within 3 minutes.');
      } catch (requestError: any) {
        if (!cancelled) {
          setError(requestError.response?.data?.detail || requestError.message || 'This report could not be loaded.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadReport();
    return () => {
      cancelled = true;
    };
  }, [scanId, user?.role]);

  if (loading) {
    return (
      <div className="workspace-page results-loading" aria-label="Loading report">
        <p className="eyebrow">Image analysis complete</p>
        <h1>Preparing the image-aware clinical draft.</h1>
        <p>The primary image-aware reporting model is reviewing the supplied image. Experimental classification and localization remain secondary evidence.</p>
        {analysis ? (
          <div className="result-grid">
            <ScanViewer
              scanImageUrl={`/static/uploads/${scanId}.png`}
              heatmapUrl={analysis.localization.heatmap_url}
              scanType={analysis.scan_type}
              heatmapTargetLabel={analysis.classification.heatmap_target_label}
            />
            <ResultPanel
              classification={analysis.classification}
              scanType={analysis.scan_type}
              analysisTimeMs={analysis.analysis_time_ms}
            />
          </div>
        ) : (
          <div className="results-skeleton-grid"><div className="skeleton" /><div className="skeleton" /></div>
        )}
        <div className="skeleton skeleton--tabs" />
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

  const studyLabel = ({ brain_mri: 'Brain MRI', chest_xray: 'Chest X-ray', lung_ct: 'Lung CT', kidney_us: 'Kidney ultrasound' } as Record<string, string>)[analysis.scan_type] || 'Imaging';
  const created = report.generated_at ? new Date(report.generated_at) : null;

  return (
    <div className="workspace-page results-page">
      <header className="case-header">
        <div>
          <button className="back-link" onClick={() => navigate(user?.role === 'patient' ? '/patient/dashboard' : user?.role === 'lab_tech' ? '/lab/dashboard' : '/doctor/dashboard')}>← Dashboard</button>
          <p className="eyebrow">Case {scanId.slice(0, 8).toUpperCase()}</p>
          <h1>{studyLabel} <em>{user?.role === 'patient' ? 'final report.' : 'review.'}</em></h1>
        </div>
        <dl className="case-header__meta">
          <div><dt>Patient</dt><dd>{report.patient_id}</dd></div>
          <div><dt>Prepared</dt><dd>{created && !Number.isNaN(created.getTime()) ? created.toLocaleDateString('en', { day: '2-digit', month: 'short', year: 'numeric' }) : report.scan_date}</dd></div>
          <div><dt>Status</dt><dd><i className="status-pulse" /> {user?.role === 'patient' ? 'Final · Doctor approved' : 'Ready for review'}</dd></div>
        </dl>
      </header>

      {user?.role !== 'patient' && <div className="report-tabbar" role="tablist" aria-label="Report audience">
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
      </div>}

      {user?.role === 'patient' ? (
        <PatientFinalReport scanId={scanId} report={report} heatmapUrl={analysis.localization.heatmap_url} originalImageUrl={`/static/uploads/${scanId}.png`} />
      ) : tab === 'doctor' ? (
        <div className="doctor-report-layout" role="tabpanel">
          <div className="result-grid">
            <ScanViewer
              scanImageUrl={`/static/uploads/${scanId}.png`}
              heatmapUrl={analysis.localization.heatmap_url}
              scanType={analysis.scan_type}
              heatmapTargetLabel={report.heatmap_target_label || analysis.classification.heatmap_target_label}
            />
            <ResultPanel
              classification={analysis.classification}
              scanType={analysis.scan_type}
              analysisTimeMs={analysis.analysis_time_ms}
            />
          </div>
          <ReportEditor scanId={scanId} report={report} onReportChange={setReport} />
        </div>
      ) : (
        <div role="tabpanel"><PatientReport scanId={scanId} /></div>
      )}
    </div>
  );
}
