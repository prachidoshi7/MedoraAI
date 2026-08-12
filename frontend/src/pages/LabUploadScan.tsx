import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import UploadZone from '../components/UploadZone';
import { getPendingDiagnosticOrders } from '../api/client';
import { useScanAnalysis } from '../hooks/useScan';
import type { DiagnosticOrder } from '../types';

export default function LabUploadScan() {
  const { orderId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [order, setOrder] = useState<DiagnosticOrder | null>((location.state as { order?: DiagnosticOrder } | null)?.order || null);
  const { analyze, error, isLoading, step, stepLabel } = useScanAnalysis();
  const id = Number(orderId);
  useEffect(() => { if (!order) getPendingDiagnosticOrders().then((items) => setOrder(items.find((item) => item.id === id) || null)); }, [id, order]);
  const handle = async (file: File) => { if (!order) return; try { const result = await analyze(file, order.scan_type, order.id); navigate(`/lab/results/${result.scan_id}`); } catch { /* displayed by hook */ } };
  if (!order) return <div className="workspace-page portal-page">Loading order context…</div>;
  return (
    <div className="workspace-page portal-page narrow-page">
      {isLoading && <LoadingSpinner step={step} stepLabel={stepLabel} />}
      <header className="portal-hero"><div><p className="eyebrow">Order #{order.id} · {order.priority}</p><h1>Upload {order.scan_type.replace('_', ' ')}.</h1><p>{order.patient.full_name} · Ordered by {order.ordering_doctor.full_name}</p></div></header>
      <section className="portal-card upload-order-card"><div className="order-context"><div><span>Clinical indication</span><strong>{order.clinical_notes || 'Not supplied'}</strong></div><div><span>Study</span><strong>{order.scan_type.replace('_', ' ')}</strong></div><div><span>Patient</span><strong>MED-{String(order.patient.id).padStart(4, '0')}</strong></div></div><UploadZone onAnalyze={handle} isLoading={isLoading} scanType={order.scan_type} />{error && <div className="form-error">{error}</div>}</section>
    </div>
  );
}
