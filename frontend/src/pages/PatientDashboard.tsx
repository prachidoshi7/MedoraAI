import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMyAppointments, getMyCaseStudies, getMyDiagnosticOrders, getMyPrescriptions } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Appointment, CaseStudy, DiagnosticOrder, Prescription } from '../types';

function dateLabel(value: string | null) {
  return value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Time to be confirmed';
}

export default function PatientDashboard() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [orders, setOrders] = useState<DiagnosticOrder[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [cases, setCases] = useState<CaseStudy[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getMyAppointments(), getMyDiagnosticOrders(), getMyPrescriptions(), getMyCaseStudies()])
      .then(([nextAppointments, nextOrders, nextPrescriptions, nextCases]) => {
        setAppointments(nextAppointments); setOrders(nextOrders); setPrescriptions(nextPrescriptions); setCases(nextCases);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load your care timeline.'));
  }, []);

  const nextAppointment = appointments.find((item) => !['completed', 'cancelled'].includes(item.status));
  return (
    <div className="workspace-page portal-page">
      <header className="portal-hero">
        <div><p className="eyebrow">Patient command center</p><h1>Good day, {user?.full_name.split(' ')[0]}.</h1><p>Your consultations, diagnostics, prescriptions, and case records—connected.</p></div>
        <Link className="button button--primary" to="/patient/book-appointment">＋ Book appointment</Link>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid">
        <article><span>Appointments</span><strong>{appointments.length}</strong><small>{nextAppointment ? `Next: ${dateLabel(nextAppointment.scheduled_at)}` : 'No upcoming visit'}</small></article>
        <article><span>Diagnostic studies</span><strong>{orders.length}</strong><small>{orders.filter((item) => item.status === 'completed').length} ready for review</small></article>
        <article><span>Prescriptions</span><strong>{prescriptions.length}</strong><small>Doctor-issued plans</small></article>
        <article><span>Final case studies</span><strong>{cases.filter((item) => item.status === 'final').length}</strong><small>Portable health records</small></article>
      </section>
      <div className="portal-columns">
        <section className="portal-card">
          <header><div><p className="eyebrow">Care timeline</p><h2>Appointments</h2></div><Link to="/patient/book-appointment">Book new →</Link></header>
          <div className="record-list">
            {appointments.length ? appointments.map((item) => (
              <article key={item.id} className="record-row">
                <span className={`status-dot status-${item.status}`} />
                <div><strong>{item.doctor.full_name}</strong><small>{item.department?.name} · {dateLabel(item.scheduled_at)}</small><p>{item.reason}</p></div>
                <span className="status-pill">{item.status.replace('_', ' ')}</span>
              </article>
            )) : <div className="portal-empty">No appointments yet. Choose a department to begin.</div>}
          </div>
        </section>
        <section className="portal-card">
          <header><div><p className="eyebrow">Clinical documents</p><h2>Recent records</h2></div></header>
          <div className="record-list">
            {cases.map((item) => <Link key={`case-${item.id}`} to={`/patient/case-study/${item.id}`} className="record-row record-row--link"><span className="record-icon">CS</span><div><strong>Case study #{item.id}</strong><small>{item.status} · {item.scan_ids.length} linked scans</small><p>{item.diagnosis || item.chief_complaint}</p></div><span>→</span></Link>)}
            {orders.filter((item) => item.scan_id && item.status === 'reviewed').map((item) => <Link key={`scan-${item.id}`} to={`/results/${item.scan_id}`} className="record-row record-row--link"><span className="record-icon">AI</span><div><strong>{item.scan_type.replace('_', ' ').toUpperCase()}</strong><small>{item.status} · ordered by {item.ordering_doctor.full_name}</small><p>{item.clinical_notes}</p></div><span>→</span></Link>)}
            {!cases.length && !orders.some((item) => item.scan_id && item.status === 'reviewed') && <div className="portal-empty">Doctor-approved reports will appear here.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
