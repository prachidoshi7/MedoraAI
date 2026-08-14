import { useEffect, useState } from 'react';
import { createDoctor, deleteDoctor, getAdminDoctors, getDepartments, updateDoctor } from '../api/client';
import type { Department, Doctor, DoctorCreateInput, DoctorUpdateInput } from '../types';

const emptyDoctor: DoctorCreateInput = {
  username: '', password: '', full_name: '', qualification: '', specialization: '',
  department_id: 0, email: '', phone: '',
};

export default function DoctorAdminPage() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form, setForm] = useState<DoctorCreateInput>(emptyDoctor);
  const [editId, setEditId] = useState<number | null>(null);
  const [edit, setEdit] = useState<DoctorUpdateInput>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    const [doctorItems, departmentItems] = await Promise.all([getAdminDoctors(), getDepartments()]);
    setDoctors(doctorItems);
    setDepartments(departmentItems.filter((item) => item.name !== 'Radiology'));
    setForm((current) => ({ ...current, department_id: current.department_id || departmentItems.find((item) => item.name !== 'Radiology')?.id || 0 }));
  };

  useEffect(() => { load().catch(() => setError('Could not load doctor administration.')); }, []);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setMessage('');
    try { await action(); } catch (err: any) { setError(err.response?.data?.detail || 'Could not update this doctor.'); }
    finally { setBusy(false); }
  };

  const addDoctor = (event: React.FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await createDoctor(form);
      setForm({ ...emptyDoctor, department_id: departments[0]?.id || 0 });
      setMessage('Doctor account created and added to the patient directory.');
      await load();
    });
  };

  const beginEdit = (doctor: Doctor) => {
    setEditId(doctor.id);
    setEdit({
      full_name: doctor.full_name,
      qualification: doctor.qualification,
      specialization: doctor.specialization,
      department_id: doctor.department_id || undefined,
      email: doctor.email,
      phone: doctor.phone,
      availability_note: doctor.availability_note,
    });
  };

  const saveEdit = (doctorId: number) => void run(async () => {
    await updateDoctor(doctorId, edit);
    setEditId(null); setEdit({}); setMessage('Doctor profile updated.'); await load();
  });

  const toggleAvailability = (doctor: Doctor) => void run(async () => {
    await updateDoctor(doctor.id, {
      is_available: !doctor.is_available,
      availability_note: doctor.is_available ? (doctor.availability_note || 'Temporarily unavailable') : '',
    });
    setMessage(doctor.is_available ? 'Doctor marked temporarily unavailable.' : 'Doctor is available for booking again.');
    await load();
  });

  const deactivate = (doctor: Doctor) => void run(async () => {
    await deleteDoctor(doctor.id); setMessage('Doctor safely deactivated. Linked records were preserved.'); await load();
  });

  const restore = (doctor: Doctor) => void run(async () => {
    await updateDoctor(doctor.id, { is_active: true, is_available: true, availability_note: '' });
    setMessage('Doctor restored to the active directory.'); await load();
  });

  return (
    <div className="workspace-page portal-page admin-doctors-page">
      <header className="portal-hero"><div><p className="eyebrow">Hospital administration</p><h1>Doctors admin panel</h1><p>Add doctors, maintain their qualifications and specialties, and control patient booking availability.</p></div><span className="env-badge"><i /> Admin controls</span></header>
      {(error || message) && <div className={error ? 'form-error' : 'success-banner'}>{error || message}</div>}

      <section className="portal-card doctor-create-card">
        <header><div><p className="eyebrow">New clinician</p><h2>Add a doctor</h2></div><span className="status-pill">All fields can be updated later</span></header>
        <form className="form-grid" onSubmit={addDoctor}>
          <label className="field"><span>Doctor name</span><input required minLength={2} placeholder="Dr. Full Name" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label>
          <label className="field"><span>Degree / qualification</span><input required placeholder="MBBS, MD (Medicine)" value={form.qualification} onChange={(event) => setForm({ ...form, qualification: event.target.value })} /></label>
          <label className="field"><span>Specialist in</span><input required placeholder="Internal Medicine" value={form.specialization} onChange={(event) => setForm({ ...form, specialization: event.target.value })} /></label>
          <label className="field"><span>Department</span><select required value={form.department_id} onChange={(event) => setForm({ ...form, department_id: Number(event.target.value) })}>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Login username</span><input required minLength={3} value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
          <label className="field"><span>Initial password</span><input required minLength={6} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
          <label className="field"><span>Email</span><input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          <label className="field"><span>Phone</span><input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
          <div className="flow-actions field--wide"><button className="button button--primary" disabled={busy || !form.department_id}>{busy ? 'Saving…' : 'Add doctor'}</button></div>
        </form>
      </section>

      <section className="portal-card">
        <header><div><p className="eyebrow">Directory control</p><h2>All doctors</h2></div><span className="status-pill">{doctors.filter((item) => item.is_active).length} active</span></header>
        <div className="doctor-admin-list">
          {doctors.map((doctor) => (
            <article key={doctor.id} className={!doctor.is_active ? 'is-inactive' : ''}>
              {editId === doctor.id ? (
                <div className="doctor-admin-edit form-grid">
                  <label className="field"><span>Name</span><input value={edit.full_name || ''} onChange={(event) => setEdit({ ...edit, full_name: event.target.value })} /></label>
                  <label className="field"><span>Degree / qualification</span><input value={edit.qualification || ''} onChange={(event) => setEdit({ ...edit, qualification: event.target.value })} /></label>
                  <label className="field"><span>Specialist in</span><input value={edit.specialization || ''} onChange={(event) => setEdit({ ...edit, specialization: event.target.value })} /></label>
                  <label className="field"><span>Department</span><select value={edit.department_id} onChange={(event) => setEdit({ ...edit, department_id: Number(event.target.value) })}>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                  <label className="field"><span>Email</span><input value={edit.email || ''} onChange={(event) => setEdit({ ...edit, email: event.target.value })} /></label>
                  <label className="field"><span>Phone</span><input value={edit.phone || ''} onChange={(event) => setEdit({ ...edit, phone: event.target.value })} /></label>
                  <label className="field field--wide"><span>Patient-facing availability note</span><input placeholder="Available from Monday" value={edit.availability_note || ''} onChange={(event) => setEdit({ ...edit, availability_note: event.target.value })} /></label>
                  <div className="flow-actions field--wide"><button type="button" className="button" onClick={() => setEditId(null)}>Cancel</button><button type="button" className="button button--primary" disabled={busy} onClick={() => saveEdit(doctor.id)}>Save profile</button></div>
                </div>
              ) : (
                <>
                  <div className="doctor-admin-identity"><span className="profile-avatar">{doctor.full_name.charAt(0)}</span><div><strong>{doctor.full_name}</strong><span>{doctor.qualification || 'Qualification not set'}</span><small>{doctor.specialization} · {doctor.department?.name || 'No department'} · @{doctor.username}</small></div></div>
                  <span className={`status-pill ${doctor.is_active && doctor.is_available ? 'status-pill--available' : ''}`}>{!doctor.is_active ? 'Deactivated' : doctor.is_available ? 'Available' : 'Temporarily unavailable'}</span>
                  <p>{doctor.availability_note || (doctor.is_available ? 'Accepting patient appointments' : 'Not accepting appointments')}</p>
                  <div className="doctor-admin-actions"><button className="button" disabled={busy || !doctor.is_active} onClick={() => beginEdit(doctor)}>Edit details</button>{doctor.is_active ? <><button className="button" disabled={busy} onClick={() => toggleAvailability(doctor)}>{doctor.is_available ? 'Set unavailable' : 'Set available'}</button><button className="text-button text-button--danger" disabled={busy} onClick={() => deactivate(doctor)}>Delete doctor</button></> : <button className="button button--primary" disabled={busy} onClick={() => restore(doctor)}>Restore doctor</button>}</div>
                </>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
