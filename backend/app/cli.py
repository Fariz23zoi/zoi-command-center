"""zoi-cli — alat baris perintah ZOI.

  python -m app.cli doctor                      Periksa kesiapan mesin (Python, disk, port, Ollama, path)
  python -m app.cli db upgrade                  Naikkan skema database (backup otomatis dulu)
  python -m app.cli backup                      Salin database ke data/backups
  python -m app.cli data export [--exclude-mock] [--out FILE]
  python -m app.cli data import FILE [--yes]    Pulihkan arsip (ZOI harus dalam keadaan berhenti)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from app.config.modes import ConfigError, RuntimeConfig, resolve_runtime
from app.config.settings import Mode, Settings, load_settings
from app.db.migrations import backup_database, current_revision, head_revision, upgrade_database
from app.db.portability import PortabilityError, export_data, find_absolute_paths, import_data, verify_archive
from app.db.session import db_path
from app.integrations.blueprint.adapter import BlueprintAdapter
from app.integrations.clipper.adapter import ClipperAdapter
from app.system import detectors

MIN_FREE_BYTES_WARN = 5 * 1024**3
MIN_FREE_BYTES_FAIL = 1 * 1024**3


@dataclass
class Check:
    name: str
    status: str  # OK | WARN | FAIL | INFO
    detail: str


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name, status, detail))

    @property
    def failed(self) -> bool:
        return any(c.status == "FAIL" for c in self.checks)


def run_doctor(settings: Settings, runtime: RuntimeConfig, *, check_port: bool = True) -> DoctorReport:
    report = DoctorReport()
    py = detectors.python_info()
    report.add("Python", "OK" if py["supported"] else "FAIL",
               f"{py['version']} ({'didukung' if py['supported'] else 'butuh 3.12 atau lebih baru'})")
    report.add("Mode", "INFO", f"{runtime.mode.value} — provider AI: {runtime.provider}")
    for warning in runtime.warnings:
        report.add("Konfigurasi", "WARN", warning)

    probe = runtime.data_dir if runtime.data_dir.exists() else Path(runtime.data_dir.anchor)
    free = shutil.disk_usage(probe).free
    gib = free / 1024**3
    status = "FAIL" if free < MIN_FREE_BYTES_FAIL else "WARN" if free < MIN_FREE_BYTES_WARN else "OK"
    report.add("Ruang disk", status, f"{gib:.1f} GB kosong di {probe} (disarankan ≥ 5 GB cadangan)")

    if check_port:
        if detectors.port_available(runtime.host, runtime.port):
            report.add("Port", "OK", f"{runtime.host}:{runtime.port} bebas → {runtime.base_url}")
        else:
            owner = detectors.port_owner(runtime.port)
            report.add("Port", "FAIL", f"Port {runtime.port} sudah dipakai" + (f" oleh {owner}" if owner else "")
                       + ". ZOI tidak mematikan program lain; hentikan program itu atau set "
                       + f"ZOI_PORT={8001 if runtime.port == 8000 else 8000}.")

    if runtime.mode is Mode.LOCAL:
        index = runtime.frontend_dist / "index.html"
        report.add("Frontend", "OK" if index.is_file() else "FAIL",
                   f"{'ditemukan' if index.is_file() else 'TIDAK ditemukan'}: {index}")

    if runtime.provider == "ollama":
        from app.providers.ollama import OllamaProvider
        from app.security.cost_guard import CostGuard

        guard = CostGuard.build(ollama_url=runtime.ollama_url, extra_hosts=settings.extra_hosts, recorder=None)
        status_ = asyncio.run(OllamaProvider(runtime.ollama_url, runtime.ollama_model, guard).health())
        report.add("Ollama", "OK" if status_.available else "WARN", status_.detail)
    elif runtime.provider == "mock":
        report.add("Penyedia AI", "INFO", "Mock Provider (hanya development, jawaban berlabel MOCK)")
    else:
        report.add("Penyedia AI", "INFO", "AI dinonaktifkan (ZOI_AI_PROVIDER=none)")

    for adapter in (ClipperAdapter(settings.clipper_dir, settings.clipper_python),
                    BlueprintAdapter(settings.blueprint_file)):
        st = adapter.detect()
        if not st.configured:
            report.add(adapter.name, "INFO", "belum dikonfigurasi (opsional)")
        else:
            report.add(adapter.name, "OK" if st.found else "WARN",
                       "ditemukan (read-only)" if st.found else "; ".join(st.problems))

    db_file = db_path(runtime.data_dir)
    if db_file.exists():
        current = current_revision(db_file)
        head = head_revision()
        report.add("Database", "OK" if current == head else "WARN",
                   f"skema {current} (terbaru {head})" + ("" if current == head else " — jalankan: db upgrade"))
        with closing(sqlite3.connect(db_file)) as conn:
            try:
                mock_rows = conn.execute("SELECT COUNT(*) FROM messages WHERE is_mock = 1").fetchone()[0]
            except sqlite3.OperationalError:
                mock_rows = 0
        if runtime.mode is Mode.LOCAL and mock_rows:
            report.add("Data mock", "WARN", f"{mock_rows} pesan mock ada di database mode local. "
                                            "Impor ulang dengan arsip --exclude-mock.")
        hits = find_absolute_paths(db_file) if current == head else []
        report.add("Portabilitas", "OK" if not hits else "WARN",
                   "tidak ada path absolut di database" if not hits else f"{len(hits)} nilai mirip path absolut")
    else:
        report.add("Database", "INFO", f"belum ada — akan dibuat saat ZOI pertama dijalankan ({db_file})")
    return report


def _print_report(report: DoctorReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps([c.__dict__ for c in report.checks], indent=2, ensure_ascii=False))
        return
    for c in report.checks:
        print(f"[{c.status:<4}] {c.name}: {c.detail}")
    print("\nHasil:", "ADA MASALAH — perbaiki baris FAIL." if report.failed else "Siap.")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="zoi-cli", description="Alat baris perintah ZOI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    doctor = sub.add_parser("doctor", help="periksa kesiapan mesin")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--skip-port", action="store_true", help="jangan periksa port (mis. saat ZOI berjalan)")
    db = sub.add_parser("db", help="database")
    db.add_argument("action", choices=["upgrade", "status"])
    sub.add_parser("backup", help="salin database ke data/backups")
    data = sub.add_parser("data", help="ekspor/impor data portabel")
    data_sub = data.add_subparsers(dest="action", required=True)
    exp = data_sub.add_parser("export")
    exp.add_argument("--out", type=Path)
    exp.add_argument("--exclude-mock", action="store_true", help="buang percakapan mock (disarankan saat migrasi)")
    imp = data_sub.add_parser("import")
    imp.add_argument("file", type=Path)
    imp.add_argument("--yes", action="store_true", help="lanjut tanpa konfirmasi")
    ver = data_sub.add_parser("verify")
    ver.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    try:
        settings = load_settings()
        runtime = resolve_runtime(settings)
    except ConfigError as exc:
        print(f"Konfigurasi salah: {exc}", file=sys.stderr)
        return 2
    db_file = db_path(runtime.data_dir)

    try:
        if args.cmd == "doctor":
            report = run_doctor(settings, runtime, check_port=not args.skip_port)
            _print_report(report, args.json)
            return 1 if report.failed else 0
        if args.cmd == "db":
            if args.action == "status":
                print(f"Skema saat ini: {current_revision(db_file)} — terbaru: {head_revision()}")
                return 0
            backup = upgrade_database(db_file)
            print(f"Database siap di skema {head_revision()}." + (f" Backup: {backup}" if backup else ""))
            return 0
        if args.cmd == "backup":
            path = backup_database(db_file, "manual")
            print(f"Backup dibuat: {path}" if path else "Belum ada database untuk di-backup.")
            return 0
        if args.cmd == "data" and args.action == "export":
            result = export_data(runtime.data_dir, args.out, exclude_mock=args.exclude_mock)
            print(f"Arsip dibuat: {result.path}")
            print(json.dumps(result.manifest["tables"], indent=2))
            return 0
        if args.cmd == "data" and args.action == "verify":
            manifest = verify_archive(args.file)
            print(f"Arsip valid. Dibuat {manifest['created_at']}, skema {manifest['schema_revision']}.")
            return 0
        if args.cmd == "data" and args.action == "import":
            if not detectors.port_available(runtime.host, runtime.port):
                print(f"ZOI tampaknya sedang berjalan di port {runtime.port}. Hentikan dulu sebelum impor.",
                      file=sys.stderr)
                return 1
            if not args.yes:
                answer = input(f"Impor akan MENGGANTI data di {runtime.data_dir} (backup dibuat dulu). Lanjut? [y/N] ")
                if answer.strip().lower() not in {"y", "ya", "yes"}:
                    print("Dibatalkan.")
                    return 1
            result = import_data(args.file, runtime.data_dir)
            print("Impor selesai." + (f" Backup data lama: {result.backup}" if result.backup else ""))
            print(json.dumps(result.table_counts, indent=2))
            return 0
    except PortabilityError as exc:
        print(f"Gagal: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
