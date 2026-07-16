import type { ClassificationDetail } from '../types';

interface ResultPanelProps {
  classification: ClassificationDetail;
  scanType: string;
  analysisTimeMs: number;
}

export default function ResultPanel({ classification, scanType, analysisTimeMs }: ResultPanelProps) {
  const { all_scores, confidence, severity, top_label } = classification;
  const scores = Object.entries(all_scores).sort(([, a], [, b]) => b - a);
  const modelName = scanType === 'brain_mri' ? 'EfficientNetB3' : 'EfficientNet-B4';

  return (
    <aside className="result-panel">
      <div className="finding-card">
        <div className="finding-card__top">
          <p className="eyebrow">Primary finding</p>
          <span className={`severity-badge severity-badge--${severity.toLowerCase()}`}>{severity}</span>
        </div>
        <h2>{top_label}</h2>
        <div className="confidence-row">
          <span>Model match</span><strong>{(confidence * 100).toFixed(1)}%</strong>
        </div>
        <div className="confidence-track"><span style={{ width: `${Math.min(confidence * 100, 100)}%` }} /></div>
        {classification.is_low_confidence && (
          <p className="confidence-warning">Low match strength. Interpret with added caution.</p>
        )}
      </div>

      <div className="scores-card">
        <div className="card-title-row"><p className="eyebrow">Class comparison</p><span>{scores.length} classes</span></div>
        <div className="score-list">
          {scores.map(([label, score]) => (
            <div className={label === top_label ? 'is-primary' : ''} key={label}>
              <span>{label}</span>
              <i><b style={{ width: `${Math.min(score * 100, 100)}%` }} /></i>
              <strong>{(score * 100).toFixed(1)}%</strong>
            </div>
          ))}
        </div>
      </div>

      <dl className="model-meta">
        <div><dt>Model</dt><dd>{modelName}</dd></div>
        <div><dt>Processing</dt><dd>{analysisTimeMs ? `${(analysisTimeMs / 1000).toFixed(1)} sec` : 'Archived'}</dd></div>
        <div><dt>Status</dt><dd><i className="status-pulse" />Review ready</dd></div>
      </dl>
    </aside>
  );
}
