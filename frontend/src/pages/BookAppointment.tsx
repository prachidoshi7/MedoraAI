import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bookAppointment, getDepartments, getDoctors } from '../api/client';
import type { Department, Doctor } from '../types';

export default function BookAppointment() {
  const navigate = useNavigate();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [doctorId, setDoctorId] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { getDepartments().then(setDepartments).catch(() => setError('Could not load departments.')); }, []);
  useEffect(() => {
    if (!departmentId) { setDoctors([]); return; }
    getDoctors(departmentId).then(setDoctors).catch(() => setError('Could not load doctors.'));
  }, [departmentId]);
  const selectedDoctor = useMemo(() => doctors.find((item) => item.id === doctorId), [doctors, doctorId]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!departmentId || !doctorId || !scheduledAt) return;
    setBusy(true); setError('');
    try {
      await bookAppointment({ doctor_id: doctorId, department_id: departmentId, reason, scheduled_at: new Date(scheduledAt).toISOString() });
      navigate('/patient/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not book this appointment.');
    } finally { setBusy(false); }
  };

  return (
    <div className="workspace-page portal-page narrow-page">
      <header className="portal-hero"><div><p className="eyebrow">New consultation</p><h1>Choose the right care team.</h1><p>Select a department, specialist, and preferred time.</p></div></header>
      <form className="booking-flow" onSubmit={submit}>
        <section className="portal-card">
          <header><span className="step-number">01</span><div><p className="eyebrow">Department</p><h2>Where should we begin?</h2></div></header>
          <div className="department-grid">
            {departments.filter((item) => item.name !== 'Radiology').map((item) => <button type="button" key={item.id} className={departmentId === item.id ? 'department-card is-selected' : 'department-card'} onClick={() => { setDepartmentId(item.id); setDoctorId(null); }}><span>{item.icon}</span><strong>{item.name}</strong><small>{item.description}</small></button>)}
          </div>
        </section>
        <section className={`portal-card${departmentId ? '' : ' is-disabled'}`}>
          <header><span className="step-number">02</span><div><p className="eyebrow">Specialist</p><h2>Select your doctor</h2></div></header>
          <div className="doctor-grid">
            {doctors.map((doctor) => <button type="button" key={doctor.id} className={doctorId === doctor.id ? 'doctor-card is-selected' : 'doctor-card'} onClick={() => setDoctorId(doctor.id)}><span className="profile-avatar">{doctor.full_name.split(' ').slice(-1)[0][0]}</span><span><strong>{doctor.full_name}</strong><small>{doctor.specialization}</small></span><i /></button>)}
            {departmentId && !doctors.length && <div className="portal-empty">No doctors available in this department.</div>}
          </div>
        </section>
        <section className={`portal-card${selectedDoctor ? '' : ' is-disabled'}`}>
          <header><span className="step-number">03</span><div><p className="eyebrow">Visit details</p><h2>Tell us what brings you in</h2></div></header>
          <div className="form-grid">
            <label className="field field--wide"><span>Reason / symptoms</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={4} placeholder="Describe your concern, symptoms, and how long you have had them…" required minLength={3} /></label>
            <label className="field"><span>Preferred date and time</span><input type="datetime-local" value={scheduledAt} min={new Date().toISOString().slice(0, 16)} onChange={(event) => setScheduledAt(event.target.value)} required /></label>
            <div className="booking-summary"><span>Consulting</span><strong>{selectedDoctor?.full_name || 'Select a doctor'}</strong><small>{selectedDoctor?.specialization}</small></div>
          </div>
        </section>
        {error && <div className="form-error">{error}</div>}
        <div className="flow-actions"><button type="button" className="button" onClick={() => navigate(-1)}>Cancel</button><button className="button button--primary" disabled={busy || !selectedDoctor}>{busy ? 'Booking…' : 'Request appointment'}</button></div>
      </form>
    </div>
  );
}
