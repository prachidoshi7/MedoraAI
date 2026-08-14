import { useState } from 'react';

interface ScanViewerProps {
  scanImageUrl: string;
  heatmapUrl: string;
  scanType: string;
  heatmapTargetLabel?: string;
}

type ViewMode = 'original' | 'heatmap' | 'compare';

export default function ScanViewer({ scanImageUrl, heatmapUrl, scanType, heatmapTargetLabel }: ScanViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('heatmap');
  const scanLabel = ({
    chest_xray: 'Chest X-ray',
    brain_mri: 'Brain MRI',
    lung_ct: 'Lung CT',
    kidney_us: 'Kidney ultrasound',
  } as Record<string, string>)[scanType] || 'Diagnostic image';
  const attributionLabel = scanType === 'chest_xray' ? 'RAD-DINO attribution' : 'Model heatmap';

  return (
    <section className="scan-viewer">
      <header className="scan-viewer__header">
        <div>
          <p className="eyebrow eyebrow--light">Image review</p>
          <h2>{scanLabel}</h2>
        </div>
        <div className="viewer-toggle" role="group" aria-label="Image display mode">
          {(['original', 'heatmap', 'compare'] as ViewMode[]).map((mode) => (
            <button key={mode} className={viewMode === mode ? 'active' : ''} onClick={() => setViewMode(mode)}>
              {mode === 'heatmap' ? attributionLabel : mode[0].toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </header>

      <div className={`scan-canvas scan-canvas--${viewMode}`}>
        {viewMode === 'compare' ? (
          <>
            <figure><img src={scanImageUrl} alt={`Original ${scanLabel}`} /><figcaption>Original</figcaption></figure>
            <figure><img src={heatmapUrl} alt={`${scanLabel} ${attributionLabel}`} /><figcaption>{attributionLabel}</figcaption></figure>
          </>
        ) : (
          <figure>
            <img
              src={viewMode === 'original' ? scanImageUrl : heatmapUrl}
              alt={viewMode === 'original' ? `Original ${scanLabel}` : `${scanLabel} ${attributionLabel}`}
            />
          </figure>
        )}
        <span className="viewer-corner viewer-corner--tl" /><span className="viewer-corner viewer-corner--tr" />
        <span className="viewer-corner viewer-corner--bl" /><span className="viewer-corner viewer-corner--br" />
      </div>

      <footer className="scan-viewer__footer">
        <span><i className="status-pulse" />Study loaded</span>
        {viewMode !== 'original' && (
          <span>{attributionLabel} target · {heatmapTargetLabel || 'primary finding'}</span>
        )}
        <span>For clinician review</span>
      </footer>
    </section>
  );
}
