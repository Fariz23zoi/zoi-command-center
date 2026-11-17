"""Lampiran di chat: ekstraksi teks (txt/docx/pdf), penolakan file non-teks, susunan pesan."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest

from app.chat.attachments import MAX_TEXT_TOTAL, compose, extract
from app.core.errors import ZoiError


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def make_docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", (
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p><w:p><w:r><w:t>baris dua</w:t></w:r></w:p></w:body>"
            "</w:document>"))
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def test_extract_text_docx_pdf():
    assert extract("catatan.md", b64("# Judul\nisi".encode()))["text"] == "# Judul\nisi"
    assert extract("laporan.docx", b64(make_docx("Halo ZOI")))["text"] == "Halo ZOI\nbaris dua"
    assert "Laporan Triwulan" in extract("a.pdf", b64(make_pdf("Laporan Triwulan")))["text"]
    big = extract("besar.txt", b64(("x" * 40_000).encode()))
    assert big["truncated"] and len(big["text"]) == 30_000 and big["chars"] == 40_000


def test_extract_rejects_non_text_and_tricks():
    for name, raw, msg in [("foto.png", b"\x89PNG", "belum didukung"), ("a.bin", b"\x00\x01" * 10, "bukan teks"),
                           ("rusak.pdf", b"bukan pdf", "tidak bisa dibaca"), ("kosong.txt", b"   ", "tidak berisi")]:
        with pytest.raises(ZoiError, match=msg):
            extract(name, b64(raw))
    with pytest.raises(ZoiError, match="rusak"):
        extract("a.txt", "%%%")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')
    with pytest.raises(ZoiError, match="tidak valid"):
        extract("bom.docx", b64(buf.getvalue()))


def test_compose_puts_question_last_and_caps_total():
    out = compose("Ringkas ya", [{"name": "a.txt", "text": "A" * 20_000}, {"name": "b].txt", "text": "B" * 20_000}])
    assert out.endswith("\n\nRingkas ya") and "[Lampiran: b).txt (dipotong)]" in out
    assert out.count("A") + out.count("B") == MAX_TEXT_TOTAL
    assert compose("hai", []) == "hai"


def test_chat_with_attachment_api(client):
    r = client.post("/api/attachments/extract", json={"name": "n.txt", "data_base64": b64(b"Data penting")})
    assert r.status_code == 200 and r.json()["text"] == "Data penting"
    res = client.post("/api/chat", json={"message": "Apa isinya?", "attachments": [r.json() | {"truncated": False}]})
    assert res.status_code == 202, res.text
    content = res.json()["user_message"]["content"]
    assert content.startswith("[Lampiran: n.txt]\nData penting") and content.endswith("Apa isinya?")
    convs = client.get("/api/conversations").json()["conversations"]
    assert convs[0]["title"] == "Apa isinya?"
