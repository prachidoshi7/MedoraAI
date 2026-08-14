import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import BookAppointment from './pages/BookAppointment';
import CaseStudyView from './pages/CaseStudyView';
import ConsultationPage from './pages/ConsultationPage';
import DoctorDashboard from './pages/DoctorDashboard';
import DoctorAdminPage from './pages/DoctorAdminPage';
import LabDashboard from './pages/LabDashboard';
import LabUploadScan from './pages/LabUploadScan';
import LoginPage from './pages/LoginPage';
import PatientDashboard from './pages/PatientDashboard';
import PharmacyBillPage from './pages/PharmacyBillPage';
import PharmacyDashboard from './pages/PharmacyDashboard';
import PharmacyInventoryPage from './pages/PharmacyInventoryPage';
import RegisterPage from './pages/RegisterPage';
import ResultsPage from './pages/ResultsPage';
import UploadPage from './pages/UploadPage';
import type { UserRole } from './types';

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
  return <span className="brand-lockup"><span className="brand-mark" /><span><strong>Medora</strong><small>Hospital intelligence</small></span></span>;
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

function Navigation() {
  const { isAuthenticated, logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  if (!isAuthenticated || !user) return null;
  const leave = () => { logout(); navigate('/login'); };
  return (
    <aside className="site-sidebar hospital-sidebar">
      <Link className="brand-button" to={homeByRole[user.role]}><Brand /></Link>
      <div className="role-chip"><span>{user.role === 'lab_tech' ? 'LT' : user.role.slice(0, 1).toUpperCase()}</span><div><small>Workspace</small><strong>{user.role.replace('_', ' ')}</strong></div></div>
      <nav className="role-navigation">
        {navByRole[user.role].map((item) => <Link key={item.path} className={location.pathname === item.path ? 'active' : ''} to={item.path}><span>{item.icon}</span>{item.label}</Link>)}
      </nav>
      <div className="journey-map"><p className="eyebrow">Connected journey</p>{['Patient visit', 'Doctor consult', 'AI diagnostics', 'Clinical review', 'Prescription', 'Pharmacy billing'].map((label, index) => <div key={label}><span>{String(index + 1).padStart(2, '0')}</span><i /><strong>{label}</strong></div>)}</div>
      <footer className="sidebar-footer">
        <div className="engine-status"><i /> Hospital systems connected</div>
        <div className="doctor-identity"><span className="doctor-avatar">{user.full_name?.slice(0, 1) || 'M'}</span><span><small>Signed in as</small>{user.full_name}</span></div>
        <button className="nav-signout" onClick={leave}>Sign out</button>
      </footer>
    </aside>
  );
}

function ApplicationFrame() {
  const { isAuthenticated, user } = useAuth();
  const dashboardLabels: Partial<Record<UserRole, string>> = {
    patient: 'Patient dashboard', doctor: 'Doctor dashboard', lab_tech: 'Lab dashboard',
    pharmacy: 'Pharmacy dashboard', admin: 'Administration dashboard',
  };
  return (
    <div className={isAuthenticated ? 'app-shell' : 'auth-shell'}>
      <Navigation />
      <main className={isAuthenticated ? 'page-content' : 'page-content page-content--auth'}>
        {isAuthenticated && user && <div className="workspace-context-bar"><span>{dashboardLabels[user.role]}</span><small>{user.full_name}</small></div>}
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
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
