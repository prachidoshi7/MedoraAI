import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { downloadPdf, regenerateReport, reviewReport, triggerPdfDownload } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { ReportData } from '../types';

interface ReportEditorProps {
  scanId: string;
  report: ReportData;
  onReportChange?: (report: ReportData) => void;
}

type DraftKey =
  | 'clinical_history'
  | 'technique'
  | 'image_quality'
  | 'findings'
  | 'impression'
  | 'differential_diagnosis'
  | 'recommendations'
  | 'critical_communication';

type ReportDraft = Record<DraftKey, string>;
type SectionGroup = 'Study context' | 'Interpretation' | 'Clinical close';

interface ReportSection {
  key: DraftKey;
  number: string;
  title: string;
  shortTitle: string;
  helper: string;
  group: SectionGroup;
  size: 'small' | 'medium' | 'large';
  prominent?: boolean;
}

const reportSections: ReportSection[] = [
  {
    key: 'clinical_history',
    number: '01',
    title: 'Clinical information',
    shortTitle: 'Clinical info',
    helper: 'Document only the indication and symptoms supplied with the examination.',
    group: 'Study context',
    size: 'small',
  },
  {
    key: 'technique',
    number: '02',
    title: 'Technique',
    shortTitle: 'Technique',
    helper: 'Record the available views, sequences, contrast details, and acquisition limitations.',
    group: 'Study context',
    size: 'medium',
  },
  {
    key: 'image_quality',
    number: '03',
    title: 'Study quality / limitations',
    shortTitle: 'Quality',
    helper: 'State diagnostic adequacy and any motion, positioning, coverage, or single-image limitation.',
    group: 'Study context',
    size: 'medium',
  },
  {
    key: 'findings',
    number: '04',
    title: 'Findings',
    shortTitle: 'Findings',
    helper: 'Describe only what is visible, organized by anatomy. Keep diagnoses and differential weighting out of this section.',
    group: 'Interpretation',
    size: 'large',
  },
  {
    key: 'impression',
    number: '05',
    title: 'Impression',
    shortTitle: 'Impression',
    helper: 'Number conclusions by clinical priority. This is where diagnostic language belongs.',
    group: 'Interpretation',
    size: 'large',
    prominent: true,
  },
  {
    key: 'differential_diagnosis',
    number: '06',
    title: 'Differential considerations',
    shortTitle: 'Differential',
    helper: 'Keep the list short, evidence-based, and ordered from favored to less likely.',
    group: 'Clinical close',
    size: 'medium',
  },
  {
    key: 'recommendations',
    number: '07',
    title: 'Recommendations',
    shortTitle: 'Recommendations',
    helper: 'Include only proportionate, actionable follow-up supported by the imaging interpretation.',
    group: 'Clinical close',
    size: 'medium',
  },
  {
    key: 'critical_communication',
    number: '08',
    title: 'Communication',
    shortTitle: 'Communication',
    helper: 'For urgent findings, record the recipient, method, date, and time. Use N/A for routine findings.',
    group: 'Clinical close',
    size: 'small',
  },
];

const routineCommunication = 'Not applicable — no critical or emergent finding requiring direct communication.';

const makeDraft = (report: ReportData): ReportDraft => {
  const communication = report.critical_communication?.trim();
  const normalizedCommunication = !communication || /^no critical communication generated\.?$/i.test(communication)
    ? routineCommunication
    : communication;

  return {
    clinical_history: report.clinical_history || 'Not provided.',
    technique: report.technique || '',
    image_quality: report.image_quality || '',
    findings: report.findings || '',
    impression: report.impression || '',
    differential_diagnosis: report.differential_diagnosis || 'None based on the supplied image.',
    recommendations: report.recommendations || '',
    critical_communication: normalizedCommunication,
  };
};

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en', { day: '2-digit', month: 'short', year: 'numeric' }).format(date);
};

const isRoutineCommunication = (value: string) => {
  const normalized = value.trim();
  return !normalized || /^(n\/?a|not applicable|none|no critical communication)/i.test(normalized);
};

