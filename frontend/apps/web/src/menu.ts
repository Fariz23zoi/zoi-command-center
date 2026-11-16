/** Menu ZOI Universe. `phase` = fase saat fitur penuhnya dibangun; `ready` = sudah berfungsi sekarang. */
export type MenuGroup = "main" | "analytics" | "creation" | "products" | "system";

export const GROUP_LABEL: Record<MenuGroup, string | null> = {
  main: null, analytics: "Analytics", creation: "Creation", products: "Products", system: null,
};

export interface MenuItem {
  path: string;
  group: MenuGroup;
  label: string;
  phase: number;
  ready: boolean;
  description: string;
}

export const MENU: MenuItem[] = [
  { path: "/dashboard", group: "main", label: "Dashboard", phase: 3, ready: true, description: "Ringkasan channel YouTube-mu, aktivitas terbaru, dan akses cepat." },
  { path: "/projects", group: "main", label: "Projects", phase: 3, ready: true, description: "Paket produksi video yang tersimpan di ZOI." },
  { path: "/account", group: "system", label: "Account", phase: 3, ready: true, description: "Akses, login, dan akun terhubung." },
  { path: "/diagnostics", group: "system", label: "Diagnostics", phase: 1, ready: true, description: "Status sistem, penyedia AI, dan aplikasi terintegrasi." },
  { path: "/ai", group: "main", label: "AI Assistant", phase: 1, ready: true, description: "Percakapan dengan ZOI, dan agen yang menyusun rencana memakai tool (dengan izinmu)." },
  { path: "/analytics", group: "analytics", label: "Channel Analytics", phase: 6, ready: true, description: "Statistik channel-mu sendiri dari YouTube Data & Analytics API (OAuth resmi, hanya-baca)." },
  { path: "/competitors", group: "analytics", label: "Competitor Intelligence", phase: 6, ready: true, description: "Data publik channel yang kamu pantau, apa adanya dari YouTube. Disimpan paling lama 30 hari, tanpa skor." },
  { path: "/viral", group: "analytics", label: "Viral Video Hunter", phase: 6, ready: true, description: "Trending resmi YouTube Indonesia dan pencarian kata kunci, dalam urutan dari YouTube." },
  { path: "/trends", group: "analytics", label: "Trend Detector", phase: 6, ready: true, description: "AI lokal merangkum tema dari judul di daftar Trending atau pencarian. Interpretasi teks, bukan statistik." },
  { path: "/ideas", group: "creation", label: "Content Ideas", phase: 6, ready: true, description: "Draf ide video panjang & Shorts oleh AI lokal: judul, hook, garis besar, dan CTA." },
  { path: "/script", group: "creation", label: "Script & Storyboard", phase: 6, ready: true, description: "Draf naskah dan storyboard oleh AI lokal. Tidak ada yang dipublikasikan." },
  { path: "/production", group: "creation", label: "Content Production", phase: 7, ready: true, description: "Paket produksi, narasi Piper, salinan Blueprint Studio, dan render HyperFrames opsional — di laptop." },
    { path: "/clipper", group: "products", label: "ZOI AI CLIPPER", phase: 7, ready: true, description: "Menyalakan dan membuka aplikasi ZOI AI CLIPPER di laptop. Repository CLIPPER tidak diubah; ZOI tidak mengolah videonya." },
  { path: "/blueprint", group: "products", label: "BLUEPRINT STUDIO", phase: 7, ready: true, description: "Paket produksi ZOI dimuat ke salinan Blueprint Studio di laptop. File asli tidak diubah." },
  { path: "/monetization", group: "analytics", label: "Monetization", phase: 6, ready: true, description: "Syarat resmi YouTube Partner Program berdampingan dengan angka channel-mu dari YouTube." },
  { path: "/performance", group: "analytics", label: "Performance", phase: 6, ready: true, description: "Laporan per video channel-mu dari YouTube Analytics, termasuk persentase tonton hitungan YouTube." },
  { path: "/automation", group: "creation", label: "Automation", phase: 8, ready: true, description: "Laporan channel, pantau kompetitor & Trending, dan pengingat produksi terjadwal (WIB). Tanpa publikasi otomatis." },
  { path: "/tasks", group: "main", label: "Task Manager", phase: 1, ready: true, description: "Tugas latar belakang: progress, riwayat, dan pembatalan." },
  { path: "/memory", group: "main", label: "Memory", phase: 5, ready: true, description: "Memori jangka panjang yang bisa dilihat, diedit, dan dihapus." },
  { path: "/settings", group: "system", label: "Settings", phase: 1, ready: true, description: "Konfigurasi efektif dan preferensi." },
];
