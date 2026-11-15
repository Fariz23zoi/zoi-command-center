/** 16 menu ZOI. `phase` = fase saat fitur penuhnya dibangun; `ready` = sudah berfungsi sekarang. */
export interface MenuItem {
  path: string;
  label: string;
  phase: number;
  ready: boolean;
  description: string;
}

export const MENU: MenuItem[] = [
  { path: "/", label: "Overview", phase: 1, ready: true, description: "Status sistem, penyedia AI, dan aplikasi terintegrasi." },
  { path: "/assistant", label: "AI Assistant", phase: 1, ready: true, description: "Percakapan dengan ZOI, dan agen yang menyusun rencana memakai tool (dengan izinmu)." },
  { path: "/analytics", label: "Channel Analytics", phase: 6, ready: true, description: "Statistik channel-mu sendiri dari YouTube Data & Analytics API (OAuth resmi, hanya-baca)." },
  { path: "/competitors", label: "Competitor Intelligence", phase: 6, ready: false, description: "Data publik kompetitor: topik, format, frekuensi upload, engagement." },
  { path: "/viral", label: "Viral Video Hunter", phase: 6, ready: false, description: "Kandidat video yang sedang naik berdasarkan snapshot berkala." },
  { path: "/trends", label: "Trend Detector", phase: 6, ready: false, description: "Topik yang meningkat sesuai niche, dari snapshot milik sendiri." },
  { path: "/ideas", label: "Content Ideas", phase: 6, ready: false, description: "Ide video panjang & Shorts, judul, hook, dan CTA." },
  { path: "/script", label: "Script & Storyboard", phase: 6, ready: false, description: "Riset, naskah, storyboard, timing, dan subtitle." },
  { path: "/production", label: "Content Production", phase: 7, ready: false, description: "Pusat produksi yang menghubungkan CLIPPER dan Blueprint Studio." },
  { path: "/clipper", label: "ZOI AI CLIPPER", phase: 7, ready: false, description: "Produksi Shorts lewat adapter. Aplikasi CLIPPER tidak diubah." },
  { path: "/blueprint", label: "BLUEPRINT STUDIO", phase: 7, ready: false, description: "Paket produksi video edukasi animasi. Blueprint Studio tidak diubah." },
  { path: "/monetization", label: "Monetization", phase: 6, ready: true, description: "Syarat resmi YouTube Partner Program berdampingan dengan angka channel-mu dari YouTube." },
  { path: "/performance", label: "Performance", phase: 6, ready: false, description: "Evaluasi hasil konten dan eksperimen." },
  { path: "/tasks", label: "Task Manager", phase: 1, ready: true, description: "Tugas latar belakang: progress, riwayat, dan pembatalan." },
  { path: "/memory", label: "Memory", phase: 5, ready: true, description: "Memori jangka panjang yang bisa dilihat, diedit, dan dihapus." },
  { path: "/settings", label: "Settings", phase: 1, ready: true, description: "Konfigurasi efektif dan preferensi." },
];
