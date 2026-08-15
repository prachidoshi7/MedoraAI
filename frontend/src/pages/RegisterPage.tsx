import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import BrandLogo from '../components/BrandLogo';

export default function RegisterPage() {
  const { isAuthenticated, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', username: '', email: '', phone: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await register(form);
      navigate('/patient/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create your account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <section className="login-editorial">
        <div className="login-brand"><BrandLogo className="medora-logo--auth" /><span>Patient access</span></div>
        <div className="login-hero-copy">
          <p className="eyebrow eyebrow--light">One connected care journey</p>
          <h1>Your care.<br /><em>In one place.</em></h1>
          <p>Book specialists, follow diagnostic orders, and receive doctor-approved reports in language that feels familiar.</p>
        </div>
        <div className="login-index"><span>01</span><span>Consult</span><span>Diagnose</span><span>Recover</span></div>
      </section>
      <section className="login-form-panel">
        <div className="login-form-wrap">
          <p className="eyebrow">Patient registration</p>
          <h2>Create your account.</h2>
          <p className="form-intro">Start a secure longitudinal record with MedoraAI.</p>
          <form className="login-form" onSubmit={submit}>
            {[
              ['full_name', 'Full name', 'Amit Kumar'],
              ['username', 'Username', 'amit.kumar'],
              ['email', 'Email', 'amit@example.com'],
              ['phone', 'Phone', '+91 98765 43210'],
            ].map(([key, label, placeholder]) => (
              <label key={key}><span>{label}</span><input value={form[key as keyof typeof form]} placeholder={placeholder} onChange={(event) => setForm({ ...form, [key]: event.target.value })} required={key === 'full_name' || key === 'username'} /></label>
            ))}
            <label><span>Password</span><input type="password" minLength={6} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
            {error && <div className="form-error">{error}</div>}
            <button className="button button--primary button--wide" disabled={loading}>{loading ? 'Creating account…' : 'Create patient account'}</button>
          </form>
          <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
        </div>
      </section>
    </div>
  );
}
