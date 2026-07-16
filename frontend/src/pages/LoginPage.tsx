import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) return <Navigate to="/upload" replace />;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError('');
    try {
      await login({ username: username.trim(), password });
      navigate('/upload');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <section className="login-editorial" aria-labelledby="login-wordmark">
        <div className="login-brand">
          <span className="brand-mark brand-mark--light" aria-hidden="true"><i /><i /></span>
          <span>MEDORA / CLINICAL IMAGING</span>
        </div>
        <div className="login-hero-copy">
          <p className="eyebrow eyebrow--light">Built for clinical pace</p>
          <h1 id="login-wordmark">Every scan.<br /><em>More clarity.</em></h1>
          <p>
            A focused workspace for image review, structured reporting, and clearer
            conversations with patients.
          </p>
        </div>
        <div className="login-index" aria-hidden="true">
          <span>01</span><span>Review</span><span>Report</span><span>Explain</span>
        </div>
      </section>

      <section className="login-form-panel">
        <div className="login-form-wrap">
          <p className="eyebrow">Secure clinician access</p>
          <h2>Welcome back.</h2>
          <p className="form-intro">Enter your credentials to open the diagnostic workspace.</p>

          <form onSubmit={handleSubmit} className="login-form">
            <label>
              <span>Username</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Your username"
                autoComplete="username"
                autoFocus
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your password"
                autoComplete="current-password"
              />
            </label>

            {error && <div className="form-error" role="alert">{error}</div>}

            <button className="button button--primary button--wide" type="submit" disabled={loading}>
              <span>{loading ? 'Opening workspace…' : 'Enter workspace'}</span>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
            </button>
          </form>

          <div className="demo-note">
            <span>Demo access</span>
            <code>demo</code><span>/</span><code>demo123</code>
          </div>
          <p className="access-note">For authorized medical professionals only.</p>
        </div>
        <p className="login-footer">Medora Clinical Workspace · {new Date().getFullYear()}</p>
      </section>
    </div>
  );
}
