import { ArrowRight, Bot, Compass, Cpu, FlaskConical, ExternalLink as Github, HardDrive, Lock, Menu, Scissors, ShieldCheck, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

import { GITHUB_URL, PRODUCTS, type Product, STATUS_TONE } from "../../products";
import { useApp } from "../../stores/appStore";
import { Badge } from "../../ui";
import "./public.css";

const ICON = { "ai-agent": Bot, clipper: Scissors, blueprint: Compass, "ai-lab": FlaskConical } as const;
const NAV = [["/about", "About"], ["/products", "AI Products"], ["/technology", "Technology"], ["/contact", "Contact"]] as const;

/** Kerangka halaman publik ZOI Universe (landing, about, products, technology, contact). Tanpa three.js. */
export function PublicLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="pub">
      <header className="pub-top">
        <Link to="/" className="pub-brand"><span className="uv-logo" aria-hidden="true">Z</span><b>ZOI UNIVERSE</b></Link>
        <button type="button" className="icon-btn pub-menu" aria-label={open ? "Tutup menu" : "Buka menu"}
          aria-expanded={open} onClick={() => setOpen((v) => !v)}>{open ? <X size={18} /> : <Menu size={18} />}</button>
        <nav className="pub-nav" data-open={open} aria-label="Navigasi situs" onClick={() => setOpen(false)}>
          {NAV.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          <Link to="/dashboard" className="pub-ghost">Dashboard</Link>
          <Link to="/ai" className="pub-cta">Open ZOI AI</Link>
        </nav>
      </header>
      <main><Outlet /></main>
      <footer className="pub-foot">
        <span>ZOI Universe — local-first, open source, zero paid API.</span>
        <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener"><Github size={16} aria-hidden="true" /> GitHub</a>
      </footer>
    </div>
  );
}

/** Bola bercahaya + partikel melayang (canvas 2D, ±30 fps, berhenti saat tab tersembunyi / reduced motion). */
function HeroOrb() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dots = Array.from({ length: 70 }, (_, i) => ({ a: (i * 2.399) % (Math.PI * 2), r: 0.32 + ((i * 37) % 60) / 100,
      s: 0.15 + ((i * 13) % 10) / 40, z: ((i * 7) % 10) / 10 }));
    let raf = 0, last = 0;
    const draw = (t: number) => {
      raf = requestAnimationFrame(draw);
      if (document.hidden || t - last < 33) return;
      last = t;
      const size = canvas.clientWidth;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      if (canvas.width !== size * dpr) { canvas.width = size * dpr; canvas.height = size * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);
      const c = size / 2;
      const glow = ctx.createRadialGradient(c - size * 0.06, c - size * 0.08, size * 0.02, c, c, size * 0.3);
      glow.addColorStop(0, "#f1e9ff"); glow.addColorStop(0.35, "#8b5cf6"); glow.addColorStop(1, "rgba(49,46,129,0)");
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(c, c, size * 0.3, 0, Math.PI * 2); ctx.fill();
      for (const d of dots) {
        const ang = d.a + (still ? 0 : (t / 1000) * d.s);
        const x = c + Math.cos(ang) * d.r * c, y = c + Math.sin(ang) * d.r * c * 0.55;
        ctx.fillStyle = `rgba(167,139,250,${0.25 + d.z * 0.6})`;
        ctx.beginPath(); ctx.arc(x, y, 1 + d.z * 1.6, 0, Math.PI * 2); ctx.fill();
      }
      if (still) cancelAnimationFrame(raf);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas ref={ref} className="pub-orb" aria-hidden="true" />;
}

export function LandingPage() {
  return (
    <>
      <section className="pub-hero">
        <div>
          <p className="pub-eyebrow"><Sparkles size={14} aria-hidden="true" /> AI Creative Ecosystem</p>
          <h1>Explore the Future with ZOI.</h1>
          <p className="pub-lead">An intelligent ecosystem connecting AI, creativity, and technology.</p>
          <div className="pub-actions">
            <Link to="/dashboard" className="pub-cta">Explore Universe <ArrowRight size={18} aria-hidden="true" /></Link>
            <Link to="/ai" className="pub-ghost">Open ZOI AI</Link>
          </div>
        </div>
        <HeroOrb />
      </section>
      <AboutSection />
      <ProductsSection heading="Featured Products" />
      <TechnologySection />
      <FutureSection />
      <ContactSection />
    </>
  );
}

