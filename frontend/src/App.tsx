import { useRef, useState } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import BookAppointment from './pages/BookAppointment';
import CaseStudyView from './pages/CaseStudyView';
import ConsultationPage from './pages/ConsultationPage';
import DoctorDashboard from './pages/DoctorDashboard';
import DoctorAdminPage from './pages/DoctorAdminPage';
import LabDashboard from './pages/LabDashboard';
import LabUploadScan from './pages/LabUploadScan';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import PatientDashboard from './pages/PatientDashboard';
import PharmacyBillPage from './pages/PharmacyBillPage';
import PharmacyDashboard from './pages/PharmacyDashboard';
import PharmacyInventoryPage from './pages/PharmacyInventoryPage';
import RegisterPage from './pages/RegisterPage';
import ResultsPage from './pages/ResultsPage';
import UploadPage from './pages/UploadPage';
import type { UserRole } from './types';
import BrandLogo from './components/BrandLogo';
import { updateMe, uploadProfileAvatar } from './api/client';

const homeByRole: Record<UserRole, string> = {
  patient: '/patient/dashboard',
  doctor: '/doctor/dashboard',
  lab_tech: '/lab/dashboard',
  pharmacy: '/pharmacy/dashboard',
  admin: '/admin/doctors',
};

function ProtectedRoute({ roles, children }: { roles?: UserRole[]; children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (roles && (!user || !roles.includes(user.role))) return <Navigate to={user ? homeByRole[user.role] : '/login'} replace />;
  return <>{children}</>;
}

function HomeRedirect() {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated || !user) return <Navigate to="/login" replace />;
  return <Navigate to={homeByRole[user.role]} replace />;
}

function Brand() {
  return <BrandLogo className="medora-logo--sidebar" />;
}

const navByRole: Record<UserRole, Array<{ path: string; label: string; icon: string }>> = {
  patient: [
    { path: '/patient/dashboard', label: 'My care', icon: '⌂' },
    { path: '/patient/book-appointment', label: 'Book appointment', icon: '＋' },
  ],
  doctor: [
    { path: '/doctor/dashboard', label: 'Clinical queue', icon: '⌂' },
    { path: '/upload', label: 'Direct analysis', icon: '⌁' },
  ],
  lab_tech: [
    { path: '/lab/dashboard', label: 'Lab worklist', icon: '⌂' },
    { path: '/upload', label: 'Direct upload', icon: '⌁' },
  ],
  pharmacy: [
    { path: '/pharmacy/dashboard', label: 'Medicine orders', icon: 'Rx' },
    { path: '/pharmacy/inventory', label: 'Store management', icon: '▦' },
  ],
  admin: [
    { path: '/admin/doctors', label: 'Doctors admin', icon: 'Dr' },
    { path: '/doctor/dashboard', label: 'Clinical operations', icon: '⌂' },
    { path: '/pharmacy/inventory', label: 'Pharmacy store', icon: '▦' },
    { path: '/upload', label: 'Direct analysis', icon: '⌁' },
  ],
};

function Navigation({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { isAuthenticated, logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  if (!isAuthenticated || !user) return null;
  const leave = () => { logout(); navigate('/login'); };
  return (
    <aside className={`site-sidebar hospital-sidebar${collapsed ? ' is-collapsed' : ''}`}>
      <button className="sidebar-collapse-control" onClick={onToggle} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
        <span aria-hidden="true">{collapsed ? '›' : '‹'}</span>
      </button>
      <Link className="brand-button" to={homeByRole[user.role]}><Brand /></Link>
      <div className="role-chip"><span>{user.role === 'lab_tech' ? 'LT' : user.role.slice(0, 1).toUpperCase()}</span><div><small>Workspace</small><strong>{user.role.replace('_', ' ')}</strong></div></div>
      <nav className="role-navigation">
        {navByRole[user.role].map((item) => <Link key={item.path} className={location.pathname === item.path ? 'active' : ''} to={item.path} title={collapsed ? item.label : undefined}><span>{item.icon}</span><b>{item.label}</b></Link>)}
      </nav>
      <div className="sidebar-spacer" />
      <footer className="sidebar-footer">
        <div className="engine-status"><i /> Hospital systems connected</div>
        <button className="nav-signout" onClick={leave}>Sign out</button>
      </footer>
    </aside>
  );
}

function AccountMenu() {
  const { setCurrentUser, user } = useAuth();
  const fileInput = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState({ full_name: user?.full_name || '', email: user?.email || '', phone: user?.phone || '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  if (!user) return null;
  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError('');
    try { setCurrentUser(await updateMe(profile)); setOpen(false); }
    catch (nextError: any) { setError(nextError.response?.data?.detail || 'Could not save your profile.'); }
    finally { setSaving(false); }
  };
  const changeAvatar = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    setSaving(true); setError('');
    try { setCurrentUser(await uploadProfileAvatar(file)); }
    catch (nextError: any) { setError(nextError.response?.data?.detail || 'Could not upload that image.'); }
    finally { setSaving(false); event.target.value = ''; }
  };
  return <div className="account-menu">
    <button className="account-trigger" onClick={() => { setProfile({ full_name: user.full_name, email: user.email, phone: user.phone }); setOpen((value) => !value); }} aria-expanded={open}>
      <span className="doctor-avatar">{user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.full_name.slice(0, 1)}</span><span><small>Patient profile</small><strong>{user.full_name}</strong></span><b>⌄</b>
    </button>
    {open && <form className="account-panel" onSubmit={saveProfile}>
      <header><div><small>Account</small><strong>Profile settings</strong></div><button type="button" onClick={() => setOpen(false)} aria-label="Close profile">×</button></header>
      <button type="button" className="profile-photo-control" onClick={() => fileInput.current?.click()} disabled={saving}><span className="doctor-avatar">{user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.full_name.slice(0, 1)}</span><span>Update profile picture<small>JPG, PNG or WebP · max 5 MB</small></span></button>
      <input ref={fileInput} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={changeAvatar} />
      <label><span>Name</span><input value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} required /></label>
      <label><span>Phone number</span><input type="tel" value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /></label>
      <label><span>Email</span><input type="email" value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} /></label>
      {error && <p className="account-panel__error">{error}</p>}
      <button className="button button--primary button--wide" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button>
    </form>}
  </div>;
}

