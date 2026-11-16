import { api, type AuthStatus } from "@zoi/api-client";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useApp } from "../stores/appStore";
import { Card, StatusDot } from "../ui";

/** Account: ZOI dipakai satu pemilik. Mode local tanpa login; mode online memakai login yang ada. */
export function AccountPage() {
  const config = useApp((s) => s.config);
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  useEffect(() => { api.auth.status().then(setAuth).catch(() => setAuth(null)); }, []);
  return (
    <section className="page" data-testid="account-page">
      <h1>Account</h1>
      <div className="proj-grid">
        <Card title="Akses">
          <p><StatusDot tone="ok" label={`Mode: ${config?.mode ?? "…"}`} /></p>
          {auth?.enabled ? (
            <>
              <p className="muted">Login aktif — satu akun pemilik untuk seluruh produk ZOI.</p>
              <button type="button" onClick={() => api.auth.logout().then(() => window.location.reload())}>Keluar</button>
            </>
          ) : (
            <p className="muted">Mode ini tidak memakai login: ZOI hanya menerima akses dari laptop ini, atau dari perangkatmu lewat
              Tailscale bila diaktifkan. Lihat panduan <code>docs/AKSES_HP.md</code>.</p>
          )}
        </Card>
        <Card title="Akun terhubung">
          <p><Link to="/settings/youtube">YouTube (OAuth)</Link> — hubungkan, putuskan, atau hubungkan ulang channel.</p>
          <p><Link to="/settings/ai-cloud">AI Cloud</Link> — API key disimpan di backend, tidak pernah ditampilkan.</p>
          <p><Link to="/settings">Settings</Link> · <Link to="/diagnostics">Diagnostics</Link></p>
        </Card>
      </div>
    </section>
  );
}
