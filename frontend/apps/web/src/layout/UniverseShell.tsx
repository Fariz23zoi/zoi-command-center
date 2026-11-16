import {
  Activity, BarChart3, Bot, Brain, ChevronRight, Clapperboard, Compass, Flame, Gauge, Home, LayoutDashboard,
  Lightbulb, ListChecks, type LucideIcon, Menu, PenLine, Scissors, Settings, Sparkles, Stethoscope, TrendingUp, Users,
  Wallet, Workflow, X,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { GROUP_LABEL, MENU, type MenuGroup } from "../menu";
import { useApp } from "../stores/appStore";
import { StatusDot } from "../ui";
import "./universe.css";

const ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard, "/ai": Bot, "/tasks": ListChecks, "/memory": Brain,
  "/analytics": BarChart3, "/competitors": Users, "/viral": Flame, "/trends": TrendingUp, "/performance": Gauge,
  "/monetization": Wallet, "/ideas": Lightbulb, "/script": PenLine, "/production": Clapperboard,
  "/automation": Workflow, "/clipper": Scissors, "/blueprint": Compass, "/diagnostics": Stethoscope,
  "/settings": Settings,
};

const ORDER: MenuGroup[] = ["main", "analytics", "creation", "products", "system"];

/** Kerangka ZOI Universe: sidebar berkelompok + topbar status. Chat & avatar ada di workspace terpisah (/ai). */
export function UniverseShell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const banner = useApp((s) => s.config?.banner);
  const current = MENU.find((m) => location.pathname === m.path || location.pathname.startsWith(`${m.path}/`));

  return (
    <div className="uv-shell" data-nav-open={open}>
      {banner && <div className="dev-banner" role="status" data-testid="dev-banner">{banner}</div>}
      <aside className="uv-side" aria-label="Menu utama">
        <Link to="/" className="uv-brand" aria-label="ZOI Universe — beranda">
          <span className="uv-logo" aria-hidden="true">Z</span>
          <span><b>ZOI UNIVERSE</b><small>AI Creative Ecosystem</small></span>
        </Link>
        <button type="button" className="icon-btn uv-close" aria-label="Tutup menu" onClick={() => setOpen(false)}>
          <X size={18} />
        </button>
        <nav onClick={() => setOpen(false)}>
          {ORDER.map((group) => (
            <div key={group} className="uv-group">
              {GROUP_LABEL[group] && <p className="uv-group-label">{GROUP_LABEL[group]}</p>}
              <ul>
                {MENU.filter((m) => m.group === group).map((item) => {
                  const Icon = ICONS[item.path] ?? Sparkles;
                  return (
                    <li key={item.path}>
                      <NavLink to={item.path} title={item.description}>
                        <Icon size={18} aria-hidden="true" />
                        <span>{item.label}</span>
                        {!item.ready && <small className="phase-tag">soon</small>}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
      <div className="uv-scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="uv-main">
        <TopBar title={current?.label ?? "ZOI"} onMenu={() => setOpen(true)} />
        <main className="uv-content" id="konten">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function TopBar({ title, onMenu }: { title: string; onMenu(): void }) {
  const config = useApp((s) => s.config);
  const connected = useApp((s) => s.connected);
  const provider = useApp((s) => s.provider);
  const aiTone = !provider ? "neutral" : provider.available ? (provider.is_mock ? "warn" : "ok") : "bad";
  const aiText = !provider ? "AI: memeriksa…" : provider.is_mock ? "AI: MOCK"
    : provider.available ? "AI Terhubung" : "AI tidak tersedia";

  return (
    <header className="uv-top">
      <button type="button" className="icon-btn uv-menu" aria-label="Buka menu" onClick={onMenu}>
        <Menu size={18} />
      </button>
      <nav className="uv-crumb" aria-label="Lokasi">
        <Link to="/" aria-label="Beranda"><Home size={16} /></Link>
        <ChevronRight size={14} aria-hidden="true" />
        <span>{title}</span>
      </nav>
      <div className="uv-top-right">
        {config && <span className={`pill mode-${config.mode}`}>Mode: {config.mode}</span>}
        <span className={`pill ${connected ? "ok" : "bad"}`} data-testid="ws-status">
          {connected ? "Tersambung" : "Terputus"}
        </span>
        <span title={provider?.detail}><StatusDot tone={aiTone} label={aiText} /></span>
        <Link to="/ai" className="uv-open-ai"><Activity size={16} aria-hidden="true" />Open ZOI AI</Link>
      </div>
    </header>
  );
}
