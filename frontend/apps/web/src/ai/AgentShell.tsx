import { api, type ConversationInfo } from "@zoi/api-client";
import {
  ArrowLeft, Boxes, Brain, Cpu, ListChecks, Menu, MessageSquarePlus, PanelRight, Settings, Trash2, X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { BottomBar } from "../layout/BottomBar";
import { errorText } from "../lib/youtube";
import { ChatTranscript } from "../pages/ChatTranscript";
import { useApp } from "../stores/appStore";
import { Badge, StatusDot } from "../ui";
import { OfficeStage } from "./OfficeStage";
import "./agent.css";

const LINKS = [
  { to: "/ai/models", label: "AI Models", icon: Cpu },
  { to: "/ai/agents", label: "Agents & Tasks", icon: ListChecks },
  { to: "/ai/memory", label: "Memory & Tools", icon: Brain },
  { to: "/ai/settings", label: "Settings", icon: Settings },
];

function useCompact() {
  const [compact, setCompact] = useState(() => window.matchMedia?.("(max-width: 820px)").matches ?? false);
  useEffect(() => {
    const mq = window.matchMedia?.("(max-width: 820px)");
    if (!mq) return;
    const on = () => setCompact(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return compact;
}

/** Workspace ZOI 3D AI Agent: sidebar percakapan · panggung avatar + chat · panel status opsional. */
export function AgentShell() {
  const [navOpen, setNavOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const banner = useApp((s) => s.config?.banner);
  const connected = useApp((s) => s.connected);
  const location = useLocation();
  const compact = useCompact();
  const onChat = location.pathname === "/ai" || location.pathname === "/assistant";

  return (
    <div className="ai-shell" data-nav-open={navOpen} data-panel-open={panelOpen && onChat}>
      {banner && <div className="dev-banner" role="status" data-testid="dev-banner">{banner}</div>}
      <Sidebar onNavigate={() => setNavOpen(false)} onClose={() => setNavOpen(false)} />
      <div className="uv-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />
      <main className="ai-main">
        <header className="ai-top">
          <button type="button" className="icon-btn ai-menu" aria-label="Buka menu" onClick={() => setNavOpen(true)}>
            <Menu size={18} />
          </button>
          <b>ZOI AI</b>
          <span className={`pill ${connected ? "ok" : "bad"}`} data-testid="ws-status">{connected ? "Tersambung" : "Terputus"}</span>
          <ModelPill />
          {onChat && (
            <button type="button" className="icon-btn ai-panel-btn" aria-label="Panel status" aria-expanded={panelOpen}
              onClick={() => setPanelOpen((v) => !v)}><PanelRight size={18} /></button>
          )}
        </header>
        <OfficeStage compact={compact || !onChat} allowOffice={onChat} />
        {onChat ? <Chat /> : <div className="ai-sub"><Outlet /></div>}
      </main>
      {panelOpen && onChat && <StatusPanel onClose={() => setPanelOpen(false)} />}
    </div>
  );
}

function ModelPill() {
  const provider = useApp((s) => s.provider);
  if (!provider) return null;
  const tone = provider.available ? (provider.is_mock ? "warn" : "ok") : "bad";
  return (
    <Link to="/ai/models" className={`pill ${tone} ai-model`} title={provider.detail}>
      AI: {provider.is_mock ? "MOCK" : provider.available ? provider.model : "tidak tersedia"}
    </Link>
  );
}

function Sidebar({ onNavigate, onClose }: { onNavigate(): void; onClose(): void }) {
  const [list, setList] = useState<ConversationInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const conversationId = useApp((s) => s.conversationId);
  const count = useApp((s) => s.messages.length);
  const navigate = useNavigate();

  useEffect(() => {
    api.conversations().then((r) => setList(r.conversations)).catch(() => undefined);
  }, [conversationId, count]);

  function fresh() {
    useApp.getState().setConversation(null, []);
    navigate("/ai");
    onNavigate();
  }

  async function open(id: string) {
    const [{ messages }, { runs }] = await Promise.all([api.messages(id), api.agent.runs(id)]);
    useApp.getState().setAgentRuns(runs);
    useApp.getState().setConversation(id, messages);
    navigate("/ai");
    onNavigate();
  }

  async function remove(c: ConversationInfo) {
    if (!window.confirm(`Hapus percakapan "${c.title}"? Tindakan ini tidak bisa dibatalkan.`)) return;
    setError(null);
    try {
      await api.deleteConversation(c.id);
      setList((l) => l.filter((x) => x.id !== c.id));
      if (c.id === conversationId) useApp.getState().setConversation(null, []);
    } catch (err) {
      setError(errorText(err, "Percakapan gagal dihapus."));
    }
  }

  return (
    <aside className="ai-side" aria-label="Menu utama">
      <button type="button" className="icon-btn uv-close" aria-label="Tutup menu" onClick={onClose}><X size={18} /></button>
      <button type="button" className="primary ai-new" onClick={fresh}><MessageSquarePlus size={18} aria-hidden="true" /> New Chat</button>
      <p className="uv-group-label">Riwayat</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <ul className="ai-history" data-testid="ai-history">
        {list.length === 0 && <li className="muted">Belum ada percakapan.</li>}
        {list.map((c) => (
          <li key={c.id} className={c.id === conversationId ? "active" : undefined}>
            <button type="button" className="link" onClick={() => open(c.id)}>{c.title}</button>
            {c.is_mock && <span className="badge mock">MOCK</span>}
            <button type="button" className="icon-btn ai-del" aria-label={`Hapus percakapan ${c.title}`} onClick={() => remove(c)}>
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
      <nav className="ai-links" onClick={onNavigate}>
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to}><Icon size={18} aria-hidden="true" />{label}</NavLink>
        ))}
        <Link to="/dashboard" className="ai-back"><ArrowLeft size={18} aria-hidden="true" />Back to ZOI Universe</Link>
      </nav>
    </aside>
  );
}

const SUGGESTIONS = ["Create something", "Analyze a project", "Research a topic", "Generate creative ideas"];

function Chat() {
  const messages = useApp((s) => s.messages);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { void endRef.current?.scrollIntoView?.({ block: "end" }); }, [messages]);

  function suggest(text: string) {
    const input = document.getElementById("chat-input") as HTMLInputElement | null;
    if (!input) return;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  }

  return (
    <>
      <div className="ai-chat">
        {messages.length === 0 ? (
          <div className="ai-greet">
            <h1>Hello, I'm ZOI.</h1>
            <p>Your intelligent AI companion. What would you like to create today?</p>
            <div className="ai-suggest">
              {SUGGESTIONS.map((s) => <button key={s} type="button" onClick={() => suggest(s)}>{s}</button>)}
            </div>
          </div>
        ) : <ChatTranscript messages={messages} />}
        <div ref={endRef} />
      </div>
      <BottomBar />
    </>
  );
}

function StatusPanel({ onClose }: { onClose(): void }) {
  const provider = useApp((s) => s.provider);
  const agent = useApp((s) => s.agent);
  const config = useApp((s) => s.config);
  const tasks = useApp((s) => s.tasks).filter((t) => t.status === "RUNNING" || t.status === "QUEUED").slice(0, 5);
  return (
    <aside className="ai-panel" aria-label="Panel status">
      <header><b>Status</b><button type="button" className="icon-btn" aria-label="Tutup panel" onClick={onClose}><X size={16} /></button></header>
      <h2>Model aktif</h2>
      <p>{provider ? (provider.is_mock ? "MOCK (mode development)" : provider.model || "—") : "Memeriksa…"}</p>
      <p className="muted">Penyedia: {config?.provider ?? "—"}{config?.is_cloud ? " · AI cloud gratis" : ""}</p>
      <p><Link to="/ai/models"><Boxes size={14} aria-hidden="true" /> Kelola model</Link></p>
      <h2>Provider</h2>
      <p><StatusDot tone={provider?.available ? "ok" : "bad"} label={provider?.available ? "Tersedia" : "Tidak tersedia"} /></p>
      {provider?.detail && <p className="muted">{provider.detail}</p>}
      <h2>Aktivitas agen</h2>
      <p><Badge tone="primary">{agent.state}</Badge></p>
      <p className="muted">{agent.reason}</p>
      <h2>Tugas berjalan</h2>
      {tasks.length === 0 ? <p className="muted">Tidak ada.</p> : (
        <ul className="ai-tasks">{tasks.map((t) => <li key={t.id}>{t.name}<progress max={1} value={t.progress} /></li>)}</ul>
      )}
    </aside>
  );
}

export function ModelsHub() {
  const config = useApp((s) => s.config);
  return (
    <section className="page">
      <h1>AI Models</h1>
      <p className="muted">Penyedia aktif: <b>{config?.provider ?? "—"}</b>. Hanya penyedia gratis yang didukung (zero paid API).</p>
      <div className="proj-grid">
        <Link className="ai-card" to="/ai/models/cloud"><b>AI Cloud gratis</b><span>NVIDIA NIM · OpenRouter (:free) — API key, daftar model, uji koneksi.</span></Link>
        <Link className="ai-card" to="/ai/models/local"><b>AI Lokal (Ollama)</b><span>Model di laptop — pilih model aktif, evaluasi, lepas dari memori.</span></Link>
      </div>
    </section>
  );
}
