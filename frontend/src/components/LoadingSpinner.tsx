import type { AnalysisStep } from '../hooks/useScan';

interface LoadingSpinnerProps {
  step: AnalysisStep;
  stepLabel: string;
}

const steps: Array<{ key: AnalysisStep; label: string }> = [
  { key: 'uploading', label: 'Upload' },
  { key: 'classifying', label: 'Review' },
  { key: 'generating_heatmap', label: 'Map' },
  { key: 'generating_report', label: 'Report' },
  { key: 'complete', label: 'Ready' },
];

export default function LoadingSpinner({ step, stepLabel }: LoadingSpinnerProps) {
  const current = steps.findIndex((item) => item.key === step);

  return (
    <div className="processing-overlay" role="status" aria-live="polite">
      <div className="processing-card">
        <div className="processing-orbit" aria-hidden="true"><span /><i /></div>
        <p className="eyebrow">Preparing study</p>
        <h2>{stepLabel}</h2>
        <p className="processing-note">Keep this window open. Your report will appear when the review is ready.</p>
        <ol className="processing-steps">
          {steps.map((item, index) => (
            <li key={item.key} className={index < current ? 'done' : index === current ? 'active' : ''}>
              <span>{index < current ? '✓' : String(index + 1).padStart(2, '0')}</span>
              {item.label}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
