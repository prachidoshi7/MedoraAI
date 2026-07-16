import { useState } from 'react';

interface ScanViewerProps {
  scanImageUrl: string;
  heatmapUrl: string;
  scanType: string;
  heatmapTargetLabel?: string;
}

type ViewMode = 'original' | 'attention' | 'compare';

export default function ScanViewer({ scanImageUrl, heatmapUrl, scanType, heatmapTargetLabel }: ScanViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('attention');
  const scanLabel = scanType === 'brain_mri' ? 'Brain MRI' : 'Chest X-ray';

  return (
    <section className="scan-viewer">
      <header className="scan-viewer__header">
        <div>
          <p className="eyebrow eyebrow--light">Image review</p>
          <h2>{scanLabel}</h2>
        </div>
        <div className="viewer-toggle" role="group" aria-label="Image display mode">
          {(['original', 'attention', 'compare'] as ViewMode[]).map((mode) => (
            <button key={mode} className={viewMode === mode ? 'active' : ''} onClick={() => setViewMode(mode)}>
              {mode === 'attention' ? 'Attention map' : mode[0].toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </header>

      <div className={`scan-canvas scan-canvas--${viewMode}`}>
        {viewMode === 'compare' ? (
          <>
            <figure><img src={scanImageUrl} alt={`Original ${scanLabel}`} /><figcaption>Original</figcaption></figure>
            <figure><img src={heatmapUrl} alt={`${scanLabel} attention map`} /><figcaption>Model attention</figcaption></figure>
          </>
        ) : (
          <figure>
            <img
              src={viewMode === 'original' ? scanImageUrl : heatmapUrl}
              alt={viewMode === 'original' ? `Original ${scanLabel}` : `${scanLabel} attention map`}
            />
          </figure>
        )}
        <span className="viewer-corner viewer-corner--tl" /><span className="viewer-corner viewer-corner--tr" />
        <span className="viewer-corner viewer-corner--bl" /><span className="viewer-corner viewer-corner--br" />
      </div>

      <footer className="scan-viewer__footer">
        <span><i className="status-pulse" />Study loaded</span>
        {viewMode !== 'original' && (
          <span>Attention target · {heatmapTargetLabel || 'primary finding'}</span>
        )}
        <span>For clinician review</span>
      </footer>
    </section>
  );
}