function AboutSection() {
  return (
    <section className="pub-section" id="about">
      <h2>About ZOI Universe</h2>
      <p className="pub-lead">ZOI adalah ekosistem AI pribadi untuk kreator YouTube: riset, analitik, ide, naskah, dan produksi —
        dalam satu tempat, berjalan di laptopmu sendiri.</p>
      <div className="pub-grid3">
        <article><HardDrive aria-hidden="true" /><h3>Local-first</h3><p>Data dan AI berjalan di perangkatmu. Bisa dipakai offline; akses dari HP lewat jaringan pribadi.</p></article>
        <article><Lock aria-hidden="true" /><h3>Zero paid API</h3><p>Hanya model gratis dan open-source. Tidak ada langganan, tidak ada kartu kredit.</p></article>
        <article><ShieldCheck aria-hidden="true" /><h3>Data jujur</h3><p>Angka selalu dari YouTube API resmi. Tidak ada statistik contoh yang terlihat seperti asli.</p></article>
      </div>
    </section>
  );
}

function ProductCard({ product }: { product: Product }) {
  const adapters = useApp((s) => s.adapters);
  const Icon = ICON[product.id as keyof typeof ICON] ?? Sparkles;
  const adapter = product.adapter ? adapters.find((a) => a.name === product.adapter) : undefined;
  return (
    <article className="pub-product" data-testid={`product-${product.id}`}>
      <span className="pub-product-icon" aria-hidden="true"><Icon size={24} /></span>
      <h3>{product.name}</h3>
      <p className="muted">{product.tagline}</p>
      <p>{product.description}</p>
      <p><Badge tone={STATUS_TONE[product.status]}>{product.statusNote}</Badge>
        {adapter && <small className="muted"> · {adapter.found ? "terdeteksi di perangkat ini" : "tidak terdeteksi di perangkat ini"}</small>}</p>
      <div className="pub-product-actions">
        {product.open ? <Link to={product.open} className="pub-cta">Open</Link> : <span className="pub-ghost" aria-disabled="true">Belum tersedia</span>}
        <Link to={`/products/${product.id}`} className="pub-ghost">Detail</Link>
      </div>
    </article>
  );
}

function ProductsSection({ heading }: { heading: string }) {
  return (
    <section className="pub-section" id="products">
      <h2>{heading}</h2>
      <div className="pub-products">{PRODUCTS.map((p) => <ProductCard key={p.id} product={p} />)}</div>
    </section>
  );
}

function TechnologySection() {
  const stack = [
    ["AI Brain", "Ollama (lokal) · NVIDIA NIM & OpenRouter (model gratis) — lewat adapter provider modular"],
    ["Backend", "Python · FastAPI · SQLite · Alembic"],
    ["Frontend", "React · TypeScript · Vite · Three.js"],
    ["Suara", "Faster-Whisper (STT) · Piper (TTS) — di perangkat"],
    ["Video", "FFmpeg · HyperFrames (opsional)"],
    ["Data", "YouTube Data API v3 & YouTube Analytics API (OAuth resmi)"],
  ];
  return (
    <section className="pub-section" id="technology">
      <h2><Cpu size={22} aria-hidden="true" /> Technology Ecosystem</h2>
      <dl className="pub-stack">{stack.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    </section>
  );
}

function FutureSection() {
  return (
    <section className="pub-section">
      <h2>Future Development</h2>
      <ul className="pub-future">
        <li>Lip-sync avatar dari audio jawaban.</li>
        <li>ZOI AI Lab — ruang eksperimen model dan agen.</li>
        <li>Provider AI gratis tambahan lewat adapter OpenAI-compatible.</li>
      </ul>
    </section>
  );
}

function ContactSection() {
  return (
    <section className="pub-section" id="contact">
      <h2>Contact</h2>
      <p className="pub-lead">ZOI dikembangkan secara terbuka. Hubungi lewat GitHub.</p>
      <a className="pub-cta" href={GITHUB_URL} target="_blank" rel="noreferrer noopener"><Github size={18} aria-hidden="true" /> github.com/Fariz23zoi</a>
    </section>
  );
}

const page = (title: string, body: React.ReactNode) => <><h1 className="pub-title">{title}</h1>{body}</>;
export const AboutPage = () => page("About ZOI", <AboutSection />);
export const ProductsPage = () => page("AI Products", <ProductsSection heading="Semua produk" />);
export const TechnologyPage = () => page("Technology", <><TechnologySection /><FutureSection /></>);
export const ContactPage = () => page("Contact", <ContactSection />);

export function ProductDetailPage() {
  const { id } = useParams();
  const product = PRODUCTS.find((p) => p.id === id);
  if (!product) return page("Produk tidak ditemukan", <p className="pub-section"><Link to="/products">Lihat semua produk</Link></p>);
  return page(product.name, <section className="pub-section"><div className="pub-products one"><ProductCard product={product} /></div></section>);
}
