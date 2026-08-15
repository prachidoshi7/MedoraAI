import { Link } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';
import { useAuth } from '../hooks/useAuth';

const workflow = [
  ['01', 'Patient visit', 'Book a consultation and keep the clinical reason attached to the record.'],
  ['02', 'Diagnostic order', 'The doctor selects the study type and shares clinical context with the lab.'],
  ['03', 'AI analysis', 'The imaging pipeline classifies the study and produces a visual explanation.'],
  ['04', 'Clinical review', 'A doctor reviews the image, AI findings and draft report before approval.'],
  ['05', 'Connected care', 'Final reports, prescriptions and pharmacy bills return to the patient dashboard.'],
];

const capabilities = [
  ['XR', 'Chest X-ray reporting', 'MAIRA-2 drafts image-aware chest reports, supported by a local RAD-DINO research classifier and token attribution.'],
  ['MR', 'Brain MRI screening', 'EfficientNetB3 supports four-class brain-tumor screening with Grad-CAM++ visual explanation.'],
  ['CT', 'Lung CT analysis', 'A five-class convolutional model supports lung CT category screening inside the same workflow.'],
  ['US', 'Kidney ultrasound', 'Renal ultrasound screening identifies normal and stone patterns with visual attribution.'],
  ['Rx', 'Prescription continuity', 'Approved clinical decisions flow into prescriptions, medicine availability and itemized pharmacy bills.'],
  ['ID', 'Role-aware records', 'Patients, doctors, lab teams, pharmacies and administrators see only the tools relevant to their work.'],
];

