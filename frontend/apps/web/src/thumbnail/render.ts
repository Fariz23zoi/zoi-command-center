/**
 * Penyusun thumbnail di canvas browser: foto latar + teks hook di potongan kertas + coretan aksen.
 * Tanpa model gambar dan tanpa unggah foto. Gaya (posisi, kemiringan, coretan) ditentukan `seed`,
 * jadi "Acak gaya" cukup mengganti seed.
 */
export type Ukuran = "kecil" | "sedang" | "besar";
export type Warna = "hitam" | "putih" | "pink" | "kuning";
export type Kotak = "putih" | "kuning" | "hitam" | "tanpa";
export type Rasio = "9:16" | "16:9";

export interface HookLine { teks: string; ukuran: Ukuran; warna: Warna; kotak: Kotak }
export interface ThumbSpec {
  baris: HookLine[]; bubble: string[]; aksen: "pink" | "kuning"; rasio: Rasio; seed: number;
  /** Letak blok teks; "bawah" bila wajah/subjek ada di atas foto. */
  posisi?: "atas" | "bawah";
  /** Titik fokus foto latar 0..1 (vertikal untuk 9:16, horizontal untuk 16:9). */
  fokus?: number;
}
export interface Background { source: CanvasImageSource; width: number; height: number }

export const SIZE: Record<Rasio, [number, number]> = { "9:16": [1080, 1920], "16:9": [1280, 720] };
export const COLOR: Record<Warna | Kotak, string> = {
  hitam: "#121212", putih: "#ffffff", pink: "#ff2d6f", kuning: "#ffd21f", tanpa: "transparent",
};
const FONT_BIG = "ZoiLuckiest";
const FONT_BODY = "ZoiMarker";
const SCALE: Record<Ukuran, number> = { kecil: 0.062, sedang: 0.08, besar: 0.165 };

let fontsReady: Promise<boolean> | null = null;
/** Muat font lokal (Apache-2.0, ada di /fonts). Gagal → canvas memakai font cadangan. */
export function loadFonts(): Promise<boolean> {
  if (fontsReady) return fontsReady;
  fontsReady = (async () => {
    if (typeof FontFace === "undefined" || typeof document === "undefined" || !document.fonts) return false;
    try {
      const faces = [new FontFace(FONT_BIG, "url(/fonts/LuckiestGuy-Regular.ttf)"),
        new FontFace(FONT_BODY, "url(/fonts/PermanentMarker-Regular.ttf)")];
      for (const face of await Promise.all(faces.map((f) => f.load()))) document.fonts.add(face);
      return true;
    } catch {
      return false;
    }
  })();
  return fontsReady;
}

/** Pembangkit acak deterministik (mulberry32). */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fontFor(line: HookLine, size: number): string {
  return line.ukuran === "besar" ? `${size}px ${FONT_BIG}, Impact, sans-serif` : `${size}px ${FONT_BODY}, "Comic Sans MS", sans-serif`;
}

function drawBackground(ctx: CanvasRenderingContext2D, W: number, H: number, bg: Background | null, rasio: Rasio,
  fokus: number, bawah: boolean) {
  if (bg) {
    const s = Math.max(W / bg.width, H / bg.height);
    const w = bg.width * s, h = bg.height * s;
    ctx.drawImage(bg.source, (W - w) * fokus, (H - h) * fokus, w, h);
  } else {
    const g = ctx.createRadialGradient(W * 0.5, H * 0.45, 10, W * 0.5, H * 0.5, Math.max(W, H) * 0.75);
    g.addColorStop(0, "#3a3a42");
    g.addColorStop(1, "#0d0d10");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "rgba(255,255,255,0.05)";
    ctx.lineWidth = 2;
    for (let x = 0; x < W; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  }
  // Bayangan lembut di area teks agar tetap terbaca di foto terang.
  const shade = rasio !== "9:16" ? ctx.createLinearGradient(0, 0, W * 0.65, 0)
    : bawah ? ctx.createLinearGradient(0, H, 0, H * 0.38) : ctx.createLinearGradient(0, 0, 0, H * 0.62);
  shade.addColorStop(0, "rgba(0,0,0,0.38)");
  shade.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = shade;
  ctx.fillRect(0, 0, W, H);
}

/** Kotak kertas sobek di sekitar persegi (x,y,w,h). */
function tornPaper(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: () => number, color: string) {
  const step = Math.max(14, h * 0.28), jag = h * 0.07;
  const pts: [number, number][] = [];
  for (let px = x; px < x + w; px += step) pts.push([px, y + (r() - 0.5) * jag * 2]);
  for (let py = y; py < y + h; py += step) pts.push([x + w + (r() - 0.5) * jag * 2, py]);
  for (let px = x + w; px > x; px -= step) pts.push([px, y + h + (r() - 0.5) * jag * 2]);
  for (let py = y + h; py > y; py -= step) pts.push([x + (r() - 0.5) * jag * 2, py]);
  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,0.35)";
  ctx.shadowBlur = h * 0.12;
  ctx.shadowOffsetY = h * 0.04;
  ctx.fillStyle = color;
  ctx.beginPath();
  pts.forEach(([px, py], i) => (i ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function brushStroke(ctx: CanvasRenderingContext2D, x1: number, y: number, x2: number, width: number, color: string, r: () => number) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineCap = "round";
  for (let i = 0; i < 2; i += 1) {
    ctx.lineWidth = width * (1 - i * 0.45);
    ctx.globalAlpha = 0.95 - i * 0.25;
    ctx.beginPath();
    ctx.moveTo(x1, y + (r() - 0.5) * width);
    ctx.quadraticCurveTo((x1 + x2) / 2, y - width * (0.6 + r() * 0.6), x2, y + (r() - 0.5) * width);
    ctx.stroke();
  }
  ctx.restore();
}

function burst(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, angle: number, color: string) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineCap = "round";
  ctx.lineWidth = Math.max(4, size * 0.09);
  for (let i = -1; i <= 1; i += 1) {
    const a = angle + i * 0.5;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * size * 0.35, cy + Math.sin(a) * size * 0.35);
    ctx.lineTo(cx + Math.cos(a) * size, cy + Math.sin(a) * size);
    ctx.stroke();
  }
  ctx.restore();
}

