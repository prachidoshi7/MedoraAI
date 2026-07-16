import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  clearHistory,
  deleteSelectedScans,
  getHistory,
} from '../api/client';
import type { HistoryScan } from '../types';

interface HistorySidebarProps {
  currentScanId?: string;
}

const formatWhen = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recent';
  return new Intl.DateTimeFormat('en', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

export default function HistorySidebar({ currentScanId }: HistorySidebarProps) {
  const [scans, setScans] = useState<HistoryScan[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const history = await getHistory();
      setScans(history.scans);
      setTotal(history.total);
      setError('');
    } catch {
      setError('Recent studies could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load, currentScanId]);

  const finishDelete = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await operation();
      setSelected(new Set());
      await load();
    } catch {
      setError('The selected studies could not be removed.');
    } finally {
      setBusy(false);
    }
  };

  const toggle = (scanId: string) => {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(scanId)) next.delete(scanId); else next.add(scanId);
      return next;
    });
  };

  return (
    <section className="history-panel">
      <header className="history-header">
        <div>
          <p className="eyebrow">Study archive</p>
          <h2>Recent cases <sup>{total}</sup></h2>
        </div>
        {scans.length > 0 && (
          <button className="text-button" onClick={() => { setManaging(!managing); setSelected(new Set()); }}>
            {managing ? 'Done' : 'Manage'}
          </button>
        )}
      </header>

      {loading ? (
        <div className="history-loading"><span /><span /><span /></div>
      ) : scans.length === 0 ? (
        <div className="history-empty">
          <span>—</span>
          <p>No studies yet.</p>
          <small>Your completed reviews will appear here.</small>
        </div>
      ) : (
        <div className="history-list">
          {scans.slice(0, 6).map((scan, index) => {
            const isCurrent = scan.scan_id === currentScanId;
            const checked = selected.has(scan.scan_id);
            return (
              <article
                key={scan.scan_id}
                className={`history-item${isCurrent ? ' is-current' : ''}`}
                onClick={() => managing ? toggle(scan.scan_id) : navigate(`/results/${scan.scan_id}`)}
              >
                {managing && <span className={`history-check${checked ? ' is-checked' : ''}`}>{checked ? '✓' : ''}</span>}
                <span className="history-index">{String(index + 1).padStart(2, '0')}</span>
                <div className="history-copy">
                  <small>{scan.scan_type === 'brain_mri' ? 'BRAIN MRI' : 'CHEST X-RAY'} · {formatWhen(scan.uploaded_at)}</small>
                  <strong>{scan.top_label || 'Awaiting review'}</strong>
                  <span>{scan.confidence ? `${(scan.confidence * 100).toFixed(0)}% match` : scan.status}</span>
                </div>
                {!managing && <span className={`severity-dot severity-dot--${scan.severity?.toLowerCase()}`} title={scan.severity} />}
              </article>
            );
          })}
        </div>
      )}

      {managing && scans.length > 0 && (
        <div className="history-actions">
          <button
            className="button button--outline"
            disabled={!selected.size || busy}
            onClick={() => void finishDelete(() => deleteSelectedScans([...selected]))}
          >
            Remove selected ({selected.size})
          </button>
          <button
            className="text-button text-button--danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm('Remove every study from this account?')) void finishDelete(clearHistory);
            }}
          >
            Clear all
          </button>
        </div>
      )}

      {error && <p className="history-error">{error}</p>}
    </section>
  );
}
