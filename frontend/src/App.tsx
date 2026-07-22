import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import HistorySidebar from './components/HistorySidebar';
import LoginPage from './pages/LoginPage';
import ResultsPage from './pages/ResultsPage';
import UploadPage from './pages/UploadPage';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function Brand() {
  return (
    <span className="brand-lockup" aria-label="Medora AI Clinical Imaging">
      <span className="brand-mark" aria-hidden="true" />
      <span><strong>Medora</strong><small>AI clinical imaging</small></span>
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
    <aside className="site-sidebar">
      <button className="brand-button" onClick={() => navigate('/upload')}><Brand /></button>
      <button
        className={`new-study-button${location.pathname === '/upload' ? ' active' : ''}`}
        onClick={() => navigate('/upload')}
      >
        <span aria-hidden="true">＋</span> New scan
      </button>

      <div className="sidebar-history"><HistorySidebar /></div>

      <footer className="sidebar-footer">
        <div className="engine-status"><i /> Inference engine connected</div>
        <div className="doctor-identity">
          <span className="doctor-avatar">{username?.slice(0, 1).toUpperCase() || 'D'}</span>
          <span><small>Signed in as</small>Dr. {username || 'Doctor'}</span>
        </div>
        <button className="nav-signout" onClick={leave}>Sign out</button>
      </footer>
    </aside>
  );
}

function ApplicationFrame() {
  const { isAuthenticated } = useAuth();

  return (
    <div className={isAuthenticated ? 'app-shell' : 'auth-shell'}>
      <Navigation />
      <main className={isAuthenticated ? 'page-content' : 'page-content page-content--auth'}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/upload" element={<PrivateRoute><UploadPage /></PrivateRoute>} />
          <Route path="/results/:scanId" element={<PrivateRoute><ResultsPage /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/upload" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return <BrowserRouter><ApplicationFrame /></BrowserRouter>;
}