export default function LandingPage() {
  const { isAuthenticated, user } = useAuth();
  const dashboardPath = user ? ({ patient: '/patient/dashboard', doctor: '/doctor/dashboard', lab_tech: '/lab/dashboard', pharmacy: '/pharmacy/dashboard', admin: '/admin/doctors' } as const)[user.role] : '/login';

  return <div className="landing-page">
    <header className="landing-nav">
      <div className="landing-wrap landing-nav__inner">
        <Link to="/" aria-label="MedoraAI home"><BrandLogo className="landing-logo" /></Link>
        <nav aria-label="Main navigation">
          <a href="#workflow">Workflow</a><a href="#capabilities">Capabilities</a><a href="#safety">Clinical safety</a>
        </nav>
        <Link className="landing-nav__cta" to={isAuthenticated ? dashboardPath : '/login'}>{isAuthenticated ? 'Open dashboard' : 'Sign in'}</Link>
      </div>
    </header>

    <main>
      <section className="landing-hero landing-wrap">
        <div className="landing-grid" aria-hidden="true" />
        <div className="landing-hero__copy">
          <p className="landing-eyebrow"><i /> Connected diagnostic care</p>
          <h1>From medical image to <em>clinician-reviewed care.</em></h1>
          <p className="landing-lead">MedoraAI connects consultations, diagnostic imaging, explainable AI, clinical reporting, prescriptions and pharmacy billing in one role-aware hospital workflow.</p>
          <div className="landing-actions">
            <Link className="landing-button landing-button--primary" to={isAuthenticated ? dashboardPath : '/login'}>{isAuthenticated ? 'Continue to dashboard' : 'Enter MedoraAI'} <span>→</span></Link>
            {!isAuthenticated && <Link className="landing-button landing-button--quiet" to="/register">Create patient account</Link>}
          </div>
          <div className="landing-trust"><span><b>4</b> imaging pathways</span><span><b>5</b> connected care roles</span><span><b>1</b> clinical record</span></div>
        </div>

        <div className="landing-scan-card" aria-label="Illustration of MedoraAI chest X-ray analysis">
          <header><span><i /> Analysis workspace</span><b>CHEST X-RAY</b></header>
          <div className="landing-scan">
            <svg viewBox="0 0 440 470" role="img" aria-label="Stylized chest X-ray">
              <defs><radialGradient id="medoraLung" cx="50%" cy="42%" r="68%"><stop offset="0" stopColor="#dbe5e8" stopOpacity=".78"/><stop offset="1" stopColor="#53626a" stopOpacity=".18"/></radialGradient></defs>
              <rect width="440" height="470" fill="#11171a"/><path d="M220 46v372" stroke="#b7c1c4" strokeOpacity=".22" strokeWidth="10"/>
              <path d="M200 78C130 75 77 132 72 235c-4 94 45 168 124 171 21-70 22-251 4-328Z" fill="url(#medoraLung)" stroke="#aebbbf" strokeOpacity=".38"/>
              <path d="M240 78c70-3 123 54 128 157 4 94-45 168-124 171-21-70-22-251-4-328Z" fill="url(#medoraLung)" stroke="#aebbbf" strokeOpacity=".38"/>
              {[120,160,200,240,280,320,360].map((y) => <path key={y} d={`M72 ${y} Q220 ${y - 42} 368 ${y}`} fill="none" stroke="#d0d8da" strokeOpacity=".14" strokeWidth="5"/>)}
              <circle cx="292" cy="276" r="52" fill="#e8542a" opacity=".13"/><circle cx="292" cy="276" r="27" fill="#f2a93b" opacity=".18"/>
            </svg>
            <div className="landing-scan__line" /><div className="landing-finding"><span>REGION OF INTEREST</span></div>
          </div>
          <footer><span>Image-aware report draft</span><b>Awaiting clinician review</b></footer>
        </div>
      </section>

      <div className="landing-ticker" aria-label="MedoraAI capabilities"><div>{['MAIRA-2 chest reporting','RAD-DINO attribution','Brain Grad-CAM++','Strict scan verification','Doctor approval workflow','Patient-language summaries','Prescription continuity','Itemized pharmacy billing','MAIRA-2 chest reporting','RAD-DINO attribution','Brain Grad-CAM++','Strict scan verification'].map((item,index)=><span key={`${item}-${index}`}>{item}</span>)}</div></div>

      <section className="landing-section landing-wrap" id="workflow">
        <div className="landing-section__head"><p className="landing-eyebrow"><i /> One continuous record</p><h2>Care moves forward without losing context.</h2><p>Every handoff carries the patient, doctor, diagnostic order and final clinical decision with it.</p></div>
        <div className="landing-workflow">{workflow.map(([number,title,copy])=><article key={number}><span>{number}</span><h3>{title}</h3><p>{copy}</p></article>)}</div>
      </section>

      <section className="landing-section landing-section--ink" id="capabilities">
        <div className="landing-wrap"><div className="landing-section__head"><p className="landing-eyebrow landing-eyebrow--dark"><i /> Diagnostic capability</p><h2>Multiple imaging models. One governed workflow.</h2><p>Specialized models support each modality while review, records and downstream care remain consistent.</p></div>
        <div className="landing-capabilities">{capabilities.map(([icon,title,copy])=><article key={title}><span>{icon}</span><h3>{title}</h3><p>{copy}</p></article>)}</div></div>
      </section>

      <section className="landing-section landing-wrap" id="safety">
        <div className="landing-safety">
          <div><p className="landing-eyebrow"><i /> Clinical safety</p><h2>AI drafts. Clinicians decide.</h2><p>MedoraAI is designed as clinical decision support. Diagnostic outputs and generated reports remain subject to qualified medical review before they become part of patient care.</p><Link className="landing-button landing-button--primary" to={isAuthenticated ? dashboardPath : '/login'}>Open the clinical workspace <span>→</span></Link></div>
          <div className="landing-safety__rules"><article><b>01</b><span><strong>Verify before inference</strong>Reject mismatched or inadequate scan types before analysis.</span></article><article><b>02</b><span><strong>Explain the model signal</strong>Pair classifications with heatmaps or token attribution.</span></article><article><b>03</b><span><strong>Require clinical review</strong>Keep generated findings editable and visibly unapproved until reviewed.</span></article><article><b>04</b><span><strong>Preserve provenance</strong>Keep the order, scan, report and responsible clinician connected.</span></article></div>
        </div>
      </section>

      <section className="landing-cta landing-wrap"><div><p className="landing-eyebrow landing-eyebrow--dark"><i /> MedoraAI workspace</p><h2>Bring the diagnostic journey into one view.</h2><p>Use the role-specific demo workspaces to follow a patient from consultation through approved report and pharmacy fulfillment.</p><div className="landing-actions"><Link className="landing-button landing-button--light" to={isAuthenticated ? dashboardPath : '/login'}>{isAuthenticated ? 'Return to dashboard' : 'Sign in to continue'} <span>→</span></Link>{!isAuthenticated && <Link className="landing-button landing-button--outline-light" to="/register">Register as patient</Link>}</div></div><span className="landing-cta__mark">M</span></section>
    </main>

    <footer className="landing-footer"><div className="landing-wrap"><BrandLogo className="landing-logo" /><p>Explainable imaging support for connected clinical care.</p><span>Decision support · Clinician review required</span></div></footer>
  </div>;
}
