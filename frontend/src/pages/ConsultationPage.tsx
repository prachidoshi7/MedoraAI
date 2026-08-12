import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { createDiagnosticOrder, createPrescription, generateCaseStudy, getAppointment, updateAppointmentNotes, updateAppointmentStatus } from '../api/client';
import { SCAN_TYPES } from '../types';
import type { Appointment, AppointmentStatus, Medication, ScanType } from '../types';

const emptyMedication: Medication = { name: '', dosage: '', frequency: '', duration: '' };

export default function ConsultationPage() {
  const { appointmentId } = useParams();
  const navigate = useNavigate();
  const id = Number(appointmentId);
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const [notes, setNotes] = useState('');
  const [scanType, setScanType] = useState<ScanType>('chest_xray');
  const [priority, setPriority] = useState('routine');
  const [clinicalNotes, setClinicalNotes] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [instructions, setInstructions] = useState('');
  const [medications, setMedications] = useState<Medication[]>([{ ...emptyMedication }]);
  const [followUp, setFollowUp] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => { getAppointment(id).then((item) => { setAppointment(item); setNotes(item.notes); }).catch((err) => setError(err.response?.data?.detail || 'Appointment not found.')); }, [id]);
  const changeStatus = async (status: AppointmentStatus) => { const next = await updateAppointmentStatus(id, status); setAppointment(next); setMessage(`Appointment marked ${status.replace('_', ' ')}.`); };
  const saveNotes = async () => { const next = await updateAppointmentNotes(id, notes); setAppointment(next); setMessage('Consultation notes saved.'); };
  const orderTest = async () => { await createDiagnosticOrder({ appointment_id: id, scan_type: scanType, priority, clinical_notes: clinicalNotes }); setClinicalNotes(''); setMessage('Diagnostic order sent to the radiology lab.'); };
  const prescribe = async () => { await createPrescription({ appointment_id: id, medications: medications.filter((item) => item.name.trim()), instructions, diagnosis }); setMessage('Prescription added to the patient record.'); };
  const createCase = async () => { const item = await generateCaseStudy({ appointment_id: id, clinical_history: notes, diagnosis, treatment_plan: instructions, follow_up_plan: followUp }); navigate(`/doctor/case-study/${item.id}`); };
  const safe = async (action: () => Promise<void>) => { setError(''); setMessage(''); try { await action(); } catch (err: any) { setError(err.response?.data?.detail || 'Could not save this clinical action.'); } };

  if (!appointment) return <div className="workspace-page portal-page">{error || 'Loading consultation…'}</div>;
  return (
    <div className="workspace-page portal-page">
      <header className="portal-hero consultation-hero"><div><p className="eyebrow">Consultation #{appointment.id} · {appointment.status}</p><h1>{appointment.patient.full_name}</h1><p>{appointment.reason}</p></div><div className="flow-actions"><button className="button" onClick={() => safe(() => changeStatus('confirmed'))}>Confirm</button><button className="button button--primary" onClick={() => safe(() => changeStatus('in_progress'))}>Start consultation</button></div></header>
      {(error || message) && <div className={error ? 'form-error' : 'success-banner'}>{error || message}</div>}
      <div className="clinical-layout">
        <aside className="patient-context portal-card"><p className="eyebrow">Patient context</p><span className="profile-avatar profile-avatar--large">{appointment.patient.full_name[0]}</span><h2>{appointment.patient.full_name}</h2><dl><div><dt>Patient ID</dt><dd>MED-{String(appointment.patient.id).padStart(4, '0')}</dd></div><div><dt>Contact</dt><dd>{appointment.patient.phone || 'Not supplied'}</dd></div><div><dt>Department</dt><dd>{appointment.department?.name}</dd></div><div><dt>Requested for</dt><dd>{appointment.scheduled_at ? new Date(appointment.scheduled_at).toLocaleString('en-IN') : 'Unscheduled'}</dd></div></dl></aside>
        <main className="consultation-stack">
          <section className="portal-card"><header><div><p className="eyebrow">Clinical notes</p><h2>Consultation assessment</h2></div><button className="button" onClick={() => safe(saveNotes)}>Save notes</button></header><textarea className="clinical-editor" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="History, examination findings, and initial assessment…" /></section>
          <section className="portal-card"><header><div><p className="eyebrow">Radiology referral</p><h2>Order a diagnostic study</h2></div></header><div className="form-grid"><label className="field"><span>Study</span><select value={scanType} onChange={(event) => setScanType(event.target.value as ScanType)}>{SCAN_TYPES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label className="field"><span>Priority</span><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="stat">STAT</option></select></label><label className="field field--wide"><span>Clinical indication</span><textarea rows={3} value={clinicalNotes} onChange={(event) => setClinicalNotes(event.target.value)} placeholder="Question for radiology and relevant clinical context…" /></label></div><div className="flow-actions"><button className="button button--primary" onClick={() => safe(orderTest)} disabled={!clinicalNotes.trim()}>Send order to lab</button></div></section>
          <section className="portal-card"><header><div><p className="eyebrow">Treatment</p><h2>Prescription and follow-up</h2></div></header><div className="form-grid"><label className="field field--wide"><span>Working diagnosis</span><input value={diagnosis} onChange={(event) => setDiagnosis(event.target.value)} /></label>{medications.map((medication, index) => <div className="medication-row" key={index}>{(['name', 'dosage', 'frequency', 'duration'] as const).map((field) => <label className="field" key={field}><span>{field}</span><input value={medication[field]} onChange={(event) => setMedications(medications.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: event.target.value } : item))} /></label>)}</div>)}<button className="text-button" type="button" onClick={() => setMedications([...medications, { ...emptyMedication }])}>＋ Add medication</button><label className="field field--wide"><span>Instructions / treatment plan</span><textarea rows={3} value={instructions} onChange={(event) => setInstructions(event.target.value)} /></label><label className="field field--wide"><span>Follow-up plan</span><textarea rows={2} value={followUp} onChange={(event) => setFollowUp(event.target.value)} /></label></div><div className="flow-actions"><button className="button" onClick={() => safe(prescribe)}>Save prescription</button><button className="button button--primary" onClick={() => safe(createCase)}>Generate case study</button></div></section>
          <div className="flow-actions flow-actions--between"><Link className="text-button" to="/doctor/dashboard">← Back to queue</Link><button className="button button--primary" onClick={() => safe(() => changeStatus('completed'))}>Complete consultation</button></div>
        </main>
      </div>
    </div>
  );
}
