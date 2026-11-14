"""Rencana tertulis untuk Mock Provider (hanya development). Berlabel MOCK, tanpa angka."""

from __future__ import annotations

from app.agent.planner import Rencana, Step

TRIGGER_BAD_PLAN = "/uji-rencana-rusak"


def mock_plan(request: str) -> Rencana:
    text = request.lower()
    goal = "[MOCK] Rencana tiruan berdasarkan kata kunci, bukan AI"
    if TRIGGER_BAD_PLAN in text:
        return Rencana(tujuan=goal, langkah=[Step(tool="unggah_video", argumen={}, alasan="[MOCK] tool terlarang")])
    steps: list[Step] = []
    if any(word in text for word in ("memori", "ingat", "catat")):
        steps += [
            Step(tool="cari_memori", argumen={"kata_kunci": "zoi"}, alasan="[MOCK] Cek catatan yang sudah ada"),
            Step(tool="simpan_memori", argumen={"isi": "[MOCK] Catatan contoh dari agen tiruan", "jenis": "fakta"},
                 alasan="[MOCK] Simpan catatan baru (perlu izin)"),
        ]
    if "sistem" in text:
        steps += [Step(tool="status_sistem", alasan="[MOCK] Baca kondisi komputer"),
                  Step(tool="jalankan_pemeriksaan_sistem", alasan="[MOCK] Jalankan pemeriksaan lengkap (perlu izin)")]
    if any(word in text for word in ("aplikasi", "clipper", "blueprint")):
        steps.append(Step(tool="status_aplikasi", alasan="[MOCK] Cek CLIPPER & Blueprint"))
    if "tugas" in text:
        steps.append(Step(tool="daftar_tugas", argumen={"jumlah": 5}, alasan="[MOCK] Lihat tugas terbaru"))
    if not steps:
        steps = [Step(tool="waktu_sekarang", alasan="[MOCK] Cek waktu"),
                 Step(tool="status_ai", alasan="[MOCK] Cek penyedia AI")]
    return Rencana(tujuan=goal, langkah=steps[:6])
