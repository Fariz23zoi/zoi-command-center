import { NavLink } from "react-router-dom";

import { MENU } from "../menu";

export function SideNav({ open, onNavigate }: { open: boolean; onNavigate(): void }) {
  return (
    <nav className="sidenav" data-open={open} aria-label="Menu utama">
      <ul>
        {MENU.map((item) => (
          <li key={item.path}>
            <NavLink to={item.path} end={item.path === "/"} onClick={onNavigate}>
              <span>{item.label}</span>
              {!item.ready && <small className="phase-tag">P{item.phase}</small>}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
