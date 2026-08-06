import { useEffect, useState } from "react";
import * as authApi from "@/api/auth";
import type { User } from "@/types";

const ROLES = ["admin", "manager", "employee"];

export function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", display_name: "", role: "employee" });

  async function load() {
    setIsLoading(true);
    try {
      setUsers(await authApi.listUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function flash(msg: string) {
    setBanner(msg);
    setTimeout(() => setBanner(null), 3000);
  }

  async function handleRoleChange(userId: number, role: string) {
    try {
      await authApi.updateUser(userId, { role });
      flash("Role updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update role.");
    }
  }

  async function handleToggleActive(user: User) {
    try {
      await authApi.updateUser(user.id, { is_active: !user.is_active });
      flash(user.is_active ? "User disabled." : "User re-enabled.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status.");
    }
  }

  async function handleResetSessions(userId: number) {
    try {
      const msg = await authApi.resetUserSessions(userId);
      flash(msg);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset sessions.");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await authApi.createUser(form);
      setForm({ email: "", password: "", display_name: "", role: "employee" });
      setFormOpen(false);
      flash("User created.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user.");
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-10 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">User management</h1>
          <p className="mt-1 text-sm text-[#6B6558]">Assign roles, disable accounts, and force session resets.</p>
        </div>
        <button onClick={() => setFormOpen((v) => !v)} className="rounded bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft">
          {formOpen ? "Cancel" : "Add user"}
        </button>
      </div>

      {banner && <div className="mb-4 rounded border border-teal/30 bg-teal/5 px-3 py-2 text-sm text-teal">{banner}</div>}
      {error && <div className="mb-4 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>}

      {formOpen && (
        <form onSubmit={handleCreate} className="mb-6 grid grid-cols-2 gap-3 rounded border border-dashed border-rule bg-white p-4">
          <input required placeholder="Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} className="rounded border border-rule px-3 py-2 text-sm" />
          <input required placeholder="Display name" value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} className="rounded border border-rule px-3 py-2 text-sm" />
          <input required type="password" placeholder="Password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} className="rounded border border-rule px-3 py-2 text-sm" />
          <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} className="rounded border border-rule bg-white px-3 py-2 text-sm">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button type="submit" className="col-span-2 rounded bg-teal py-2 text-sm font-medium text-white hover:opacity-90">Create user</button>
        </form>
      )}

      <div className="overflow-x-auto rounded border border-rule bg-white">
        <table className="w-full text-left text-xs">
          <thead className="bg-paper-dim text-[#6B6558]">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Last login</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-[#6B6558]">Loading…</td></tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="border-t border-rule/50">
                  <td className="px-3 py-2">{u.display_name}</td>
                  <td className="px-3 py-2 text-[#6B6558]">{u.email}</td>
                  <td className="px-3 py-2">
                    <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)} className="rounded border border-rule bg-white px-2 py-1 text-xs">
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] ${u.is_active ? "bg-teal/10 text-teal" : "bg-danger/10 text-danger"}`}>
                      {u.is_active ? "active" : "disabled"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-[#6B6558]">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      <button onClick={() => handleToggleActive(u)} className="text-[11px] text-ink hover:underline">
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                      <button onClick={() => handleResetSessions(u.id)} className="text-[11px] text-danger hover:underline">
                        Reset sessions
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
