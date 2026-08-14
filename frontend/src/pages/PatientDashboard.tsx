import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { downloadPdf, getMyAppointments, getMyCaseStudies, getMyDiagnosticOrders, getMyPharmacyBills, getMyPrescriptions, triggerPdfDownload } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Appointment, CaseStudy, DiagnosticOrder, PharmacyBill, Prescription } from '../types';

const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' });

function dateLabel(value: string | null) {
  return value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Time to be confirmed';
}

export default function PatientDashboard() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [orders, setOrders] = useState<DiagnosticOrder[]>([]);
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [bills, setBills] = useState<PharmacyBill[]>([]);
  const [cases, setCases] = useState<CaseStudy[]>([]);
  const [error, setError] = useState('');
  const [downloadingScanId, setDownloadingScanId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMyAppointments(), getMyDiagnosticOrders(), getMyPrescriptions(), getMyCaseStudies(), getMyPharmacyBills()])
      .then(([nextAppointments, nextOrders, nextPrescriptions, nextCases, nextBills]) => {
        setAppointments(nextAppointments); setOrders(nextOrders); setPrescriptions(nextPrescriptions); setCases(nextCases); setBills(nextBills);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load your care timeline.'));
  }, []);

  const nextAppointment = appointments.find((item) => !['completed', 'cancelled'].includes(item.status));
  const billedPrescriptionIds = new Set(bills.map((bill) => bill.prescription.id));
  const downloadFinalReport = async (scanId: string) => {
    setDownloadingScanId(scanId);
    setError('');
    try {
      const blob = await downloadPdf(scanId);
      triggerPdfDownload(blob, scanId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not download the final report.');
    } finally {
      setDownloadingScanId(null);
    }
  };
  return (
    <div className="workspace-page portal-page">
      <header className="portal-hero">
        <div><p className="eyebrow">Patient command center</p><h1>Good day, {user?.full_name.split(' ')[0]}.</h1><p>Your consultations, diagnostics, prescriptions, and case records—connected.</p></div>
        <Link className="button button--primary" to="/patient/book-appointment">＋ Book appointment</Link>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid metric-grid--five">
        <article><span>Appointments</span><strong>{appointments.length}</strong><small>{nextAppointment ? `Next: ${dateLabel(nextAppointment.scheduled_at)}` : 'No upcoming visit'}</small></article>
        <article><span>Diagnostic studies</span><strong>{orders.length}</strong><small>{orders.filter((item) => item.status === 'completed').length} ready for review</small></article>
        <article><span>Prescriptions</span><strong>{prescriptions.length}</strong><small>Doctor-issued plans</small></article>
        <article><span>Medicine bills</span><strong>{bills.length}</strong><small>{bills.filter((bill) => bill.status === 'dispensed').length} orders dispensed</small></article>
        <article><span>Final case studies</span><strong>{cases.filter((item) => item.status === 'final').length}</strong><small>Portable health records</small></article>
      </section>
      <div className="portal-columns">
        <section className="portal-card">
          <header><div><p className="eyebrow">Care timeline</p><h2>Appointments</h2></div><Link to="/patient/book-appointment">Book new →</Link></header>
          <div className="record-list">
            {appointments.length ? appointments.map((item) => (
              <article key={item.id} className="record-row">
                <span className={`status-dot status-${item.status}`} />
                <div><strong>{item.doctor.full_name}</strong><small>{[item.doctor.qualification, item.doctor.specialization, item.department?.name].filter(Boolean).join(' · ')}</small><small>{dateLabel(item.scheduled_at)}</small><p>{item.reason}</p></div>
                <span className="status-pill">{item.status.replace('_', ' ')}</span>
              </article>
            )) : <div className="portal-empty">No appointments yet. Choose a department to begin.</div>}
          </div>
        </section>
        <section className="portal-card">
          <header><div><p className="eyebrow">Clinical documents</p><h2>Recent records</h2></div></header>
          <div className="record-list">
            {cases.map((item) => <Link key={`case-${item.id}`} to={`/patient/case-study/${item.id}`} className="record-row record-row--link"><span className="record-icon">CS</span><div><strong>Case study #{item.id}</strong><small>{item.status} · {item.scan_ids.length} linked scans</small><p>{item.diagnosis || item.chief_complaint}</p></div><span>→</span></Link>)}
            {orders.filter((item) => item.scan_id && item.status === 'reviewed').map((item) => {
              const scanId = item.scan_id as string;
              return <article key={`scan-${item.id}`} className="record-row patient-report-record"><span className="record-icon">AI</span><div><strong>{item.scan_type.replace('_', ' ').toUpperCase()} · Final report</strong><small>Doctor approved · ordered by {item.ordering_doctor.full_name}</small><p>{item.clinical_notes}</p></div><div className="patient-report-actions"><Link className="button" to={`/results/${scanId}`}>View report</Link><button className="button button--primary" disabled={downloadingScanId === scanId} onClick={() => void downloadFinalReport(scanId)}>{downloadingScanId === scanId ? 'Downloading…' : 'Download full report'}</button></div></article>;
            })}
            {!cases.length && !orders.some((item) => item.scan_id && item.status === 'reviewed') && <div className="portal-empty">Doctor-approved reports will appear here.</div>}
          </div>
        </section>
      </div>
      <section className="portal-card patient-medicine-card">
        <header><div><p className="eyebrow">Prescription to pharmacy</p><h2>Medicines and bills</h2></div><span className="status-pill">Shared by your medicine shop</span></header>
        <div className="record-list">
          {bills.map((bill) => <Link key={`bill-${bill.id}`} to={`/medicine-bills/${bill.id}`} className="record-row record-row--link"><span className="record-icon">₹</span><div><strong>{bill.invoice_number} · {currency.format(bill.total)}</strong><small>{bill.pharmacy.full_name} · {bill.status}</small><p>{bill.items.map((item) => item.name).join(', ')}</p></div><span>View bill →</span></Link>)}
          {prescriptions.filter((prescription) => !billedPrescriptionIds.has(prescription.id)).map((prescription) => <article key={`rx-${prescription.id}`} className="record-row"><span className="record-icon">Rx</span><div><strong>{prescription.medications.map((item) => item.name).join(', ') || `Prescription #${prescription.id}`}</strong><small>{prescription.doctor.full_name} · sent to medicine shop</small><p>Awaiting availability check and itemized bill.</p></div><span className="status-pill">Awaiting bill</span></article>)}
          {!bills.length && !prescriptions.length && <div className="portal-empty">Doctor prescriptions and medicine-shop bills will appear here.</div>}
        </div>
      </section>
    </div>
  );
}
