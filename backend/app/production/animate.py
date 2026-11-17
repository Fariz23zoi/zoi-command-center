"""Animasi oleh ZOI AI (ADR 0018) — pengganti langkah "prompt motion → Claude" di alur Blueprint Studio.

AI Brain ZOI (sesuai .env) menulis adegan per beat sebagai potongan HTML/SVG + CSS. Potongan itu DISARING ketat
(daftar izin tag & atribut, tanpa script/URL/event) lalu dirangkai ZOI ke komposisi HyperFrames dengan waktu
narasi Piper dan subtitle. Adegan yang gagal dibuat/disaring memakai kartu teks biasa — dicatat jujur di hasil.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel, Field

from app.ai.structured import chat_json
from app.production.hyperframes import SIZES, estimate_seconds
from app.providers.base import ChatMessage, LLMProvider

MAX_SCENE_HTML = 6000
MAX_SCENE_CSS = 6000

ALLOWED_TAGS = {
    "div", "span", "p", "h1", "h2", "h3", "b", "i", "em", "strong", "br", "ul", "li",
    "svg", "g", "path", "circle", "rect", "ellipse", "line", "polyline", "polygon", "text", "tspan",
    "defs", "lineargradient", "radialgradient", "stop",
}
SKIP_CONTENT = {"script", "style", "iframe", "object", "embed", "foreignobject", "template", "noscript", "title",
                "textarea", "select"}
VOID = {"br", "stop", "path", "circle", "rect", "ellipse", "line", "polyline", "polygon"}
ALLOWED_ATTRS = {
    "class", "viewbox", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "width", "height",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "points", "transform", "opacity",
    "offset", "stop-color", "stop-opacity", "id", "gradientunits", "font-size", "font-weight", "text-anchor",
    "xmlns", "preserveaspectratio", "fill-opacity", "stroke-dasharray", "stroke-dashoffset",
}
SVG_CASE = {"viewbox": "viewBox", "lineargradient": "linearGradient", "radialgradient": "radialGradient",
            "gradientunits": "gradientUnits", "preserveaspectratio": "preserveAspectRatio"}
# url(#id) (gradien SVG lokal) boleh; url ke file/internet tidak.
BAD_VALUE = re.compile(r"url\s*\(\s*(?![\'\"]?#[\w-]+[\'\"]?\s*\))|javascript:|expression\s*\(|@import|</|<!--", re.I)


class Scene(BaseModel):
    html: str = Field(description="Isi adegan: HTML/SVG tanpa script, tanpa gambar luar.")
    css: str = Field(default="", description="CSS khusus adegan; semua selector diawali .s<nomor>.")


class Scenes(BaseModel):
    background: str = Field(default="#0b0e14", description="Warna latar utama (hex).")
    text_color: str = Field(default="#f2f4f8", description="Warna teks utama (hex).")
    scenes: list[Scene]


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.dropped = 0
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_CONTENT:
            self.skip_depth += 1
            self.dropped += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            self.dropped += 1
            return
        clean = []
        for name, value in attrs:
            if name not in ALLOWED_ATTRS or value is None or BAD_VALUE.search(value):
                self.dropped += 1
                continue
            clean.append(f' {SVG_CASE.get(name, name)}="{html.escape(value, quote=True)}"')
        name = SVG_CASE.get(tag, tag)
        if tag in VOID:
            self.out.append(f"<{name}{''.join(clean)}/>" if tag != "br" else "<br>")
        else:
            self.out.append(f"<{name}{''.join(clean)}>")
            self.stack.append(name)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_CONTENT:
            self.dropped += 1
            return
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag in ALLOWED_TAGS and not self.skip_depth:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_CONTENT:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        name = SVG_CASE.get(tag, tag)
        if tag in VOID or name not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == name:
                break

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        return "".join(self.out) + "".join(f"</{t}>" for t in reversed(self.stack))


def sanitize_html(fragment: str) -> tuple[str, int]:
    parser = _Sanitizer()
    parser.feed(fragment[:MAX_SCENE_HTML])
    parser.close()
    return parser.result(), parser.dropped


def sanitize_css(css: str) -> str | None:
    css = css[:MAX_SCENE_CSS]
    if BAD_VALUE.search(css) or "<" in css:
        return None
    return css


def _hex(value: str, default: str) -> str:
    return value if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value.strip()) else default


PROMPT = """Kamu motion designer. Buat {count} adegan animasi untuk video penjelasan berukuran {w}x{h} piksel.
Satu adegan per beat, urutan sama. Gaya visual yang diminta:
{gaya}

Beat:
{beats}

Aturan teknis WAJIB (adegan dirender HyperFrames, tanpa internet):
- Tiap adegan: "html" berisi elemen div/span/h1-h3/p dan SVG (path, circle, rect, polygon, text, gradient). DILARANG
  script, img, iframe, url(), font atau gambar dari internet.
