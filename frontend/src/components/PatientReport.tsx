import { useState } from 'react';
import { getPatientSummary } from '../api/client';
import { PATIENT_LANGUAGES } from '../types';

interface PatientReportProps {
  scanId: string;
}

export default function PatientReport({ scanId }: PatientReportProps) {
  const [language, setLanguage] = useState<(typeof PATIENT_LANGUAGES)[number]>('English');
  const [summary, setSummary] = useState('');
  const [summaryLanguage, setSummaryLanguage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError('');
    setCopied(false);
    try {
      const result = await getPatientSummary(scanId, language);
      setSummary(result.summary);
      setSummaryLanguage(result.language);
    } catch {
      setError('The patient explanation could not be prepared. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(summary);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  const share = async () => {
    if (navigator.share) {
      await navigator.share({ title: 'Your scan explanation', text: summary });
    } else {
      await copy();
    }
  };

  return (
    <section className="patient-report">
      <div className="patient-report__intro">
        <p className="eyebrow">Patient communication · 02</p>
        <h2>Explain the finding<br /><em>without the jargon.</em></h2>
        <p>
          Create a calm, plain-language explanation from the clinical report.
          Choose the language the patient is most comfortable reading.
        </p>
        <div className="language-control">
          <label htmlFor="patient-language">Patient language</label>
          <select
            id="patient-language"
            value={language}
            onChange={(event) => setLanguage(event.target.value as typeof language)}
          >
            {PATIENT_LANGUAGES.map((item) => <option key={item}>{item}</option>)}
          </select>
        </div>
        <button className="button button--primary button--wide" onClick={() => void generate()} disabled={loading}>
          <span>{loading ? `Preparing ${language}…` : `Create ${language} explanation`}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
        </button>
        <p className="patient-safety-note">Share only after the clinical report has been reviewed by the treating doctor.</p>
      </div>

      <div className={`patient-paper${summary ? ' has-summary' : ''}`} id="patient-summary-print">
        {!summary && !loading && (
          <div className="patient-paper__empty">
            <span>अ · A · அ</span>
            <h3>A clearer explanation will appear here.</h3>
            <p>No confidence scores, technical model terms, or radiology jargon.</p>
          </div>
        )}
        {loading && (
          <div className="patient-paper__loading"><i /><p>Writing in {language}…</p></div>
        )}
        {summary && !loading && (
          <>
            <header>
              <div><p className="eyebrow">For the patient</p><h3>Your scan, in simple terms.</h3></div>
              <span>{summaryLanguage}</span>
            </header>
            <div className="patient-summary-text" lang={summaryLanguage === 'English' ? 'en' : undefined}>
              {summary.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
            </div>
            <footer>
              <button className="text-button" onClick={() => void copy()}>{copied ? 'Copied' : 'Copy text'}</button>
              <button className="text-button" onClick={() => window.print()}>Print</button>
              <button className="text-button" onClick={() => void share()}>Share</button>
            </footer>
          </>
        )}
        {error && <div className="form-error" role="alert">{error}</div>}
      </div>
    </section>
  );
}
