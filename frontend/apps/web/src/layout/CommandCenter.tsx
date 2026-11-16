import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { BottomBar } from "./BottomBar";
import { CenterStage } from "./CenterStage";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import { useApp } from "../stores/appStore";

/** Tata letak 5 zona: TOP status · LEFT navigasi · CENTER avatar & percakapan · RIGHT halaman · BOTTOM chat. */
export function CommandCenter() {
  const banner = useApp((s) => s.config?.banner);
  const [navOpen, setNavOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const location = useLocation();

  return (
    <div className="shell" data-nav-open={navOpen} data-panel-open={panelOpen}>
      {banner && (
        <div className="dev-banner" role="status" data-testid="dev-banner">
          {banner}
        </div>
      )}
      <TopBar
        onToggleNav={() => setNavOpen((v) => !v)}
        onTogglePanel={() => setPanelOpen((v) => !v)}
        navOpen={navOpen}
        panelOpen={panelOpen}
      />
      <div className="workspace">
        <SideNav open={navOpen} onNavigate={() => setNavOpen(false)} />
        <main className="center" aria-label="Avatar dan percakapan">
          <CenterStage />
          <BottomBar />
        </main>
        <aside className="panel" aria-label="Panel halaman" hidden={!panelOpen} key={location.pathname}>
          <Outlet />
        </aside>
      </div>
    </div>
  );
}