- Tiap adegan ada di dalam wadah .s<nomor> (mulai .s1) berukuran penuh {w}x{h}, posisi absolut. Semua selector CSS
  adegan harus diawali .s<nomor>, mis. ".s2 .bulan".
- Animasi hanya @keyframes CSS dengan nama unik per adegan (mis. s2-terbit); boleh animation-delay. Tanpa JavaScript.
- Teks di layar singkat (judul/kata kunci), JANGAN menyalin narasi penuh — subtitle ditambahkan ZOI di bawah.
- Bentuk sederhana dan berani, cocok untuk layar HP.
Balas HANYA JSON sesuai skema: background, text_color, scenes[{count}] berisi html dan css."""


async def generate_scenes(provider: LLMProvider, package: dict[str, Any]) -> Scenes:
    w, h = SIZES.get(str(package.get("rasio")), SIZES["9:16"])
    beats = package.get("beats") or []
    listing = "\n".join(f"{i + 1}. {b.get('k', '')}: narasi \"{b.get('n', '')}\" | catatan visual: {b.get('v', '')}"
                        for i, b in enumerate(beats))
    gaya = str(package.get("gaya") or "bebas, modern, minimalis, kontras tinggi")[:3000]
    messages = [ChatMessage("user", PROMPT.format(count=len(beats), w=w, h=h, gaya=gaya, beats=listing))]
    result = await chat_json(provider, messages, Scenes, timeout_s=300)
    return result.value


def compose_animated(package: dict[str, Any], scenes: Scenes, timings: list[dict[str, Any]] | None) -> tuple[str, dict]:
    """Rangkai adegan AI (sudah disaring) + audio narasi + subtitle → index.html HyperFrames."""
    width, height = SIZES.get(str(package.get("rasio")), SIZES["9:16"])
    scale = width / 720
    beats = package.get("beats") or []
    bg = _hex(scenes.background, "#0b0e14")
    fg = _hex(scenes.text_color, "#f2f4f8")
    clips: list[str] = []
    styles: list[str] = []
    report = {"ai_scenes": 0, "fallback_scenes": 0, "removed_parts": 0}
    t = 0.0
    for i, beat in enumerate(beats):
        n = i + 1
        timing = timings[i] if timings and i < len(timings) else None
        duration = round(float(timing["duration"]) if timing else estimate_seconds(str(beat.get("n", ""))), 3)
        scene = scenes.scenes[i] if i < len(scenes.scenes) else None
        body, dropped = sanitize_html(scene.html) if scene else ("", 0)
        css = sanitize_css(scene.css) if scene else None
        report["removed_parts"] += dropped
        if scene and body.strip() and css is not None:
            report["ai_scenes"] += 1
            styles.append(css)
        else:
            report["fallback_scenes"] += 1
            body = f'<div class="fallback">{html.escape(str(beat.get("k", "")))}</div>'
        caption = html.escape(str(beat.get("n", "")))
        clips.append(f'<section class="clip s{n}" data-start="{t:.3f}" data-duration="{duration:.3f}">{body}'
                     f'<div class="cap">{caption}</div></section>')
        if timing and timing.get("file"):
            clips.append(f'<audio data-start="{t:.3f}" data-duration="{duration:.3f}" '
                         f'src="{html.escape(timing["file"])}"></audio>')
        t += duration
    title = html.escape(str(package.get("judul", "ZOI")))
    mock = '<div class="mock">MOCK — teks tiruan</div>' if package.get("mock") else ""
    doc = f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><title>{title}</title>
<!-- Dibuat ZOI: adegan ditulis AI ZOI lalu disaring (tanpa script/URL); animasi CSS saja. -->
<style>
html,body{{margin:0;background:{bg}}}
#root{{position:relative;width:{width}px;height:{height}px;overflow:hidden;color:{fg};background:{bg};
  font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}}
.clip{{position:absolute;inset:0;overflow:hidden}}
.fallback{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:{round(56 * scale)}px;font-weight:800;text-align:center;padding:{round(48 * scale)}px}}
.cap{{position:absolute;left:{round(40 * scale)}px;right:{round(40 * scale)}px;bottom:{round(90 * scale)}px;z-index:9;
  font-size:{round(30 * scale)}px;line-height:1.3;text-align:center;color:#fff;
  text-shadow:0 2px 8px rgba(0,0,0,.85);background:rgba(0,0,0,.35);padding:{round(10 * scale)}px;border-radius:12px}}
.mock{{position:absolute;top:16px;left:16px;font-size:{round(20 * scale)}px;color:#ffb020;z-index:10}}
{chr(10).join(styles)}
</style></head><body>
<div id="root" data-composition-id="root" data-width="{width}" data-height="{height}" data-fps="30"
     data-start="0" data-duration="{round(t, 3):.3f}">
{mock}
{chr(10).join(clips)}
</div></body></html>
"""
    return doc, report
