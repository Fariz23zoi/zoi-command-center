import { api, type CodeProject, type CodeSession, type CodeStep } from "@zoi/api-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import "../artifacts/artifacts.css";
import { errorText } from "../lib/youtube";

const ALAT: Record<string, string> = {
  daftar: "📂 Lihat folder", baca: "📖 Baca", tulis: "✍️ Tulis", ganti: "✏️ Edit", cari: "🔎 Cari",
  jalankan: "▶️ Jalankan", hapus: "🗑️ Hapus",
};

function argsText(step: Pick<CodeStep, "alat" | "args">): string {
  const a = step.args ?? {};
  if (step.alat === "jalankan") return a.perintah ?? "";
  if (step.alat === "tulis") return `${a.path ?? ""}\n${a.isi ?? ""}`;
  if (step.alat === "ganti") return `${a.path ?? ""}\n--- lama\n${a.lama ?? ""}\n+++ baru\n${a.baru ?? ""}`;
  return Object.values(a).join(" ");
}

function Step({ step }: { step: CodeStep }) {
  const cls = `code-step ${step.jenis}${step.gagal ? " gagal" : ""}`;
  if (step.jenis === "pengguna") return <div className={cls}><b>Kamu:</b> {step.teks}</div>;
  if (step.jenis === "selesai") return <div className={cls}><b>ZOI Code:</b> {step.teks}</div>;
  if (step.jenis === "galat") return <div className={cls} role="alert"><b>Berhenti:</b> {step.teks}</div>;
  if (step.jenis === "ditolak") return <div className={cls}>Langkah <b>{step.alat}</b> kamu tolak.</div>;
  if (step.jenis === "aksi") {
    const body = argsText(step);
    return (
      <div className={cls}>
        {step.pikir && <div className="muted">{step.pikir}</div>}
        <b>{ALAT[step.alat ?? ""] ?? step.alat}</b>
        {body && (step.alat === "tulis" || step.alat === "ganti")
          ? <details><summary>{body.split("\n")[0]}</summary><pre>{body.split("\n").slice(1).join("\n")}</pre></details>
          : body && <code> {body}</code>}
      </div>
    );
  }
  return <div className={cls}><details open={step.alat === "jalankan" || !!step.gagal}><summary>Hasil {step.alat}</summary>
    <pre>{step.teks}</pre></details></div>;
}

