import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { downloadCaseStudyPdf, finalizeCaseStudy, getCaseStudy } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { CaseStudy } from '../types';

export default function CaseStudyView() {
  const { caseStudyId } = useParams();
  const { user } = useAuth();
  const [caseStudy, setCaseStudy] = useState<CaseStudy | null>(null);
  const [error, setError] = useState('');
  const id = Number(caseStudyId);
  useEffect(() => { getCaseStudy(id).then(setCaseStudy).catch((err) => setError(err.response?.data?.detail || 'Case study not found.')); }, [id]);
  const finalize = async () => { try { setCaseStudy(await finalizeCaseStudy(id)); } catch (err: any) { setError(err.response?.data?.detail || 'Could not finalize this case.'); } };
  const download = async () => { try { const blob = await downloadCaseStudyPdf(id); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `MedoraAI_Case_${id}.pdf`; anchor.click(); URL.revokeObjectURL(url); } catch { setError('Could not download the case study.'); } };
  if (!caseStudy) return <div className="workspace-page portal-page">{error || 'Loading case study…'}</div>;
  return (
    <div className="workspace-page portal-page case-study-page">
      <header className="case-study-header"><div><p className="eyebrow">Complete patient journey</p><h1>Case study <em>#{caseStudy.id}</em></h1><p>{caseStudy.patient.full_name} · Appointment #{caseStudy.appointment_id}</p></div><div className="flow-actions"><span className={`status-pill status-${caseStudy.status}`}>{caseStudy.status}</span><button className="button" onClick={download}>Download PDF</button>{user?.role === 'doctor' && caseStudy.status !== 'final' && <button className="button button--primary" onClick={finalize}>Sign & finalize</button>}</div></header>
      {error && <div className="form-error">{error}</div>}
      <div className="case-timeline"><span className="is-complete">Consultation</span><i /><span className={caseStudy.scan_ids.length ? 'is-complete' : ''}>AI diagnostics</span><i /><span className={caseStudy.prescriptions.length ? 'is-complete' : ''}>Treatment</span><i /><span className={caseStudy.status === 'final' ? 'is-complete' : ''}>Final record</span></div>
      <article className="case-paper">
        <header><div><span>MedoraAI Hospital Intelligence</span><strong>Integrated clinical case record</strong></div><dl><div><dt>Patient</dt><dd>{caseStudy.patient.full_name}</dd></div><div><dt>Record</dt><dd>MED-{String(caseStudy.patient.id).padStart(4, '0')}</dd></div><div><dt>Status</dt><dd>{caseStudy.status.toUpperCase()}</dd></div></dl></header>
        {[
          ['Chief complaint', caseStudy.chief_complaint],
          ['Clinical history', caseStudy.clinical_history],
          ['Diagnostic findings', caseStudy.diagnostic_findings],
          ['Clinical diagnosis', caseStudy.diagnosis],
          ['Treatment plan', caseStudy.treatment_plan],
        ].map(([label, value], index) => <section className="case-section" key={label}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{label}</h2><p>{value || 'Not documented.'}</p></div></section>)}
        <section className="case-section"><span>06</span><div><h2>Diagnostic studies</h2><div className="scan-link-grid">{caseStudy.scan_ids.map((scanId) => <Link key={scanId} to={`/results/${scanId}`}><strong>AI imaging study</strong><small>{scanId.slice(0, 8).toUpperCase()} · Open report →</small></Link>)}{!caseStudy.scan_ids.length && <p>No linked scans.</p>}</div></div></section>
        <section className="case-section"><span>07</span><div><h2>Prescription</h2>{caseStudy.prescriptions.map((prescription) => <div className="prescription-block" key={prescription.id}><p><strong>{prescription.diagnosis}</strong></p>{prescription.medications.map((medication, index) => <div className="medication-line" key={index}><strong>{medication.name}</strong><span>{medication.dosage}</span><span>{medication.frequency}</span><span>{medication.duration}</span></div>)}<small>{prescription.instructions}</small></div>)}{!caseStudy.prescriptions.length && <p>No prescription recorded.</p>}</div></section>
        <section className="case-section"><span>08</span><div><h2>Follow-up plan</h2><p>{caseStudy.follow_up_plan || 'Not documented.'}</p><div className="doctor-signature"><span>Clinician notes</span><strong>{caseStudy.doctor_notes || 'No additional notes.'}</strong></div></div></section>
      </article>
    </div>
  );
}
