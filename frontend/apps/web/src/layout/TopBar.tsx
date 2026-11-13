import { useApp } from "../stores/appStore";

interface Props {
  onToggleNav(): void;
  onTogglePanel(): void;
  navOpen: boolean;
  panelOpen: boolean;
}

export function TopBar({ onToggleNav, onTogglePanel, navOpen, panelOpen }: Props) {
  const config = useApp((s) => s.config);
  const connected = useApp((s) => s.connected);
  const provider = useApp((s) => s.provider);

  return (
    <header className="topbar">
      <button type="button" className="icon-btn nav-toggle" aria-label="Buka menu" aria-expanded={navOpen}
        onClick={onToggleNav}>☰</button>
      <div className="brand">ZOI<span>Command Center</span></div>
      <select className="channel-select" disabled aria-label="Pilih channel"
        title="Hubungkan channel YouTube tersedia di Phase 6">
        <option>Channel belum terhubung</option>
      </select>
      <div className="status-row">
        {config && <span className={`pill mode-${config.mode}`}>Mode: {config.mode}</span>}
        <span className={`pill ${connected ? "ok" : "bad"}`} data-testid="ws-status">
          {connected ? "Tersambung" : "Terputus"}
        </span>
        {provider && (
          <span className={`pill ${provider.available ? (provider.is_mock ? "warn" : "ok") : "bad"}`}
            title={provider.detail}>
            AI: {provider.is_mock ? "MOCK" : provider.available ? provider.model : "tidak tersedia"}
          </span>
        )}
      </div>
      <button type="button" className="icon-btn panel-toggle" aria-label="Tampilkan panel halaman"
        aria-expanded={panelOpen} onClick={onTogglePanel}>▤</button>
    </header>
  );
}
