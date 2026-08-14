import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createPharmacyBill, getPharmacyInventory, getPharmacyQueue } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { PharmacyInventoryItem, PharmacyQueueItem } from '../types';

interface CartRow {
  medicationIndex: number;
  quantity: number;
  unitPrice: string;
}

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
});

function dateLabel(value: string | null) {
  return value
    ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
    : 'Date unavailable';
}

export default function PharmacyDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [queue, setQueue] = useState<PharmacyQueueItem[]>([]);
  const [inventory, setInventory] = useState<PharmacyInventoryItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [cart, setCart] = useState<CartRow[]>([]);
  const [taxPercent, setTaxPercent] = useState('18');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([getPharmacyQueue(), getPharmacyInventory()])
      .then(([items, stock]) => {
        setQueue(items);
        setInventory(stock);
        setSelectedId(items.find((item) => !item.bill)?.prescription.id ?? items[0]?.prescription.id ?? null);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load prescriptions.'))
      .finally(() => setLoading(false));
  }, []);

  const selected = queue.find((item) => item.prescription.id === selectedId) ?? null;
  const availableByMedicine = useMemo(() => new Map(inventory.map((item) => [item.medicine.id, item.current_quantity])), [inventory]);
  const subtotal = useMemo(
    () => cart.reduce((sum, row) => sum + row.quantity * (Number(row.unitPrice) || 0), 0),
    [cart],
  );
  const taxAmount = subtotal * (Number(taxPercent) || 0) / 100;

  const choosePrescription = (id: number) => {
    setSelectedId(id);
    setCart([]);
    setTaxPercent('18');
    setNotes('');
    setError('');
  };

  const addToCart = (medicationIndex: number) => {
    if (cart.some((row) => row.medicationIndex === medicationIndex)) return;
    const medicineId = selected?.prescription.medications[medicationIndex]?.medicine_id;
    if (!medicineId || (availableByMedicine.get(medicineId) || 0) < 1) return;
    const suggested = selected?.prescription.medications[medicationIndex]?.suggested_quantity || 1;
    setCart([...cart, { medicationIndex, quantity: suggested, unitPrice: '' }]);
  };

  const updateCart = (medicationIndex: number, update: Partial<CartRow>) => {
    setCart(cart.map((row) => row.medicationIndex === medicationIndex ? { ...row, ...update } : row));
  };

  const generateBill = async () => {
    if (!selected || !cart.length) return;
    if (cart.some((row) => row.quantity < 1 || row.unitPrice === '' || Number(row.unitPrice) < 0)) {
      setError('Enter a valid quantity and unit price for every cart item.');
      return;
    }
    const insufficient = cart.find((row) => {
      const medicineId = selected.prescription.medications[row.medicationIndex]?.medicine_id;
      return !medicineId || row.quantity > (availableByMedicine.get(medicineId) || 0);
    });
    if (insufficient) { setError('One or more quantities exceed the current medicine stock.'); return; }
    setSubmitting(true);
    setError('');
    try {
      const bill = await createPharmacyBill({
        prescription_id: selected.prescription.id,
        items: cart.map((row) => ({
          medication_index: row.medicationIndex,
          quantity: row.quantity,
          unit_price: Number(row.unitPrice),
        })),
        tax_percent: Number(taxPercent) || 0,
        notes,
      });
      navigate(`/medicine-bills/${bill.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not generate this bill.');
    } finally {
      setSubmitting(false);
    }
  };

  const pendingCount = queue.filter((item) => !item.bill).length;
  const billedToday = queue.filter((item) => item.bill && item.bill.created_at && new Date(item.bill.created_at).toDateString() === new Date().toDateString());

  return (
    <div className="workspace-page portal-page pharmacy-page">
      <header className="portal-hero">
        <div><p className="eyebrow">Medicine fulfillment · Pharmacy dashboard</p><h1>{user?.full_name}</h1><p>Review doctor-issued prescriptions, add available medicines to the cart, and send an itemized bill to the patient.</p></div>
        <div className="hero-action-stack"><span className="env-badge"><i /> Prescription feed live</span><Link className="button" to="/pharmacy/inventory">Open store management</Link></div>
      </header>
      {error && <div className="form-error">{error}</div>}
      <section className="metric-grid metric-grid--three">
        <article><span>Prescriptions received</span><strong>{queue.length}</strong><small>All doctor-issued requests</small></article>
        <article><span>Awaiting billing</span><strong>{pendingCount}</strong><small>Ready for medicine selection</small></article>
        <article><span>Billed today</span><strong>{billedToday.length}</strong><small>{currency.format(billedToday.reduce((sum, item) => sum + (item.bill?.total || 0), 0))} generated</small></article>
      </section>

      <div className="pharmacy-layout">
        <section className="portal-card pharmacy-queue">
          <header><div><p className="eyebrow">Incoming queue</p><h2>Doctor prescriptions</h2></div><span className="status-pill">{pendingCount} pending</span></header>
          <div className="pharmacy-queue__list">
            {queue.map((item) => (
              <article className={item.prescription.id === selectedId ? 'is-selected' : ''} key={item.prescription.id}>
                <button type="button" onClick={() => choosePrescription(item.prescription.id)}>
                  <span className={`status-dot ${item.bill ? 'status-completed' : 'status-requested'}`} />
                  <span><strong>{item.prescription.patient.full_name}</strong><small>Rx #{item.prescription.id} · {dateLabel(item.prescription.created_at)}</small><em>{item.prescription.medications.length} medicine{item.prescription.medications.length === 1 ? '' : 's'} · {item.prescription.doctor.full_name}</em></span>
                  <span className="status-pill">{item.bill ? item.bill.status : 'new'}</span>
                </button>
              </article>
            ))}
            {!loading && !queue.length && <div className="portal-empty">No prescriptions have arrived yet.</div>}
            {loading && <div className="portal-empty">Loading prescription queue…</div>}
          </div>
        </section>

        <section className="portal-card pharmacy-workspace">
          {!selected ? <div className="portal-empty">Select a prescription to prepare a medicine bill.</div> : selected.bill ? (
            <div className="bill-complete-card">
              <span className="record-icon">✓</span>
              <p className="eyebrow">Bill already generated</p>
              <h2>{selected.bill.invoice_number}</h2>
              <p>{selected.prescription.patient.full_name} can now see this bill and the medicine-shop details in their dashboard.</p>
              <strong>{currency.format(selected.bill.total)}</strong>
              <Link className="button button--primary" to={`/medicine-bills/${selected.bill.id}`}>View itemized bill</Link>
            </div>
          ) : (
            <>
              <header><div><p className="eyebrow">Prescription #{selected.prescription.id}</p><h2>{selected.prescription.patient.full_name}</h2></div><span className="status-pill">Prescribed by {selected.prescription.doctor.full_name}</span></header>
              <div className="prescription-summary"><strong>{selected.prescription.diagnosis || 'Prescription'}</strong><p>{selected.prescription.instructions || 'No additional instructions.'}</p></div>
              <div className="medicine-picker">
                <div className="section-label"><span>Prescribed medicine</span><span>Action</span></div>
                {selected.prescription.medications.map((medicine, index) => {
                  const inCart = cart.some((row) => row.medicationIndex === index);
                  const available = medicine.medicine_id ? (availableByMedicine.get(medicine.medicine_id) || 0) : 0;
                  return (
                    <article key={`${medicine.name}-${index}`}>
                      <div><strong>{medicine.name}</strong><small>{[medicine.dosage, medicine.frequency, medicine.duration].filter(Boolean).join(' · ')}</small><em className={available > 0 ? 'medicine-stock' : 'medicine-stock is-out'}>{available > 0 ? `${available} units available` : 'Out of stock'}</em></div>
                      <button className={inCart ? 'button' : 'button button--primary'} disabled={inCart || available < 1} onClick={() => addToCart(index)}>{inCart ? 'Added ✓' : available < 1 ? 'Out of stock' : '＋ Add to cart'}</button>
                    </article>
                  );
                })}
                {!selected.prescription.medications.length && <div className="portal-empty">This prescription has no medicine lines.</div>}
              </div>

              <div className="pharmacy-cart">
                <div className="section-label"><span>Billing cart</span><span>{cart.length} item{cart.length === 1 ? '' : 's'}</span></div>
                {cart.map((row) => {
                  const medicine = selected.prescription.medications[row.medicationIndex];
                  const available = medicine.medicine_id ? (availableByMedicine.get(medicine.medicine_id) || 0) : 0;
                  return (
                    <article key={row.medicationIndex}>
                      <div><strong>{medicine.name}</strong><small>{medicine.dosage} · {medicine.duration}</small><em className="cart-quantity-basis">Suggested {medicine.suggested_quantity || 1} unit(s): {medicine.quantity_basis || 'pharmacist review'}. Editable before billing.</em>{row.quantity > available && <em className="medicine-stock is-out">Suggested quantity exceeds the {available} units in stock.</em>}</div>
                      <label><span>Qty (max {available})</span><input aria-label={`${medicine.name} quantity`} min="1" max={available} type="number" value={row.quantity} onChange={(event) => updateCart(row.medicationIndex, { quantity: Math.min(available, Math.max(1, Number(event.target.value))) })} /></label>
                      <label><span>Unit price ₹</span><input aria-label={`${medicine.name} unit price`} min="0" step="0.01" type="number" placeholder="0.00" value={row.unitPrice} onChange={(event) => updateCart(row.medicationIndex, { unitPrice: event.target.value })} /></label>
                      <strong>{currency.format(row.quantity * (Number(row.unitPrice) || 0))}</strong>
                      <button className="text-button text-button--danger" onClick={() => setCart(cart.filter((item) => item.medicationIndex !== row.medicationIndex))}>Remove</button>
                    </article>
                  );
                })}
                {!cart.length && <div className="portal-empty">Add available prescribed medicines to start the bill.</div>}
              </div>

              <div className="billing-controls">
                <label className="field"><span>Tax / GST (%)</span><input min="0" max="100" step="0.01" type="number" value={taxPercent} onChange={(event) => setTaxPercent(event.target.value)} /></label>
                <label className="field"><span>Shop note</span><input placeholder="Batch, availability, or pickup note" value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
                <div className="bill-totals"><span>Subtotal <strong>{currency.format(subtotal)}</strong></span><span>Tax <strong>{currency.format(taxAmount)}</strong></span><span>Total <strong>{currency.format(subtotal + taxAmount)}</strong></span></div>
              </div>
              <div className="flow-actions"><button className="button button--primary" disabled={!cart.length || submitting} onClick={generateBill}>{submitting ? 'Generating bill…' : 'Generate & send bill →'}</button></div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
