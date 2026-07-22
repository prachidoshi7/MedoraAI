import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import UploadZone from '../components/UploadZone';
import { useScanAnalysis } from '../hooks/useScan';
import { SCAN_TYPES } from '../types';
import type { ScanType } from '../types';

const scanLineIcons: Record<ScanType, React.ReactNode> = {
  chest_xray: (
    <svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 6v16M14 12c-5 3-7 9-7 15 0 4 2 6 6 6h2c2 0 3-2 3-4V18m8-6c5 3 7 9 7 15 0 4-2 6-6 6h-2c-2 0-3-2-3-4V18" /></svg>
  ),
  brain_mri: (
    <svg viewBox="0 0 40 40" aria-hidden="true"><path d="M18 7a6 6 0 0 0-10 5c-3 1-4 5-2 8-2 3 0 7 3 8 0 4 4 6 7 4 2 3 6 2 7-1V10c-1-3-3-4-5-3Zm5 5c3-4 9-2 9 3 4 2 4 8 1 10 1 4-3 8-7 6l-3 2" /></svg>
  ),
};

export default function UploadPage() {
  const [scanType, setScanType] = useState<ScanType | null>(null);
  const { analyze, error, isLoading, step, stepLabel } = useScanAnalysis();
  const navigate = useNavigate();

  const handleAnalyze = async (file: File) => {
    if (!scanType) return;
    try {
      const result = await analyze(file, scanType);
      window.setTimeout(() => navigate(`/results/${result.scan_id}`), 500);
    } catch {
      // The hook exposes a user-safe error below.
    }
  };

  return (
    <div className="workspace-page upload-page">
      {isLoading && <LoadingSpinner step={step} stepLabel={stepLabel} />}

      <header className="topbar upload-hero">
        <div>
          <p className="eyebrow">Diagnostic console</p>
          <h1>New diagnostic study</h1>
          <p>Choose a modality and upload a medical image to begin analysis.</p>
        </div>
        <div className="env-badge"><i /> Inference engine connected</div>
      </header>

      <div className="upload-workspace">
        <section className="workflow-panel fade-stage">
          <div className="workflow-step">
            <div className="step-heading">
              <span>01</span>
              <div><p className="eyebrow">Study type</p><h2>What are you reviewing?</h2><small>Select the model that matches this study.</small></div>
            </div>
            <div className="scan-type-grid" role="radiogroup" aria-label="Study type">
              {SCAN_TYPES.map((type) => {
                const selected = scanType === type.id;
                return (
                  <button
                    key={type.id}
                    className={`scan-type-option${selected ? ' is-selected' : ''}`}
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setScanType(type.id)}
                  >
                    <span className="scan-type-icon">{scanLineIcons[type.id]}</span>
                    <span className="scan-type-copy">
                      <small>{type.id === 'chest_xray' ? 'DIGITAL RADIOGRAPHY' : 'MAGNETIC RESONANCE'}</small>
                      <strong>{type.label}</strong>
                      <span>{type.description}</span>
                    </span>
                    <span className="scan-radio" aria-hidden="true" />
                    <span className="model-chip">Model · {type.model}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className={`workflow-step upload-step${scanType ? '' : ' is-locked'}`}>
            <div className="step-heading">
              <span>02</span>
              <div>
                <p className="eyebrow">Medical image</p>
                <h2>{scanType ? 'Add the scan.' : 'Choose a study type first.'}</h2>
              </div>
            </div>
            {scanType && <UploadZone onAnalyze={handleAnalyze} isLoading={isLoading} scanType={scanType} />}
          </div>

          {error && <div className="form-error workflow-error" role="alert">{error}</div>}
          <div className="workflow-footnote">
            <span>◎ Explainable AI</span><span>⌁ Editable report</span><span>◈ Patient summary</span>
          </div>
        </section>
      </div>
    </div>
  );
}
