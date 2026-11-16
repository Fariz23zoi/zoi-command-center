import { api, ApiError, type AuthStatus } from "@zoi/api-client";
import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";

/** Gerbang login mode online. Di mode development/local auth nonaktif dan anak langsung dirender. */
export function AuthGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    api.auth.status().then((s) => { setStatus(s); setFailed(false); }, () => setFailed(true));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    const out = () => setStatus((s) => (s ? { ...s, logged_in: false } : s));
    window.addEventListener("zoi-unauthorized", out);
    return () => window.removeEventListener("zoi-unauthorized", out);
  }, []);

  if (failed) {
    return (
      <main className="auth-screen">
        <section className="auth-card">
          <h1>ZOI</h1>
          <p className="muted">
            Server belum menjawab. Di hosting gratis, ZOI yang tertidur butuh sekitar satu menit untuk bangun.
          </p>
          <button type="button" onClick={load}>Coba lagi</button>
        </section>
      </main>
    );
  }
  if (!status) return null;
  if (!status.enabled || status.logged_in) return <>{children}</>;
  if (!status.ready) return <SetupForm onDone={load} />;
  return <LoginForm onDone={load} />;
}

function useSubmit(action: () => Promise<unknown>, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    action().then(onDone, (e: unknown) => {
      setError(e instanceof ApiError ? e.message : "Server tidak dapat dihubungi. Coba lagi.");
      setBusy(false);
    });
  };
  return { busy, error, submit };
}

function SetupForm({ onDone }: { onDone: () => void }) {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(() => api.auth.setup(token.trim(), password), onDone);

  return (
    <main className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <h1>ZOI — Setup</h1>
        <p className="muted">
          Kata sandi belum dibuat. Salin nilai <code>ZOI_SETUP_TOKEN</code> dari halaman Environment di
          Render, lalu buat kata sandi (minimal 8 karakter).
        </p>
        <label>
          Setup token
          <input value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" required />
        </label>
        <label>
          Kata sandi baru
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="new-password" minLength={8} required />
        </label>
        {error && <p className="notice bad" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Menyimpan…" : "Buat kata sandi"}</button>
      </form>
    </main>
  );
}

function LoginForm({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState("");
  const { busy, error, submit } = useSubmit(() => api.auth.login(password), onDone);

  return (
    <main className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <h1>ZOI</h1>
        <p className="muted">Masukkan kata sandi untuk membuka Command Center.</p>
        <label>
          Kata sandi
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="current-password" required autoFocus />
        </label>
        {error && <p className="notice bad" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Memeriksa…" : "Masuk"}</button>
      </form>
    </main>
  );
}