function sparkle(ctx: CanvasRenderingContext2D, cx: number, cy: number, s: number, color: string) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(3, s * 0.12);
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(cx, cy - s);
  ctx.quadraticCurveTo(cx, cy, cx + s, cy);
  ctx.quadraticCurveTo(cx, cy, cx, cy + s);
  ctx.quadraticCurveTo(cx, cy, cx - s, cy);
  ctx.quadraticCurveTo(cx, cy, cx, cy - s);
  ctx.stroke();
  ctx.restore();
}

function wrapWords(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const out: string[] = [];
  let cur = "";
  for (const word of text.split(" ")) {
    const next = cur ? `${cur} ${word}` : word;
    if (cur && ctx.measureText(next).width > maxW) { out.push(cur); cur = word; } else cur = next;
  }
  if (cur) out.push(cur);
  return out;
}

function bubble(ctx: CanvasRenderingContext2D, text: string, cx: number, cy: number, unit: number, tailLeft: boolean) {
  let size = unit * 0.05;
  ctx.font = `${size}px ${FONT_BODY}, sans-serif`;
  let lines = wrapWords(ctx, text.toUpperCase(), unit * 0.24);
  const widest = () => Math.max(...lines.map((l) => ctx.measureText(l).width));
  while (widest() > unit * 0.26 && size > unit * 0.03) {
    size *= 0.9;
    ctx.font = `${size}px ${FONT_BODY}, sans-serif`;
    lines = wrapWords(ctx, text.toUpperCase(), unit * 0.24);
  }
  const rx = widest() / 2 + size * 0.9, ry = (lines.length * size * 1.1) / 2 + size * 0.7;
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.strokeStyle = "#121212";
  ctx.lineWidth = Math.max(4, size * 0.12);
  ctx.beginPath();
  const tx = tailLeft ? cx - rx * 0.4 : cx + rx * 0.4;
  ctx.moveTo(tx - size * 0.5, cy + ry * 0.85);
  ctx.lineTo(tx + (tailLeft ? -size : size) * 1.1, cy + ry + size * 1.1);
  ctx.lineTo(tx + size * 0.5, cy + ry * 0.85);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#121212";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((l, i) => ctx.fillText(l, cx, cy + (i - (lines.length - 1) / 2) * size * 1.1));
  ctx.restore();
}

