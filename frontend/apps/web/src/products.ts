/** Registry produk ekosistem ZOI. Menambah produk = menambah satu entri; status dibaca dari sistem, bukan dikarang. */
export type ProductStatus = "live" | "paused" | "planned";

export interface Product {
  id: string;
  name: string;
  tagline: string;
  description: string;
  status: ProductStatus;
  statusNote: string;
  /** Rute di dalam ZOI; `null` = belum bisa dibuka. */
  open: string | null;
  /** Nama adapter backend (deteksi read-only), bila ada. */
  adapter?: string;
}

export const PRODUCTS: Product[] = [
  { id: "ai-agent", name: "ZOI 3D AI Agent", tagline: "Your intelligent AI companion",
    description: "Asisten AI dengan avatar 3D, percakapan, suara, memori, dan agen yang menyusun rencana memakai tool dengan izinmu.",
    status: "live", statusNote: "Aktif", open: "/ai" },
  { id: "clipper", name: "ZOI AI Clipper", tagline: "AI video processing & content creation",
    description: "Aplikasi terpisah untuk memotong video menjadi Shorts. Repository aslinya tidak diubah; ZOI hanya mendeteksinya.",
    status: "paused", statusNote: "Integrasi ditunda — cara unduh videonya bertentangan dengan ketentuan YouTube",
    open: "/clipper", adapter: "zoi_ai_clipper" },
  { id: "blueprint", name: "Blueprint Studio", tagline: "Planning & creativity studio",
    description: "Studio video edukasi animasi. Paket produksi dari ZOI dimuat ke salinan Blueprint; file asli tidak disentuh.",
    status: "live", statusNote: "Aktif di laptop", open: "/blueprint", adapter: "blueprint_studio" },
  { id: "ai-lab", name: "ZOI AI Lab", tagline: "AI technology experiments",
    description: "Ruang eksperimen teknologi AI. Belum ada produknya — ditampilkan apa adanya sebagai rencana.",
    status: "planned", statusNote: "Direncanakan", open: null },
];

export const STATUS_TONE = { live: "ok", paused: "warn", planned: "neutral" } as const;
export const GITHUB_URL = "https://github.com/Fariz23zoi";