/** ZOI Code: agen pemrograman ala Claude Code — membaca, menulis, menguji di folder proyek; perintah butuh izin. */
export function CodePage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<CodeProject[]>([]);
  const [project, setProject] = useState("");
  const [newName, setNewName] = useState("");
  const [files, setFiles] = useState<{ path: string; bytes: number }[]>([]);
  const [openFile, setOpenFile] = useState<{ path: string; content: string; dirty: boolean } | null>(null);
  const [session, setSession] = useState<CodeSession | null>(null);
  const [perintah, setPerintah] = useState("");
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const active = session?.status === "running" || session?.status === "waiting";

  const loadProjects = useCallback(() => {
    api.code.projects().then((r) => {
      setProjects(r.items);
      setProject((cur) => cur || r.items[0]?.name || "");
    }, (e) => setError(errorText(e, "Gagal memuat proyek.")));
  }, []);
  useEffect(loadProjects, [loadProjects]);

  const loadFiles = useCallback(() => {
    if (project) api.code.files(project).then((r) => setFiles(r.items), () => setFiles([]));
  }, [project]);
  useEffect(loadFiles, [loadFiles]);

  function changeProject(name: string) {
    setProject(name);
    setFiles([]);
    setOpenFile(null);
    setSession(null);
  }

  // Polling sesi selama agen bekerja.
  useEffect(() => {
    if (!session || !active) return;
    const timer = setInterval(() => {
      api.code.session(session.id).then((s) => {
        if (s.steps.length !== session.steps.length || s.status !== session.status) loadFiles();
        setSession(s);
      }, () => undefined);
    }, 1000);
    return () => clearInterval(timer);
  }, [session, active, loadFiles]);

  const stepCount = session?.steps.length ?? 0;
  useEffect(() => { const el = logRef.current; if (el && stepCount) el.scrollTop = el.scrollHeight; }, [stepCount]);

  async function create() {
    setError(null);
    try {
      const p = await api.code.create(newName);
      setNewName("");
      changeProject(p.name);
      loadProjects();
    } catch (err) { setError(errorText(err, "Gagal membuat proyek.")); }
  }

  async function send() {
    setError(null);
    try {
      const resume = session && !active ? session.id : undefined;
      setSession(await api.code.start(project, perintah.trim(), resume));
      setPerintah("");
    } catch (err) { setError(errorText(err, "Gagal memulai.")); }
  }

  async function open(path: string) {
    try {
      const f = await api.code.file(project, path);
      setOpenFile({ path, content: f.binary ? "(file biner — tidak ditampilkan)" : f.content, dirty: false });
    } catch (err) { setError(errorText(err, "File tidak bisa dibuka.")); }
  }

  async function asArtifact(path: string) {
    try {
      const f = await api.code.file(project, path);
      const saved = await api.artifacts.upload(f.content, `${project}/${path}`);
      navigate(`/artefak/${saved.id}`);
    } catch (err) { setError(errorText(err, "Gagal membuat artefak.")); }
  }

  const htmlFiles = files.filter((f) => /\.html?$/i.test(f.path));
  return (
    <section className="page code-page" data-testid="code-page">
      <h1>Code</h1>
      <p className="muted">
        ZOI Code menulis, mengedit, dan menguji kode di folder proyek ZOI (bukan di folder lain). Baca/tulis file
        berjalan otomatis (ada cadangan), tetapi <b>menjalankan perintah dan menghapus file selalu minta izinmu</b>.
      </p>
      {error && <p className="notice bad" role="alert">{error}</p>}
      <div className="code-grid">
        <aside className="code-side">
          <label htmlFor="code-proj">Proyek</label>
          <select id="code-proj" value={project} disabled={active} onChange={(e) => changeProject(e.target.value)}>
            {projects.length === 0 && <option value="">(belum ada)</option>}
            {projects.map((p) => <option key={p.name} value={p.name}>{p.name} · {p.files} file</option>)}
          </select>
          <div className="art-row">
            <input type="text" value={newName} placeholder="nama-proyek-baru" aria-label="Nama proyek baru"
                   data-testid="code-new-name" onChange={(e) => setNewName(e.target.value)} />
            <button type="button" disabled={!newName.trim()} onClick={create}>+ Proyek</button>
          </div>
          {project && (
            <>
              <h2>File</h2>
              {files.length === 0 ? <p className="empty">Folder kosong.</p> : (
                <ul className="code-files" data-testid="code-files">
                  {files.map((f) => (
                    <li key={f.path}>
                      <button type="button" aria-current={openFile?.path === f.path} onClick={() => open(f.path)}>{f.path}</button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="art-row">
                <a className="button" href={api.code.zipUrl(project)}>Unduh ZIP</a>
                {htmlFiles.slice(0, 1).map((f) => (
                  <button key={f.path} type="button" onClick={() => asArtifact(f.path)}>▶ Pratinjau {f.path}</button>
                ))}
                <button type="button" className="ghost" disabled={active} onClick={() => {
                  if (window.confirm(`Hapus proyek "${project}" beserta semua filenya?`)) {
                    api.code.remove(project).then(() => { changeProject(""); loadProjects(); }, (e) => setError(errorText(e, "Gagal.")));
                  }
                }}>Hapus proyek</button>
              </div>
            </>
          )}
        </aside>

        <div className="code-main">
          {openFile && (
            <div className="code-file">
              <div className="art-row"><b>{openFile.path}</b>
                <button type="button" disabled={!openFile.dirty} onClick={() =>
                  api.code.save(project, openFile.path, openFile.content).then(() => { setOpenFile({ ...openFile, dirty: false }); loadFiles(); },
                    (e) => setError(errorText(e, "Gagal menyimpan.")))}>Simpan</button>
                <button type="button" className="ghost" onClick={() => setOpenFile(null)}>Tutup</button>
              </div>
              <textarea className="code-editor" rows={14} value={openFile.content} spellCheck={false} aria-label="Isi file"
                        onChange={(e) => setOpenFile({ ...openFile, content: e.target.value, dirty: true })} />
            </div>
          )}

          <div className="code-log" ref={logRef} data-testid="code-log" aria-live="polite">
            {!session && <p className="empty">Tulis tugas untuk ZOI Code, mis. “buat halaman HTML kalkulator BMI lalu
              uji”, atau “perbaiki error di main.py”.</p>}
            {session?.steps.map((s, i) => <Step key={i} step={s} />)}
            {session?.status === "running" && <p className="muted">ZOI Code bekerja…{session.provider ? ` (${session.provider})` : ""}</p>}
          </div>

          {session?.status === "waiting" && session.pending && (
            <div className="code-approve" role="alertdialog" aria-label="Minta izin" data-testid="code-approve">
              <b>ZOI Code minta izin: {ALAT[session.pending.alat] ?? session.pending.alat}</b>
              <pre>{argsText(session.pending)}</pre>
              <div className="art-row">
                <button type="button" className="primary" data-testid="code-allow"
                        onClick={() => api.code.decide(session.id, true).then(setSession)}>Izinkan sekali</button>
                <button type="button" onClick={() => api.code.decide(session.id, true, true).then(setSession)}>
                  Izinkan semua di sesi ini</button>
                <button type="button" onClick={() => api.code.decide(session.id, false).then(setSession)}>Tolak</button>
              </div>
            </div>
          )}

          <label htmlFor="code-cmd">{session && !active ? "Lanjutkan percakapan" : "Tugas untuk ZOI Code"}</label>
          <textarea id="code-cmd" rows={3} value={perintah} maxLength={8000} disabled={!project || active}
                    data-testid="code-input" placeholder={project ? "Contoh: buat skrip Python yang merapikan nama file di folder ini" : "Buat proyek dulu"}
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && perintah.trim()) void send(); }}
                    onChange={(e) => setPerintah(e.target.value)} />
          <div className="art-row">
            <button type="button" className="primary" data-testid="code-send" disabled={!project || active || !perintah.trim()}
                    onClick={send}>Kirim (Ctrl+Enter)</button>
            {active && session && <button type="button" onClick={() => api.code.stop(session.id).then(setSession)}>■ Hentikan</button>}
            {session && !active && <button type="button" className="ghost" onClick={() => setSession(null)}>Sesi baru</button>}
          </div>
        </div>
      </div>
    </section>
  );
}
