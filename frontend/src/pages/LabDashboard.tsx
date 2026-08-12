import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { claimDiagnosticOrder, getPendingDiagnosticOrders } from '../api/client';
import type { DiagnosticOrder } from '../types';

export default function LabDashboard() {
  const [orders, setOrders] = useState<DiagnosticOrder[]>([]);
  const [error, setError] = useState('');
  const load = () => getPendingDiagnosticOrders().then(setOrders).catch((err) => setError(err.response?.data?.detail || 'Could not load the lab queue.'));
  useEffect(() => { void load(); }, []);
  const claim = async (id: number) => { try { await claimDiagnosticOrder(id); load(); } catch (err: any) { setError(err.response?.data?.detail || 'Could not claim this order.'); } };
  return (
    <div className="workspace-page portal-page">
      <header className="portal-hero"><div><p className="eyebrow">Radiology operations</p><h1>Diagnostic lab queue</h1><p>Claim ordered studies, upload source imaging, and run explainable AI analysis.</p></div><span className="env-badge"><i /> 4 models online</span></header>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid metric-grid--three"><article><span>Unassigned</span><strong>{orders.filter((item) => item.status === 'ordered').length}</strong><small>Ready to claim</small></article><article><span>In progress</span><strong>{orders.filter((item) => ['assigned', 'in_progress'].includes(item.status)).length}</strong><small>Active studies</small></article><article><span>Urgent / STAT</span><strong>{orders.filter((item) => item.priority !== 'routine').length}</strong><small>Prioritize these orders</small></article></section>
      <section className="portal-card"><header><div><p className="eyebrow">Live worklist</p><h2>Pending diagnostic orders</h2></div></header><div className="lab-table"><div className="lab-table__head"><span>Priority</span><span>Patient / study</span><span>Ordering doctor</span><span>Status</span><span>Action</span></div>{orders.map((item) => <article key={item.id}><span className={`priority-tag priority-${item.priority}`}>{item.priority}</span><span><strong>{item.patient.full_name}</strong><small>{item.scan_type.replace('_', ' ')} · Order #{item.id}</small></span><span><strong>{item.ordering_doctor.full_name}</strong><small>{item.clinical_notes}</small></span><span className="status-pill">{item.status}</span><span>{item.status === 'ordered' ? <button className="button" onClick={() => claim(item.id)}>Claim</button> : <Link className="button button--primary" to={`/lab/upload/${item.id}`} state={{ order: item }}>Upload scan</Link>}</span></article>)}{!orders.length && <div className="portal-empty">The lab queue is clear.</div>}</div></section>
    </div>
  );
}
