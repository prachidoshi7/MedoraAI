import { useEffect, useMemo, useState } from 'react';
import {
  getMedicines,
  getPharmacyInventory,
  restockPharmacyInventory,
  uploadPharmacyInventoryCsv,
} from '../api/client';
import MedicineSearchSelect from '../components/MedicineSearchSelect';
import type { Medicine, PharmacyInventoryItem } from '../types';

function expiryLabel(value: string | null) {
  if (!value) return 'Not recorded';
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`));
}

export default function PharmacyInventoryPage() {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [inventory, setInventory] = useState<PharmacyInventoryItem[]>([]);
  const [medicineId, setMedicineId] = useState<number | null>(null);
  const [newStock, setNewStock] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvInputKey, setCsvInputKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = async () => {
    const [catalog, stock] = await Promise.all([getMedicines(), getPharmacyInventory()]);
    setMedicines(catalog);
    setInventory(stock);
    setMedicineId((current) => current || catalog[0]?.id || null);
  };

  useEffect(() => {
    load().catch(() => setError('Could not load store inventory.'));
  }, []);

  const quantities = useMemo(
    () => new Map(inventory.map((item) => [item.medicine.id, item.current_quantity])),
    [inventory],
  );
  const current = medicineId ? quantities.get(medicineId) || 0 : 0;
  const addition = Math.max(0, Number(newStock) || 0);
  const total = current + addition;

  const addStock = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!medicineId || addition < 1 || !expiryDate) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await restockPharmacyInventory(medicineId, addition, expiryDate);
      setMessage(`${result.inventory.medicine.name}: ${result.previous_quantity} + ${result.added_quantity} = ${result.total_quantity} units. Expiry recorded.`);
      setNewStock('');
      setExpiryDate('');
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not add this stock.');
    } finally {
      setBusy(false);
    }
  };

  const importCsv = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!csvFile) return;
    setImporting(true);
    setError('');
    setMessage('');
    try {
      const result = await uploadPharmacyInventoryCsv(csvFile);
      setMessage(`CSV imported: ${result.rows_processed} row(s), ${result.medicines_updated} medicine(s), and ${result.total_units_added} total units added.`);
      setCsvFile(null);
      setCsvInputKey((value) => value + 1);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not import this inventory CSV.');
    } finally {
      setImporting(false);
    }
  };

  const downloadTemplate = () => {
    const templateExpiry = new Date();
    templateExpiry.setFullYear(templateExpiry.getFullYear() + 2);
    const csv = `medicine_name,quantity,expiry_date\nCetirizine 10 mg Tablet,300,${templateExpiry.toISOString().slice(0, 10)}\n`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'medora-inventory-template.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const lowStock = inventory.filter(
    (item) => item.current_quantity > 0 && item.current_quantity <= 10,
  ).length;
  const totalUnits = inventory.reduce((sum, item) => sum + item.current_quantity, 0);

  return (
    <div className="workspace-page portal-page inventory-page">
      <header className="portal-hero">
        <div><p className="eyebrow">Pharmacy administration</p><h1>Store management</h1><p>Search medicines, import received stock from CSV, track expiry dates, and keep billing availability current.</p></div>
        <span className="env-badge"><i /> Live stock control</span>
      </header>
      {(error || message) && <div className={error ? 'form-error' : 'success-banner'}>{error || message}</div>}
      <section className="metric-grid metric-grid--three">
        <article><span>Catalog medicines</span><strong>{medicines.length}</strong><small>Searchable by doctors and pharmacy</small></article>
        <article><span>Total units available</span><strong>{totalUnits}</strong><small>Automatically reduced by bills</small></article>
        <article><span>Low stock</span><strong>{lowStock}</strong><small>10 units or fewer</small></article>
      </section>

      <section className="portal-card inventory-import-card">
        <header><div><p className="eyebrow">Bulk stock intake</p><h2>Import inventory CSV</h2></div><span className="status-pill">Validated before any stock changes</span></header>
        <p className="inventory-import-help">Required columns: <code>medicine_name</code>, <code>quantity</code>, and <code>expiry_date</code>. Medicine names must exactly match the catalog. Dates can use YYYY-MM-DD, DD-MM-YYYY, or DD/MM/YYYY.</p>
        <form className="inventory-import-form" onSubmit={importCsv}>
          <label className="field field--wide"><span>CSV inventory file</span><input key={csvInputKey} required type="file" accept=".csv,text/csv" onChange={(event) => setCsvFile(event.target.files?.[0] || null)} /></label>
          <div className="flow-actions"><button className="button" type="button" onClick={downloadTemplate}>Download CSV template</button><button className="button button--primary" disabled={!csvFile || importing}>{importing ? 'Validating and importing…' : 'Upload & update inventory'}</button></div>
        </form>
      </section>

      <section className="portal-card stock-intake-card">
        <header><div><p className="eyebrow">Single stock intake</p><h2>Add newly received medicine</h2></div><span className="status-pill">Current and total are read-only</span></header>
        <form onSubmit={addStock}>
          <label className="field field--wide"><span>Search medicine</span><MedicineSearchSelect medicines={medicines} value={medicineId} onChange={(medicine) => { setMedicineId(medicine?.id || null); setNewStock(''); }} /></label>
          <div className="stock-intake-grid">
            <label className="field"><span>1. New stock</span><input required min="1" max="1000000" type="number" placeholder="Enter received quantity" value={newStock} onChange={(event) => setNewStock(event.target.value)} /></label>
            <label className="field"><span>2. Expiry date</span><input required min={new Date().toISOString().slice(0, 10)} type="date" value={expiryDate} onChange={(event) => setExpiryDate(event.target.value)} /></label>
            <label className="field field--readonly"><span>3. Current available</span><input readOnly aria-readonly="true" value={current} /></label>
            <label className="field field--readonly"><span>4. Total after add</span><input readOnly aria-readonly="true" value={total} /></label>
          </div>
          <div className="stock-equation"><strong>{addition || 0}</strong><span>new</span><b>＋</b><strong>{current}</strong><span>current</span><b>＝</b><strong>{total}</strong><span>total</span></div>
          <div className="flow-actions"><button className="button button--primary" disabled={busy || addition < 1 || !medicineId || !expiryDate}>{busy ? 'Updating stock…' : 'Add to inventory'}</button></div>
        </form>
      </section>

      <section className="portal-card inventory-list-card">
        <header><div><p className="eyebrow">Current availability</p><h2>Medicine inventory</h2></div><span className="status-pill">{inventory.length} stocked medicines</span></header>
        <div className="inventory-table">
          <div className="inventory-table__head"><span>Medicine</span><span>Category</span><span>Available</span><span>Nearest expiry</span><span>Status</span></div>
          {inventory.map((item) => <article key={item.id}><span><strong>{item.medicine.name}</strong></span><span>{item.medicine.category}</span><span><strong>{item.current_quantity}</strong> units</span><span>{expiryLabel(item.expiry_date)}</span><span className={`stock-state ${item.current_quantity === 0 ? 'is-out' : item.current_quantity <= 10 ? 'is-low' : ''}`}>{item.current_quantity === 0 ? 'Out of stock' : item.current_quantity <= 10 ? 'Low stock' : 'In stock'}</span></article>)}
          {!inventory.length && <div className="portal-empty">No inventory has been set up yet. Import a CSV or add the first medicine above.</div>}
        </div>
      </section>
    </div>
  );
}
