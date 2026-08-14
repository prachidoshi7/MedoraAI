import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMyAppointments, getMyCaseStudies, getMyDiagnosticOrders } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Appointment, CaseStudy, DiagnosticOrder } from '../types';

export default function DoctorDashboard() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [orders, setOrders] = useState<DiagnosticOrder[]>([]);
  const [cases, setCases] = useState<CaseStudy[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { Promise.all([getMyAppointments(), getMyDiagnosticOrders(), getMyCaseStudies()]).then(([a, o, c]) => { setAppointments(a); setOrders(o); setCases(c); }).catch((err) => setError(err.response?.data?.detail || 'Could not load clinical queue.')); }, []);
  const active = appointments.filter((item) => !['completed', 'cancelled'].includes(item.status));
  return (
    <div className="workspace-page portal-page">
      <header className="portal-hero"><div><p className="eyebrow">{user?.department_name || 'Clinical service'} · Doctor dashboard</p><h1>{user?.full_name}</h1><p className="doctor-credential-line">{[user?.qualification, user?.specialization].filter(Boolean).join(' · ')}</p><p>One queue from consultation through diagnostic sign-off.</p></div><span className="env-badge"><i /> Clinical systems live</span></header>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid metric-grid--three">
        <article><span>Active consultations</span><strong>{active.length}</strong><small>{appointments.filter((item) => item.status === 'requested').length} awaiting confirmation</small></article>
        <article><span>Reports to review</span><strong>{orders.filter((item) => item.status === 'completed').length}</strong><small>AI analysis completed</small></article>
        <article><span>Final case studies</span><strong>{cases.filter((item) => item.status === 'final').length}</strong><small>{cases.filter((item) => item.status === 'draft').length} drafts in progress</small></article>
      </section>
      <div className="portal-columns portal-columns--clinical">
        <section className="portal-card">
          <header><div><p className="eyebrow">Consultation queue</p><h2>Appointments</h2></div></header>
          <div className="record-list">
            {appointments.map((item) => <Link key={item.id} to={`/doctor/consultation/${item.id}`} className="record-row record-row--link"><span className={`status-dot status-${item.status}`} /><div><strong>{item.patient.full_name}</strong><small>{item.scheduled_at ? new Date(item.scheduled_at).toLocaleString('en-IN') : 'Unscheduled'} · {item.status}</small><p>{item.reason}</p></div><span>Open →</span></Link>)}
            {!appointments.length && <div className="portal-empty">No appointments in your queue.</div>}
          </div>
        </section>
        <section className="portal-card">
          <header><div><p className="eyebrow">Diagnostic inbox</p><h2>Reports</h2></div></header>
          <div className="record-list">
            {orders.map((item) => item.scan_id ? <Link key={item.id} to={`/results/${item.scan_id}`} className="record-row record-row--link"><span className="record-icon">AI</span><div><strong>{item.patient.full_name}</strong><small>{item.scan_type.replace('_', ' ')} · {item.status}</small><p>{item.clinical_notes}</p></div><span>Review →</span></Link> : <article key={item.id} className="record-row"><span className="record-icon">{item.priority[0].toUpperCase()}</span><div><strong>{item.patient.full_name}</strong><small>{item.scan_type.replace('_', ' ')} · lab pending</small><p>{item.clinical_notes}</p></div><span className="status-pill">{item.status}</span></article>)}
            {!orders.length && <div className="portal-empty">No diagnostic orders yet.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
