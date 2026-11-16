/* Markdown ringan & aman untuk jawaban ZOI (tanpa dependency, tanpa HTML mentah): paragraf, judul, daftar, **tebal**,
   *miring*, `kode`, tautan http(s), dan blok kode dengan penyorotan sederhana + tombol salin. */
import { Check, Copy } from "lucide-react";
import { type ReactNode, useState } from "react";

const KEYWORDS = /\b(?:const|let|var|function|return|if|else|for|while|import|from|export|class|def|async|await|try|except|catch|new|True|False|None|true|false|null|undefined|in|of|as|with|yield|lambda|public|private|static|void|int|string|print)\b/;
const TOKEN = new RegExp(String.raw`(\/\/[^\n]*|#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|${KEYWORDS.source})`, "g");

function highlight(code: string): ReactNode[] {
  return code.split(TOKEN).map((part, i) => {
    if (i % 2 === 0) return part;
    const cls = /^(\/\/|#)/.test(part) ? "tk-c" : /^["']/.test(part) ? "tk-s" : /^\d/.test(part) ? "tk-n" : "tk-k";
    return <span key={i} className={cls}>{part}</span>;
  });
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    } catch { /* clipboard ditolak browser — diam saja */ }
  }
  return (
    <button type="button" className="icon-btn md-copy" aria-label={done ? "Tersalin" : label} title={label} onClick={copy}>
      {done ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;
  let last = 0, m: RegExpExecArray | null, n = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    const k = `${key}-${n++}`;
    if (t.startsWith("`")) out.push(<code key={k}>{t.slice(1, -1)}</code>);
    else if (t.startsWith("**")) out.push(<strong key={k}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("[")) {
      const [, label, href] = /^\[([^\]]+)\]\((.+)\)$/.exec(t) ?? [];
      out.push(<a key={k} href={href} target="_blank" rel="noreferrer noopener">{label}</a>);
    } else out.push(<em key={k}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function blocks(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const k = `${key}-${i}`;
    if (!line.trim()) { i++; continue; }
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) { out.push(<p key={k} className={`md-h md-h${h[1].length}`}>{inline(h[2], k)}</p>); i++; continue; }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const li = items.map((it, j) => <li key={j}>{inline(it, `${k}-${j}`)}</li>);
      out.push(ordered ? <ol key={k}>{li}</ol> : <ul key={k}>{li}</ul>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\s*([-*]|\d+\.)\s+)/.test(lines[i])) para.push(lines[i++]);
    out.push(<p key={k}>{inline(para.join("\n"), k)}</p>);
  }
  return out;
}

export function Markdown({ text }: { text: string }) {
  const parts = text.split(/```/);
  return (
    <div className="md">
      {parts.map((part, i) => {
        if (i % 2 === 0) return <div key={i}>{blocks(part, String(i))}</div>;
        const nl = part.indexOf("\n");
        const lang = nl > 0 ? part.slice(0, nl).trim() : "";
        const code = (nl >= 0 ? part.slice(nl + 1) : part).replace(/\n$/, "");
        return (
          <figure key={i} className="md-code">
            <figcaption>{lang || "kode"} <CopyButton text={code} label="Salin kode" /></figcaption>
            <pre><code>{highlight(code)}</code></pre>
          </figure>
        );
      })}
    </div>
  );
}