function ApplicationFrame() {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();
  const isLandingPage = location.pathname === '/';
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('medoraai_sidebar_collapsed') === 'true');
  const toggleSidebar = () => setSidebarCollapsed((current) => {
    const next = !current;
    localStorage.setItem('medoraai_sidebar_collapsed', String(next));
    return next;
  });
  const dashboardLabels: Partial<Record<UserRole, string>> = {
    patient: 'Patient dashboard', doctor: 'Doctor dashboard', lab_tech: 'Lab dashboard',
    pharmacy: 'Pharmacy dashboard', admin: 'Administration dashboard',
  };
  return (
    <div className={isAuthenticated && !isLandingPage ? `app-shell${sidebarCollapsed ? ' app-shell--collapsed' : ''}` : 'auth-shell'}>
      {!isLandingPage && <Navigation collapsed={sidebarCollapsed} onToggle={toggleSidebar} />}
      <main className={isAuthenticated && !isLandingPage ? 'page-content' : 'page-content page-content--auth'}>
        {isAuthenticated && user && !isLandingPage && <div className="workspace-context-bar"><span>{dashboardLabels[user.role]}</span><AccountMenu /></div>}
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/patient/dashboard" element={<ProtectedRoute roles={['patient']}><PatientDashboard /></ProtectedRoute>} />
          <Route path="/patient/book-appointment" element={<ProtectedRoute roles={['patient']}><BookAppointment /></ProtectedRoute>} />
          <Route path="/patient/case-study/:caseStudyId" element={<ProtectedRoute roles={['patient']}><CaseStudyView /></ProtectedRoute>} />
          <Route path="/doctor/dashboard" element={<ProtectedRoute roles={['doctor', 'admin']}><DoctorDashboard /></ProtectedRoute>} />
          <Route path="/admin/doctors" element={<ProtectedRoute roles={['admin']}><DoctorAdminPage /></ProtectedRoute>} />
          <Route path="/doctor/consultation/:appointmentId" element={<ProtectedRoute roles={['doctor', 'admin']}><ConsultationPage /></ProtectedRoute>} />
          <Route path="/doctor/case-study/:caseStudyId" element={<ProtectedRoute roles={['doctor', 'admin']}><CaseStudyView /></ProtectedRoute>} />
          <Route path="/lab/dashboard" element={<ProtectedRoute roles={['lab_tech', 'admin']}><LabDashboard /></ProtectedRoute>} />
          <Route path="/lab/upload/:orderId" element={<ProtectedRoute roles={['lab_tech', 'admin']}><LabUploadScan /></ProtectedRoute>} />
          <Route path="/lab/results/:scanId" element={<ProtectedRoute roles={['lab_tech', 'admin']}><ResultsPage /></ProtectedRoute>} />
          <Route path="/pharmacy/dashboard" element={<ProtectedRoute roles={['pharmacy', 'admin']}><PharmacyDashboard /></ProtectedRoute>} />
          <Route path="/pharmacy/inventory" element={<ProtectedRoute roles={['pharmacy', 'admin']}><PharmacyInventoryPage /></ProtectedRoute>} />
          <Route path="/medicine-bills/:billId" element={<ProtectedRoute roles={['patient', 'pharmacy', 'admin']}><PharmacyBillPage /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute roles={['doctor', 'lab_tech', 'admin']}><UploadPage /></ProtectedRoute>} />
          <Route path="/results/:scanId" element={<ProtectedRoute><ResultsPage /></ProtectedRoute>} />
          <Route path="*" element={<HomeRedirect />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() { return <BrowserRouter><ApplicationFrame /></BrowserRouter>; }
