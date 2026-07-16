import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import LoginPage from './pages/LoginPage';
import ResultsPage from './pages/ResultsPage';
import UploadPage from './pages/UploadPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function Brand() {
  return (
    <span className="brand-lockup" aria-label="Medora Clinical Imaging">
      <span className="brand-mark" aria-hidden="true"><i /><i /></span>
      <span>
        <strong>Medora</strong>
        <small>Clinical imaging</small>
      </span>
    </span>
  );
}

function Navigation() {
  const { isAuthenticated, logout, username } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (!isAuthenticated) return null;

  const leave = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="site-header">
      <button className="brand-button" onClick={() => navigate('/upload')}><Brand /></button>
      <nav className="site-nav" aria-label="Primary navigation">
        <button
          className={location.pathname === '/upload' ? 'active' : ''}
          onClick={() => navigate('/upload')}
        >
          New study
        </button>
        <span className="nav-divider" />
        <span className="doctor-identity">
          <span className="doctor-avatar">{username?.slice(0, 1).toUpperCase() || 'D'}</span>
          <span><small>Signed in as</small>Dr. {username || 'Doctor'}</span>
        </span>
        <button className="nav-signout" onClick={leave}>Sign out</button>
      </nav>
    </header>
  );
}

function ApplicationFrame() {
  const { isAuthenticated } = useAuth();

  return (
    <>
      <Navigation />
      <main className={isAuthenticated ? 'page-content' : 'page-content page-content--auth'}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/upload" element={<PrivateRoute><UploadPage /></PrivateRoute>} />
          <Route path="/results/:scanId" element={<PrivateRoute><ResultsPage /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/upload" replace />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return <BrowserRouter><ApplicationFrame /></BrowserRouter>;
}