function AutoGrowTextarea({
  section,
  value,
  onChange,
  readOnly,
}: {
  section: ReportSection;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      className={`report-textarea report-textarea--${section.size}`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={section.title}
      spellCheck
      readOnly={readOnly}
    />
  );
}

export default function ReportEditor({ scanId, report, onReportChange }: ReportEditorProps) {
  const { user } = useAuth();
  const canReview = user?.role === 'doctor' || user?.role === 'admin';
  const canRegenerate = user?.role === 'admin';
  const original = useMemo(() => makeDraft(report), [report]);
  const [draft, setDraft] = useState<ReportDraft>(original);
  const [downloading, setDownloading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState('');
  const [doctorNotes, setDoctorNotes] = useState('');
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);

  useEffect(() => setDraft(original), [original]);
  useEffect(() => setDoctorNotes(report.doctor_assessment || ''), [report.doctor_assessment]);

  const communicationIsRoutine = isRoutineCommunication(draft.critical_communication);
  const examName = ({ brain_mri: 'Limited brain MRI image', chest_xray: 'Chest radiograph', lung_ct: 'Limited lung CT image', kidney_us: 'Kidney ultrasound image' } as Record<string, string>)[report.scan_type] || 'Medical imaging study';
  const reportSource = report.llm_provider === 'maira-2'
    ? 'MAIRA-2 independent image review'
    : `${report.llm_provider || 'AI'} image-report draft`;

  const jumpToSection = (key: DraftKey) => {
    document.getElementById(`report-section-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
    try {
      const blob = await downloadPdf(scanId);
      triggerPdfDownload(blob, scanId);
    } catch {
      setError('The PDF could not be prepared. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  const approve = async () => {
    setApproving(true);
    setError('');
    try {
      const result = await reviewReport(scanId, {
        doctor_notes: doctorNotes,
        approve: true,
      });
      onReportChange?.(result.report);
      setApproved(true);
    } catch {
      setError('The report could not be approved. Confirm that you are assigned to this case.');
    } finally {
      setApproving(false);
    }
  };

  return (
    <section className="report-editor">
      <header className="report-editor__header">
        <div className="report-title-block">
          <div className="report-status-line">
            <span className="report-status-badge"><i /> {approved ? 'Doctor approved' : 'Preliminary'}</span>
            <span>{reportSource}</span>
            <span>Unverified draft</span>
          </div>
          <p className="eyebrow">Primary image review</p>
          <h2>Preliminary imaging interpretation</h2>
          <p>This image-aware draft is the primary AI review. Verify every section against the complete source examination before signing.</p>
        </div>
        <div className="report-header-actions">
          {canRegenerate && <button className="button button--secondary" onClick={() => void regenerate()} disabled={regenerating || downloading}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 7v5h-5M5 17v-5h5M7.1 8.2A6 6 0 0 1 18.5 10M5.5 14a6 6 0 0 0 11.4 1.8" /></svg>
            {regenerating ? 'Regenerating…' : 'Regenerate draft'}
          </button>}
        </div>
      </header>

      <dl className="report-demographics">
        <div><dt>Patient ID / MRN</dt><dd>{report.patient_id}</dd></div>
        <div><dt>Exam date</dt><dd>{formatDate(report.scan_date)}</dd></div>
        <div><dt>Examination</dt><dd>{examName}</dd></div>
        <div><dt>Modality</dt><dd>{report.modality}</dd></div>
        <div><dt>Accession</dt><dd>{scanId.slice(0, 8).toUpperCase()}</dd></div>
      </dl>

      <div className="report-workspace">
        <aside className="report-outline" aria-label="Report outline">
          <div className="report-outline__sticky">
            <div className="report-outline__heading">
              <p className="eyebrow">Report outline</p>
              <span>{reportSections.length} sections</span>
            </div>
            <nav>
              {reportSections.map((section) => (
                <button key={section.key} onClick={() => jumpToSection(section.key)}>
                  <span>{section.number}</span>
                  <strong>{section.shortTitle}</strong>
                  <i className={draft[section.key].trim() ? 'is-complete' : ''} aria-hidden="true" />
                </button>
              ))}
            </nav>
            <div className="report-quality-rules">
              <span>Reporting standard</span>
              <p>Use exact measurements. Keep observations in Findings and conclusions in Impression.</p>
            </div>
          </div>
        </aside>

        <main className="report-document">
          <div className="report-document__masthead">
            <div>
              <span>Examination</span>
              <strong>{examName}</strong>
            </div>
            <div>
              <span>Report status</span>
              <strong>Awaiting radiologist review</strong>
            </div>
          </div>

          {(['Study context', 'Interpretation', 'Clinical close'] as SectionGroup[]).map((group) => (
            <section className="report-section-group" key={group} aria-label={group}>
              <header className="report-section-group__header"><span>{group}</span><i /></header>
              {reportSections.filter((section) => section.group === group).map((section) => {
                const isCommunication = section.key === 'critical_communication';
                return (
                  <article
                    id={`report-section-${section.key}`}
                    className={`report-field${section.prominent ? ' report-field--prominent' : ''}${isCommunication ? ' report-field--communication' : ''}`}
                    key={section.key}
                  >
                    <header className="report-field__header">
                      <span className="report-field__number">{section.number}</span>
                      <div>
                        <div className="report-field__title-row">
                          <h3>{section.title}</h3>
                          <span className="report-readonly-badge">Read only</span>
                          {section.prominent && <span className="report-priority-badge">Priority order</span>}
                          {isCommunication && (
                            <span className={`communication-state${communicationIsRoutine ? '' : ' communication-state--critical'}`}>
                              <i />{communicationIsRoutine ? 'Routine' : 'Direct communication'}
                            </span>
                          )}
                        </div>
                        <p>{section.helper}</p>
                      </div>
                    </header>
                    <div className="report-field__editor">
                      <AutoGrowTextarea section={section} value={draft[section.key]} onChange={() => undefined} readOnly />
                    </div>
                  </article>
                );
              })}
            </section>
          ))}

          <footer className="report-signature">
            <div>
              <span>Verification status</span>
              <strong><i /> Awaiting radiologist review</strong>
            </div>
            <div>
              <span>Electronic signature</span>
              <strong>Not yet applied</strong>
            </div>
          </footer>
        </main>
      </div>

      <div className="report-supporting-info">
        <details className="report-provenance">
          <summary>Method and known limitations</summary>
          <div>
            <p><strong>Method</strong>{report.methodology || 'Automated image classification with model-attribution heatmap explainability.'}</p>
            <p><strong>Limitations</strong>{report.limitations || 'The output is limited by the supplied image and the trained finding categories.'}</p>
          </div>
        </details>

        <div className="clinical-notice">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8v5m0 3h.01M10 3.5 2.6 17a2 2 0 0 0 1.8 3h15.2a2.3 2.3 0 0 0-4 0Z" /></svg>
          <div><strong>Clinical verification required</strong><p>{report.disclaimer}</p></div>
        </div>
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}
      {canReview && (
        <div className="doctor-review-strip">
          <label><span>Doctor assessment / sign-off note</span><textarea rows={2} value={doctorNotes} onChange={(event) => setDoctorNotes(event.target.value)} placeholder="Add your clinical judgment or communication note…" /></label>
          <button className="button button--primary" onClick={() => void approve()} disabled={approving || approved}>{approved ? 'Approved & sent' : approving ? 'Approving…' : 'Approve & release to patient'}</button>
        </div>
      )}
      <footer className="report-actions">
        <div>
          <span className="edit-state"><i /> Read-only generated report</span>
          <small>{canReview ? 'Only the doctor clinical assessment above can be edited before approval.' : 'Generated report sections cannot be modified.'}</small>
        </div>
        <button className="button button--primary" onClick={() => void download()} disabled={downloading || regenerating}>
          <span>{downloading ? 'Preparing PDF…' : 'Download clinical PDF'}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0 4-4m-4 4-4-4M5 20h14" /></svg>
        </button>
      </footer>
    </section>
  );
}
