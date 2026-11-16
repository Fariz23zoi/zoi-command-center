/* Komponen dasar design system ZOI Universe V2. Ringan: tanpa library UI, ikon dari lucide-react (ISC). */
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import "./ui.css";

type Tone = "neutral" | "primary" | "ok" | "warn" | "bad" | "info";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`zui-badge zui-${tone}`}>{children}</span>;
}

export function StatusDot({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className={`zui-status zui-${tone}`}>
      <i aria-hidden="true" />
      {label}
    </span>
  );
}

interface CardProps {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Sorotan gradien lembut — pakai seperlunya. */
  highlight?: boolean;
}

export function Card({ title, action, children, className = "", highlight }: CardProps) {
  return (
    <section className={`zui-card${highlight ? " zui-card-hl" : ""} ${className}`.trim()}>
      {(title || action) && (
        <header className="zui-card-head">
          {title && <h3>{title}</h3>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

interface StatProps {
  label: string;
  icon: LucideIcon;
  /** `null` = data belum tersedia → ditampilkan "—", tidak pernah angka contoh. */
  value: string | null;
  delta?: { text: string; up: boolean } | null;
  hint?: string;
  tone?: Exclude<Tone, "neutral">;
}

export function StatCard({ label, icon: Icon, value, delta, hint, tone = "primary" }: StatProps) {
  return (
    <div className={`zui-stat zui-${tone}`}>
      <span className="zui-stat-icon" aria-hidden="true">
        <Icon size={20} />
      </span>
      <div>
        <p className="zui-stat-label">{label}</p>
        <p className="zui-stat-value">
          {value ?? "—"}
          {value && delta && <small className={delta.up ? "zui-up" : "zui-down"}>{delta.up ? "▲" : "▼"} {delta.text}</small>}
        </p>
        {hint && <p className="zui-stat-hint">{hint}</p>}
      </div>
    </div>
  );
}

interface EmptyProps {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, children, action }: EmptyProps) {
  return (
    <div className="zui-empty">
      <Icon size={28} aria-hidden="true" />
      <p className="zui-empty-title">{title}</p>
      {children && <p className="zui-empty-body">{children}</p>}
      {action}
    </div>
  );
}
