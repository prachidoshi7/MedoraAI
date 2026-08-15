import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import BrandLogo from '../components/BrandLogo';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { isAuthenticated, login, user } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated && user) {
    const home = user.role === 'patient'
      ? '/patient/dashboard'
      : user.role === 'lab_tech'
        ? '/lab/dashboard'
        : user.role === 'pharmacy'
          ? '/pharmacy/dashboard'
          : user.role === 'admin'
            ? '/admin/doctors'
            : '/doctor/dashboard';
    return <Navigate to={home} replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setLoading(true);
    setError('');
    try {
      await login({ username: username.trim(), password });
      navigate('/');
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
          <BrandLogo className="medora-logo--auth" variant="login" />
          <span>Clinical imaging</span>
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
          <p className="eyebrow">Secure hospital access</p>
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

          <div className="demo-credentials">
            <span><small>Patient</small><code>patient / patient123</code></span>
            <span><small>Doctor</small><code>dr.sharma / doctor123</code></span>
            <span><small>Lab</small><code>lab.tech / lab123</code></span>
            <span><small>Pharmacy</small><code>pharmacy / pharmacy123</code></span>
            <span><small>Admin</small><code>admin / admin123</code></span>
          </div>
          <p className="auth-switch">New patient? <a href="/register">Create an account</a></p>
        </div>
        <p className="login-footer">Medora Clinical Workspace · {new Date().getFullYear()}</p>
      </section>
    </div>
  );
}
