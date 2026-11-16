# Third-party notices

Daftar dependensi ZOI beserta lisensinya (dibuat otomatis oleh `scripts/check_licenses.py`).
Python: seluruh paket di venv backend (termasuk alat pengembangan). npm: dependensi produksi frontend.

| Ekosistem | Paket | Versi | Lisensi |
|---|---|---|---|
| python | alembic | 1.20.1 | MIT |
| python | annotated-doc | 0.0.6 | MIT |
| python | annotated-types | 0.8.0 | MIT |
| python | anyio | 4.16.0 | MIT |
| python | boolean.py | 5.0 | BSD-2-Clause |
| python | CacheControl | 0.14.4 | Apache-2.0 |
| python | certifi | 2026.10.23 | MPL-2.0 |
| python | charset-normalizer | 3.5.2 | MIT |
| python | click | 8.5.1 | BSD-3-Clause |
| python | cyclonedx-python-lib | 11.12.0 | Apache-2.0 |
| python | defusedxml | 0.7.1 | PSF-2.0 |
| python | fastapi | 0.162.6 | MIT |
| python | filelock | 4.2.10 | MIT |
| python | h11 | 0.16.0 | MIT |
| python | httpcore | 1.0.9 | BSD-3-Clause |
| python | httpx | 0.28.1 | BSD-3-Clause |
| python | idna | 3.20 | BSD-3-Clause |
| python | iniconfig | 2.3.1 | MIT |
| python | license-expression | 30.4.4 | Apache-2.0 |
| python | Mako | 1.4.3 | MIT |
| python | markdown-it-py | 4.3.0 | MIT |
| python | MarkupSafe | 3.0.4 | BSD-3-Clause |
| python | mdurl | 0.1.2 | MIT |
| python | msgpack | 1.2.4 | Apache-2.0 |
| python | opentelemetry-api | 1.45.2 | Apache-2.0 |
| python | packageurl-python | 0.17.6 | MIT |
| python | packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| python | pip | 26.3 | MIT |
| python | pip-requirements-parser | 32.0.1 | MIT |
| python | pip_api | 0.0.35 | Apache-2.0 |
| python | pip_audit | 2.10.1 | Apache-2.0 |
| python | platformdirs | 4.14.5 | MIT |
| python | pluggy | 1.7.0 | MIT |
| python | psutil | 7.2.2 | BSD-3-Clause |
| python | py-serializable | 2.2.0 | Apache-2.0 |
| python | pydantic | 2.14.3 | MIT |
| python | pydantic-settings | 2.16.3 | MIT |
| python | pydantic_core | 2.50.4 | MIT |
| python | Pygments | 2.21.0 | BSD-2-Clause |
| python | pyparsing | 3.3.3 | MIT |
| python | pytest | 9.2.0 | MIT |
| python | pytest-asyncio | 1.5.0 | Apache-2.0 |
| python | python-dotenv | 1.2.4 | BSD-3-Clause |
| python | requests | 2.34.2 | Apache-2.0 |
| python | rich | 15.0.0 | MIT |
| python | ruff | 0.17.5 | MIT |
| python | sortedcontainers | 2.4.0 | Apache-2.0 |
| python | SQLAlchemy | 2.1.8 | MIT |
| python | starlette | 1.10.0 | BSD-3-Clause |
| python | structlog | 26.1.0 | MIT OR Apache-2.0 |
| python | tomli | 2.5.0 | MIT |
| python | tomli_w | 1.2.0 | MIT |
| python | typing-inspection | 0.4.5 | MIT |
| python | typing_extensions | 4.16.0 | PSF-2.0 |
| python | urllib3 | 2.8.0 | MIT |
| python | uvicorn | 0.54.0 | BSD-3-Clause |
| python | websockets | 17.4 | BSD-3-Clause |
| npm | @interviewflowai/talking-avatar | 0.3.0 | MIT |
| npm | @types/react | 19.3.0 | MIT |
| npm | cookie | 1.1.1 | MIT |
| npm | csstype | 3.2.3 | MIT |
| npm | react | 19.3.1 | MIT |
| npm | react-dom | 19.3.1 | MIT |
| npm | react-router | 7.18.5 | MIT |
| npm | react-router-dom | 7.18.5 | MIT |
| npm | scheduler | 0.28.0 | MIT |
| npm | set-cookie-parser | 2.7.3 | MIT |
| npm | three | 0.187.0 | MIT |
| npm | zustand | 5.1.0 | MIT |

## Aset yang ikut dibundel (avatar 3D)

Disalin dari paket `@interviewflowai/talking-avatar` ke `avatar-assets/` dan disajikan dari server ZOI
sendiri (tanpa CDN). Teks lisensinya ikut disalin ke folder yang sama.

| Aset | Asal | Lisensi |
|---|---|---|
| `female.glb`, `male.glb` | Microsoft Rocketbox (business female 04 / male 01), dikonversi oleh talking-avatar | MIT (Copyright (c) 2020 Microsoft) — `LICENSE-rocketbox.txt` |
| `viseme-model.bin` | Bobot model lip-sync talking-avatar | MIT — `LICENSE-talking-avatar.txt` |

Lisensi lengkap tiap paket tersedia di folder paket masing-masing (site-packages / node_modules).

ZOI sendiri berlisensi MIT — lihat `LICENSE`.
