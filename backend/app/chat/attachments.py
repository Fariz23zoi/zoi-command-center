"""Lampiran file di chat ZOI AI: teks diekstrak di laptop (tidak dikirim ke mana pun selain AI Brain bersama pesan).

Didukung: teks (txt, md, csv, json, srt, vtt, html, kode), DOCX (zip+XML, pustaka standar), PDF (pypdf, BSD-3).
Gambar/audio/video belum didukung — model teks tidak bisa membacanya; ditolak dengan pesan jelas.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
import zipfile
from xml.etree import ElementTree

from app.core.errors import ZoiError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 3
MAX_TEXT_PER_FILE = 30_000
MAX_TEXT_TOTAL = 30_000  # ±8.500 token: muat di anggaran riwayat AI cloud ZOI
TEXT_EXT = {"txt", "md", "markdown", "csv", "tsv", "json", "srt", "vtt", "html", "htm", "xml", "yaml", "yml",
            "log", "py", "js", "ts", "tsx", "css", "sql", "ini", "toml", "env.example"}
BINARY_REJECT = {"png", "jpg", "jpeg", "gif", "webp", "mp3", "wav", "mp4", "mov", "mkv", "zip", "exe", "xlsx", "pptx"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _docx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        if zf.getinfo("word/document.xml").file_size > 20 * 1024 * 1024:
            raise ZoiError("Isi DOCX terlalu besar.", code="attachment_too_large")
        xml = zf.read("word/document.xml")
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:  # DOCX asli tidak memakai DTD; tolak trik entitas XML
        raise ZoiError("DOCX tidak valid.", code="attachment_invalid")
    root = ElementTree.fromstring(xml)  # noqa: S314 — DTD/entitas ditolak di atas
    lines = ["".join(t.text or "" for t in p.iter(f"{_W}t")) for p in root.iter(f"{_W}p")]
    return "\n".join(lines)


def _pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader  # impor saat dipakai: tidak memperlambat start ZOI

    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ZoiError("PDF ini dikunci kata sandi.", code="attachment_locked")
    parts: list[str] = []
    size = 0
    for page in reader.pages[:200]:
        text = page.extract_text() or ""
        parts.append(text)
        size += len(text)
        if size > MAX_TEXT_PER_FILE * 2:
            break
    return "\n".join(parts)


def extract(name: str, data_base64: str) -> dict:
    name = re.sub(r"[\r\n\t]", " ", name).strip()[:120] or "lampiran"
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ZoiError("File lampiran rusak.", code="attachment_invalid") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ZoiError("File terlalu besar (maksimal 10 MB).", code="attachment_too_large")
    ext = _ext(name)
    try:
        if ext == "pdf":
            text = _pdf_text(raw)
        elif ext == "docx":
            text = _docx_text(raw)
        elif ext in BINARY_REJECT:
            raise ZoiError(f"File .{ext} belum didukung — AI ZOI hanya membaca teks "
                           "(txt, md, csv, json, srt, pdf, docx).", code="attachment_unsupported")
        else:
            if b"\x00" in raw[:4096]:
                raise ZoiError("File ini bukan teks.", code="attachment_unsupported")
            text = raw.decode("utf-8", errors="replace")
    except ZoiError:
        raise
    except Exception as exc:  # noqa: BLE001 — file rusak/tidak terbaca: jawab jujur, jangan crash
        raise ZoiError(f"Isi {name} tidak bisa dibaca.", code="attachment_unreadable") from exc
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    if not text:
        raise ZoiError(f"{name} tidak berisi teks yang bisa dibaca (mungkin hasil scan/gambar).",
                       code="attachment_empty")
    truncated = len(text) > MAX_TEXT_PER_FILE
    return {"name": name, "text": text[:MAX_TEXT_PER_FILE], "chars": len(text), "truncated": truncated}


def compose(text: str, attachments: list[dict]) -> str:
    """Lampiran DULU, pertanyaan TERAKHIR: bila konteks penuh, bagian awal yang terpotong, pertanyaan tetap utuh."""
    if not attachments:
        return text
    if len(attachments) > MAX_FILES:
        raise ZoiError(f"Maksimal {MAX_FILES} lampiran per pesan.", code="too_many_attachments")
    blocks: list[str] = []
    left = MAX_TEXT_TOTAL
    for item in attachments:
        name = str(item.get("name") or "lampiran")[:120].replace("]", ")")
        body = str(item.get("text") or "")
        cut = body[:max(0, left)]
        left -= len(cut)
        note = " (dipotong)" if len(cut) < len(body) or item.get("truncated") else ""
        blocks.append(f"[Lampiran: {name}{note}]\n{cut}\n[/Lampiran]")
    return "\n\n".join(blocks) + "\n\n" + text
