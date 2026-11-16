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
  { path: "/competitors", label: "Competitor Intelligence", phase: 6, ready: true, description: "Data publik channel yang kamu pantau, apa adanya dari YouTube. Disimpan paling lama 30 hari, tanpa skor." },
  { path: "/viral", label: "Viral Video Hunter", phase: 6, ready: true, description: "Trending resmi YouTube Indonesia dan pencarian kata kunci, dalam urutan dari YouTube." },
  { path: "/trends", label: "Trend Detector", phase: 6, ready: true, description: "AI lokal merangkum tema dari judul di daftar Trending atau pencarian. Interpretasi teks, bukan statistik." },
  { path: "/ideas", label: "Content Ideas", phase: 6, ready: true, description: "Draf ide video panjang & Shorts oleh AI lokal: judul, hook, garis besar, dan CTA." },
  { path: "/script", label: "Script & Storyboard", phase: 6, ready: true, description: "Draf naskah dan storyboard oleh AI lokal. Tidak ada yang dipublikasikan." },
  { path: "/production", label: "Content Production", phase: 7, ready: false, description: "Pusat produksi yang menghubungkan CLIPPER dan Blueprint Studio." },
  { path: "/clipper", label: "ZOI AI CLIPPER", phase: 7, ready: false, description: "Produksi Shorts lewat adapter. Aplikasi CLIPPER tidak diubah." },
  { path: "/blueprint", label: "BLUEPRINT STUDIO", phase: 7, ready: false, description: "Paket produksi video edukasi animasi. Blueprint Studio tidak diubah." },
  { path: "/monetization", label: "Monetization", phase: 6, ready: true, description: "Syarat resmi YouTube Partner Program berdampingan dengan angka channel-mu dari YouTube." },
  { path: "/performance", label: "Performance", phase: 6, ready: true, description: "Laporan per video channel-mu dari YouTube Analytics, termasuk persentase tonton hitungan YouTube." },
  { path: "/tasks", label: "Task Manager", phase: 1, ready: true, description: "Tugas latar belakang: progress, riwayat, dan pembatalan." },
  { path: "/memory", label: "Memory", phase: 5, ready: true, description: "Memori jangka panjang yang bisa dilihat, diedit, dan dihapus." },
  { path: "/settings", label: "Settings", phase: 1, ready: true, description: "Konfigurasi efektif dan preferensi." },
];
