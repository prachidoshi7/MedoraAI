import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getPharmacyBill, markPharmacyBillDispensed } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { PharmacyBill } from '../types';
import BrandLogo from '../components/BrandLogo';

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
});

function dateLabel(value: string | null) {
  return value
    ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(value))
    : 'Not available';
}

export default function PharmacyBillPage() {
  const { billId } = useParams();
  const { user } = useAuth();
  const [bill, setBill] = useState<PharmacyBill | null>(null);
  const [error, setError] = useState('');
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    getPharmacyBill(Number(billId))
      .then(setBill)
      .catch((err) => setError(err.response?.data?.detail || 'Could not load this medicine bill.'));
  }, [billId]);

  const dispense = async () => {
    if (!bill) return;
    setUpdating(true);
    setError('');
    try {
      setBill(await markPharmacyBillDispensed(bill.id));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not update the bill.');
    } finally {
      setUpdating(false);
    }
  };

  const backTo = user?.role === 'pharmacy'
    ? '/pharmacy/dashboard'
    : user?.role === 'admin'
      ? '/doctor/dashboard'
      : '/patient/dashboard';
  if (error && !bill) return <div className="workspace-page empty-state-page"><div className="empty-state-card"><span>!</span><h1>Bill unavailable</h1><p>{error}</p><Link className="button" to={backTo}>Back to dashboard</Link></div></div>;
  if (!bill) return <div className="workspace-page"><div className="portal-empty">Loading medicine bill…</div></div>;

  return (
    <div className="workspace-page medicine-bill-page">
      <header className="bill-page-actions">
        <div><p className="eyebrow">Patient medicine bill</p><h1>{bill.invoice_number}</h1></div>
        <div><Link className="button" to={backTo}>← Dashboard</Link><button className="button" onClick={() => window.print()}>Print / save PDF</button>{user?.role === 'pharmacy' && bill.status === 'billed' && <button className="button button--primary" disabled={updating} onClick={dispense}>{updating ? 'Updating…' : 'Mark dispensed'}</button>}</div>
      </header>
      {error && <div className="form-error">{error}</div>}

      <article className="medicine-invoice">
        <header>
          <div className="invoice-brand"><BrandLogo className="medora-logo--invoice" /><div><strong>{bill.pharmacy.full_name}</strong><small>Authorized medicine shop</small></div></div>
          <div className="invoice-number"><span>Tax invoice</span><strong>{bill.invoice_number}</strong><small>{dateLabel(bill.created_at)}</small></div>
        </header>

        <section className="invoice-parties">
          <div><span>Billed to</span><strong>{bill.patient.full_name}</strong><small>{bill.patient.phone || bill.patient.email || `Patient ID ${bill.patient.id}`}</small></div>
          <div><span>Prescribed by</span><strong>{bill.prescription.doctor.full_name}</strong><small>{bill.prescription.doctor.specialization || 'Medora clinician'} · Rx #{bill.prescription.id}</small></div>
          <div><span>Medicine shop</span><strong>{bill.pharmacy.full_name}</strong><small>{bill.pharmacy.specialization || 'Hospital pharmacy'}</small><small>{[bill.pharmacy.phone, bill.pharmacy.email].filter(Boolean).join(' · ')}</small></div>
        </section>

        <section className="invoice-prescription-note"><span>Diagnosis / prescription note</span><p>{bill.prescription.diagnosis || 'Not specified'}{bill.prescription.instructions ? ` — ${bill.prescription.instructions}` : ''}</p></section>

        <div className="invoice-table">
          <div className="invoice-table__head"><span>#</span><span>Medicine</span><span>Prescribed use</span><span>Qty</span><span>Unit price</span><span>Amount</span></div>
          {bill.items.map((item, index) => (
            <article key={`${item.medication_index}-${item.name}`}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <span><strong>{item.name}</strong><small>{item.dosage || 'As directed'}</small></span>
              <span><strong>{item.frequency || 'As directed'}</strong><small>{item.duration}</small></span>
              <span>{item.quantity}</span>
              <span>{currency.format(item.unit_price)}</span>
              <span><strong>{currency.format(item.line_total)}</strong></span>
            </article>
          ))}
        </div>

        <section className="invoice-footer">
          <div><span>Pharmacy note</span><p>{bill.notes || 'Medicines supplied according to the doctor-issued prescription.'}</p><div className={`invoice-status invoice-status--${bill.status}`}><i /> {bill.status === 'dispensed' ? `Dispensed ${dateLabel(bill.dispensed_at)}` : 'Bill generated · Awaiting dispensing'}</div></div>
          <dl>
            <div><dt>Subtotal</dt><dd>{currency.format(bill.subtotal)}</dd></div>
            <div><dt>Tax / GST ({bill.tax_percent.toFixed(2)}%)</dt><dd>{currency.format(bill.tax_amount)}</dd></div>
            <div><dt>Total payable</dt><dd>{currency.format(bill.total)}</dd></div>
          </dl>
        </section>
        <footer><span>Generated securely through MedoraAI</span><span>Keep this bill with your prescription record.</span></footer>
      </article>
    </div>
  );
}