/** Gambar thumbnail lengkap ke canvas berukuran SIZE[spec.rasio]. */
export function drawThumbnail(ctx: CanvasRenderingContext2D, spec: ThumbSpec, bg: Background | null): void {
  const [W, H] = SIZE[spec.rasio];
  const r = rng(spec.seed);
  const vertical = spec.rasio === "9:16";
  const unit = vertical ? W : H * 1.15;
  const left = W * (vertical ? 0.06 : 0.05);
  const maxW = W * (vertical ? 0.88 : 0.58);
  const top = H * (vertical ? 0.05 : 0.08);
  const room = H * (vertical ? 0.6 : 0.84);
  const aksen = COLOR[spec.aksen];
  const lain = spec.aksen === "pink" ? COLOR.kuning : COLOR.pink;

  ctx.save();
  ctx.clearRect(0, 0, W, H);
  const bawah = spec.posisi === "bawah";
  drawBackground(ctx, W, H, bg, spec.rasio, Math.min(1, Math.max(0, spec.fokus ?? 0.5)), bawah);
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";

  // Ukuran tiap baris: sesuai kelasnya, diperkecil bila terlalu lebar / terlalu tinggi totalnya.
  const lines = spec.baris.filter((l) => l.teks.trim());
  const sizes = lines.map((line) => {
    let size = unit * SCALE[line.ukuran];
    ctx.font = fontFor(line, size);
    const pad = line.kotak === "tanpa" ? size * 0.1 : size * 0.7;
    const w = ctx.measureText(line.ukuran === "besar" ? line.teks.toUpperCase() : line.teks).width + pad;
    if (w > maxW) size *= maxW / w;
    return size;
  });
  const gap = (s: number) => s * 0.42;
  const total = sizes.reduce((a, s) => a + s * 1.05 + gap(s), 0);
  const shrink = total > room ? room / total : 1;

  let y = bawah ? H * (vertical ? 0.95 : 0.92) - Math.min(total, room) : top;
  lines.forEach((line, i) => {
    const size = sizes[i] * shrink;
    const text = line.ukuran === "besar" ? line.teks.toUpperCase() : line.teks;
    ctx.font = fontFor(line, size);
    const tw = ctx.measureText(text).width;
    const padX = line.kotak === "tanpa" ? 0 : size * 0.35;
    const boxW = tw + padX * 2;
    const free = Math.max(0, maxW - boxW);
    const x = left + (vertical ? free * (0.15 + r() * 0.7) : free * r() * 0.35);
    const cy = y + size * 0.55;
    const tilt = ((r() - 0.5) * (line.ukuran === "besar" ? 7 : 5) * Math.PI) / 180;

    ctx.save();
    ctx.translate(x + boxW / 2, cy);
    ctx.rotate(tilt);
    ctx.translate(-(x + boxW / 2), -cy);
    if (line.kotak !== "tanpa") tornPaper(ctx, x, cy - size * 0.62, boxW, size * 1.2, r, COLOR[line.kotak]);
    if (line.ukuran === "besar") {
      brushStroke(ctx, x + size * 0.1, cy + size * 0.62, x + boxW - size * 0.1, size * 0.13,
        line.warna === "kuning" ? COLOR.pink : COLOR.kuning, r);
    }
    const textY = cy + (line.ukuran === "besar" ? size * 0.06 : size * 0.04);
    if (line.kotak === "tanpa") {
      ctx.lineJoin = "round";
      ctx.shadowColor = "rgba(0,0,0,0.45)";
      ctx.shadowBlur = size * 0.12;
      ctx.shadowOffsetY = size * 0.05;
      ctx.strokeStyle = line.warna === "putih" ? "#121212" : "#ffffff";
      ctx.lineWidth = size * 0.17;
      ctx.strokeText(text, x + padX, textY);
      ctx.shadowColor = "transparent";
    }
    ctx.fillStyle = COLOR[line.warna];
    ctx.fillText(text, x + padX, textY);
    if (line.ukuran === "besar") {
      const right = r() > 0.4;
      burst(ctx, right ? x + boxW + size * 0.15 : x - size * 0.15, cy - size * 0.45, size * 0.55,
        right ? -0.75 : -2.4, r() > 0.5 ? aksen : "#ffffff");
    }
    ctx.restore();
    y += size * 1.05 + gap(size);
  });

  // Coretan kecil di tepi + bubble reaksi.
  const sparks = 2 + Math.floor(r() * 2);
  for (let i = 0; i < sparks; i += 1) {
    const sx = r() > 0.5 ? W * (0.04 + r() * 0.08) : W * (0.88 + r() * 0.08);
    const sy = H * (vertical ? (bawah ? 0.06 + r() * 0.3 : 0.62 + r() * 0.3) : 0.15 + r() * 0.75);
    sparkle(ctx, sx, sy, unit * (0.025 + r() * 0.02), i % 2 ? lain : "#ffffff");
  }
  spec.bubble.slice(0, 2).forEach((text, i) => {
    const pos = vertical
      ? (bawah ? [[W * 0.24, H * 0.14], [W * 0.78, H * 0.22]] : [[W * 0.24, H * 0.7], [W * 0.78, H * 0.64]])[i]
      : [[W * 0.82, H * 0.2], [W * 0.84, H * 0.72]][i];
    bubble(ctx, text, pos[0] + (r() - 0.5) * W * 0.04, pos[1] + (r() - 0.5) * H * 0.03, unit, vertical ? i === 1 : true);
  });
  ctx.restore();
}
