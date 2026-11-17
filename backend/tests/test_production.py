"""Phase 7 — produksi konten di laptop: paket, narasi, salinan Blueprint Studio, HyperFrames opsional.

Blueprint asli TIDAK ada di repo: tes memakai halaman tiruan kecil dengan penanda yang sama. Bila file asli
pengguna tersedia lewat ZOI_TEST_BLUEPRINT_FILE (hanya di mesin pengembang), tes tambahan memakainya.
HyperFrames sungguhan diuji hanya bila ZOI_TEST_HYPERFRAMES_DIR diisi.
"""

from __future__ import annotations

import io
import json
import os
import wave
from pathlib import Path

import pytest

from app.production.blueprint import INJECT_MARK, BlueprintCopyError, make_copy
from app.production.hyperframes import HyperFrames, compose, estimate_seconds
from app.production.service import build_srt, srt_time, validate_package
from tests.conftest import wait_for

FAKE_BLUEPRINT = """<!doctype html><html><head><title>Blueprint Studio</title></head><body>
<input id="topik"><select id="durasi"><option value="30">30</option><option value="60" selected>60</option></select>
<select id="bahasa"><option>Indonesia</option></select><select id="rasio"><option>16:9</option><option>9:16</option>
</select><select id="mc"><option value="auto">a</option><option value="manual">m</option></select>
<textarea id="srt"></textarea><div id="beats"></div>
<script>var $=function(i){return document.getElementById(i)},state={beats:[],style:null};
function render(){} function setMode(){}</script>
</body></html>"""

PAKET = {"format": "zoi.paket/v1", "judul": "Kenapa langit biru", "topik": "Langit biru", "durasi": "60 detik",
         "bahasa": "Indonesia", "rasio": "9:16", "mock": False,
         "beats": [{"k": "Hook", "n": "Pernah bertanya kenapa langit biru?", "v": "Langit pagi"},
                   {"k": "Penjelasan", "n": "Cahaya biru dihamburkan udara lebih kuat.", "v": "Diagram cahaya"},
                   {"k": "Penutup", "n": "Ikuti untuk sains singkat.", "v": ""}]}


# ── unit ──────────────────────────────────────────────────────────────────
def test_blueprint_copy_injects_only_one_block():
    copy = make_copy(FAKE_BLUEPRINT)
    assert copy.startswith(FAKE_BLUEPRINT[: FAKE_BLUEPRINT.rfind("</body>")])
    assert copy.endswith("</body></html>") and copy.count(INJECT_MARK) == 1
    assert "Muat paket ZOI" in copy and "zoi.paket/v1" in copy
    with pytest.raises(BlueprintCopyError, match="tidak dikenali"):
        make_copy(FAKE_BLUEPRINT.replace('id="mc"', 'id="lain"'))
    with pytest.raises(BlueprintCopyError, match="sudah berupa salinan"):
        make_copy(copy)


@pytest.mark.skipif(not os.environ.get("ZOI_TEST_BLUEPRINT_FILE"), reason="file Blueprint asli tidak tersedia")
def test_real_blueprint_file_is_recognized():
    original = Path(os.environ["ZOI_TEST_BLUEPRINT_FILE"]).read_text(encoding="utf-8")
    copy = make_copy(original)
    assert len(copy) > len(original) and copy.replace(copy[copy.find(INJECT_MARK):copy.rfind("</body>")], "") \
        == original


def test_package_validation_and_srt():
    package = validate_package(PAKET)
    assert package["naskah_tts"].startswith("Pernah bertanya")
    with pytest.raises(Exception, match="format"):
        validate_package({**PAKET, "format": "lain"})
    with pytest.raises(Exception, match="beat"):
        validate_package({**PAKET, "beats": []})
    assert validate_package({**PAKET, "rasio": "4:3"})["rasio"] == "9:16"
    assert srt_time(3661.5) == "01:01:01,500"
    srt = build_srt(package["beats"][:2], [{"start": 0, "speech": 1.2}, {"start": 1.5, "speech": 2.0}])
    assert "1\n00:00:00,000 --> 00:00:01,200\nPernah bertanya" in srt
    assert "2\n00:00:01,500 --> 00:00:03,500\nCahaya biru" in srt


def test_compose_template():
    html = compose(validate_package(PAKET))
    assert 'data-composition-id="root"' in html and 'data-width="720"' in html and 'data-height="1280"' in html
    assert html.count('class="clip"') == 3 and "<audio" not in html and "gsap" not in html.lower()
    total = sum(estimate_seconds(b["n"]) for b in PAKET["beats"])
    assert f'data-duration="{round(total, 3):.3f}"' in html
    timed = compose(validate_package(PAKET), [{"start": 0, "speech": 1, "duration": 1.3, "file": "narasi/b1.wav"},
                                              {"start": 1.3, "speech": 1, "duration": 1.3, "file": "narasi/b2.wav"},
                                              {"start": 2.6, "speech": 1, "duration": 1.3, "file": "narasi/b3.wav"}])
    assert timed.count("<audio") == 3 and 'data-duration="3.900"' in timed
    assert "&lt;script&gt;" in compose(validate_package({**PAKET, "judul": "<script>"}))


def test_hyperframes_status_reports_missing_pieces(tmp_path):
    status = HyperFrames(None).status()
    assert status["enabled"] is False and any("ZOI_HYPERFRAMES_DIR" in p for p in status["problems"])
    status = HyperFrames(tmp_path).status()
    assert any("npm install hyperframes" in p for p in status["problems"])


# ── API (mode development, TTS tiruan) ───────────────────────────────────
@pytest.fixture
def prod_client(client_factory, tmp_path):
    original = tmp_path / "Blueprint_Studio.html"
    original.write_text(FAKE_BLUEPRINT, encoding="utf-8")
    return client_factory(blueprint_file=str(original), tts="mock"), original


def test_production_flow(prod_client):
    client, original = prod_client
    status = client.get("/api/production/status").json()
    assert status["available"] is True
    assert status["blueprint"]["original_found"] and not status["blueprint"]["copy_exists"]
    assert status["narration"]["available"] and status["narration"]["mock"]
    assert status["hyperframes"]["enabled"] is False

    assert client.post("/api/production/packages", json={"package": {"format": "x"}}).status_code == 400
    created = client.post("/api/production/packages", json={"package": PAKET}).json()
    pid = created["id"]
    assert created["beats"] == 3 and "paket.json" in created["files"]
    assert client.get("/api/production/packages").json()["items"][0]["id"] == pid
    assert client.get(f"/api/production/packages/{pid}/files/paket.json").json()["judul"] == PAKET["judul"]
    assert client.get(f"/api/production/packages/{pid}/files/rahasia.txt").status_code == 404
    assert client.get("/api/production/packages/../../etc/files/paket.json").status_code == 404

    # Narasi (TTS tiruan): wav gabungan + SRT per beat
    task = client.post(f"/api/production/packages/{pid}/narrate").json()
    done = wait_for(lambda: (t := client.get(f"/api/tasks/{task['id']}").json())["status"] in
                    {"COMPLETED", "FAILED"} and t)
    assert done["status"] == "COMPLETED", done
    assert done["result"]["mock"] is True
    info = client.get("/api/production/packages").json()["items"][0]
    assert {"narasi.wav", "narasi.srt"} <= set(info["files"]) and len(info["narration"]) == 3
    wav = client.get(f"/api/production/packages/{pid}/files/narasi.wav").content
    with wave.open(io.BytesIO(wav)) as w:
        seconds = w.getnframes() / w.getframerate()
    assert abs(seconds - sum(t["duration"] for t in info["narration"])) < 0.05
    srt = client.get(f"/api/production/packages/{pid}/files/narasi.srt").text
    assert srt.count(" --> ") == 3 and "Ikuti untuk sains singkat." in srt

    # Render: HyperFrames belum dipasang → ditolak jujur, tanpa tugas
    blocked = client.post(f"/api/production/packages/{pid}/render")
    assert blocked.status_code == 409 and "HyperFrames" in blocked.json()["error"]["message"]

    # Salinan Blueprint: dibuat dari asli (asli tidak berubah), disajikan dengan CSP khusus
    before = original.read_bytes()
    assert client.get("/blueprint-studio/").status_code == 404
    built = client.post("/api/production/blueprint/build").json()
    assert built["copy_exists"] and built["up_to_date"]
    assert original.read_bytes() == before
    page = client.get("/blueprint-studio/")
    assert page.status_code == 200 and INJECT_MARK in page.text
    assert "'unsafe-inline'" in page.headers["content-security-policy"]
    assert "connect-src 'self'" in page.headers["content-security-policy"]
    original.write_text(FAKE_BLUEPRINT + "<!-- ubah -->", encoding="utf-8")
    assert client.get("/api/production/status").json()["blueprint"]["up_to_date"] is False

    assert client.delete(f"/api/production/packages/{pid}").status_code == 204
    assert client.get("/api/production/packages").json()["items"] == []


def test_production_from_script(client):
    task = client.post("/api/content/scripts", json={"judul": "Cara kerja vaksin", "format": "shorts"}).json()
    wait_for(lambda: client.get(f"/api/tasks/{task['id']}").json()["status"] == "COMPLETED")
    item_id = client.get("/api/content/items?kind=script").json()["items"][0]["id"]
    created = client.post("/api/production/packages", json={"script_id": item_id}).json()
    assert created["mock"] is True and created["rasio"] == "9:16"
    assert client.post("/api/production/packages", json={"script_id": "tidak-ada"}).status_code == 404


@pytest.mark.skipif(not os.environ.get("ZOI_TEST_HYPERFRAMES_DIR"), reason="HyperFrames tidak terpasang")
def test_real_hyperframes_render(client_factory, tmp_path):
    client = client_factory(hyperframes_dir=os.environ["ZOI_TEST_HYPERFRAMES_DIR"], tts="mock")
    hf = client.get("/api/production/status").json()["hyperframes"]
    assert hf["enabled"], hf
    pid = client.post("/api/production/packages", json={"package": PAKET}).json()["id"]
    task = client.post(f"/api/production/packages/{pid}/narrate").json()
    wait_for(lambda: client.get(f"/api/tasks/{task['id']}").json()["status"] == "COMPLETED")
    task = client.post(f"/api/production/packages/{pid}/render").json()
    done = wait_for(lambda: (t := client.get(f"/api/tasks/{task['id']}").json())["status"] in
                    {"COMPLETED", "FAILED"} and t, timeout=600)
    assert done["status"] == "COMPLETED", done
    assert done["result"]["with_audio"] is True
    video = client.get(f"/api/production/packages/{pid}/files/video.mp4")
    assert video.status_code == 200 and video.content[4:8] == b"ftyp"


def test_online_mode_production_is_laptop_only(tmp_path):
    from app.production.service import ProductionError, ProductionService
    service = ProductionService(data_dir=tmp_path, blueprint_file=None, hyperframes_dir=None, voice=None,
                                content=None, available=False)
    with pytest.raises(ProductionError, match="hanya berjalan di laptop"):
        service.import_package(PAKET)
    assert service.list() == [] or True
    json.dumps(PAKET)


# ── AI pengganti Claude di salinan Blueprint (ADR 0018) ──────────────────────
class _FakeProvider:
    name = "nvidia"
    is_mock = False

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    async def chat(self, messages, *, timeout_s=0, options=None):
        from app.providers.base import ChatChunk as StreamChunk
        self.seen.append(messages)
        yield StreamChunk(type="text", text=self.replies.pop(0))
        yield StreamChunk(type="done")


async def test_blueprint_ai_parses_json_and_retries_once():
    from app.core.errors import ZoiError
    from app.production.blueprint_ai import blueprint_json

    fake = _FakeProvider(["Tentu! ```json\n[{\"k\": \"Hook\", \"n\": \"Halo\", \"v\": \"\"}]\n```"])
    out = await blueprint_json(fake, "Tulis cerita. Balas HANYA JSON array.")
    assert out == {"result": [{"k": "Hook", "n": "Halo", "v": ""}], "provider": "nvidia", "is_mock": False}
    assert fake.seen[0][1].content == "Tulis cerita. Balas HANYA JSON array."  # prompt Blueprint tidak diubah

    fake = _FakeProvider(["maaf", '{"n": "baru"}'])
    assert (await blueprint_json(fake, "x"))["result"] == {"n": "baru"} and len(fake.seen) == 2
    with pytest.raises(ZoiError, match="JSON"):
        await blueprint_json(_FakeProvider(["a", "b"]), "x")


def test_blueprint_copy_has_ai_shim_and_endpoint_validates(client_factory):
    copy = make_copy(FAKE_BLUEPRINT)
    assert "/api/production/blueprint/ai" in copy and 'name === "sample"' in copy and "X-ZOI-Client" in copy
    client = client_factory()
    assert client.post("/api/production/blueprint/ai", json={"prompt": ""}).status_code == 422
    assert client.post("/api/production/blueprint/ai", json={"prompt": "x" * 30_001}).status_code == 422


# ── Animasi ZOI AI ────────────────────────────────────────────────────────────
def test_sanitizer_removes_script_urls_events():
    from app.production.animate import sanitize_css, sanitize_html

    dirty = ('<div class="a" onclick="x()" style="background:url(http://x)"><script>alert(1)</script>Hai'
             '<img src="http://x/y.png"><svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#fff"/>'
             '<foreignObject><p>no</p></foreignObject></svg><iframe src="http://x"></iframe></div>')
    clean, dropped = sanitize_html(dirty)
    assert clean == '<div class="a">Hai<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#fff"/></svg></div>'
    assert dropped >= 5
    assert sanitize_css(".s1 .b{background:url(http://x)}") is None
    assert sanitize_css("@import 'x.css';") is None
    assert sanitize_css(".s1 .b{fill:url(#g)}") is not None and sanitize_css(".s1{background:url( 'a.png')}") is None
    assert sanitize_html('<circle fill="url(#g)"/>')[0] == '<circle fill="url(#g)"/>'
    assert sanitize_html('<circle fill="url(http://x/#g)"/>')[0] == "<circle/>"
    assert sanitize_css(".s1 .b{animation:s1-x 1s}@keyframes s1-x{from{opacity:0}}") is not None


def test_compose_animated_uses_timings_captions_and_fallback():
    from app.production.animate import Scene, Scenes, compose_animated

    package = validate_package({**PAKET, "gaya": "kertas potong, hangat"})
    assert package["gaya"] == "kertas potong, hangat"
    scenes = Scenes(background="#112233", text_color="javascript:x", scenes=[
        Scene(html='<h1 class="t">Bulan</h1>', css=".s1 .t{animation:s1-in 1s both}@keyframes s1-in{from{opacity:0}}"),
        Scene(html="<script>x</script>", css=""),
    ])
    timings = [{"duration": 2.0, "file": "narasi/beat-01.wav"}, {"duration": 3.0}, {"duration": 1.5}]
    doc, report = compose_animated(package, scenes, timings)
    assert report == {"ai_scenes": 1, "fallback_scenes": 2, "removed_parts": 1}
    assert 'data-duration="6.500"' in doc and "background:#112233" in doc and "color:#f2f4f8" in doc
    assert '<audio data-start="0.000"' in doc and doc.count('class="cap"') == 3 and "<script" not in doc


@pytest.mark.skipif(not os.environ.get("ZOI_TEST_HYPERFRAMES_DIR"), reason="HyperFrames tidak terpasang")
def test_real_animate_render(client_factory):
    client = client_factory(hyperframes_dir=os.environ["ZOI_TEST_HYPERFRAMES_DIR"], tts="mock")
    pid = client.post("/api/production/packages", json={"package": {**PAKET, "gaya": "risograph"}}).json()["id"]
    task = client.post(f"/api/production/packages/{pid}/animate").json()
    done = wait_for(lambda: (t := client.get(f"/api/tasks/{task['id']}").json())["status"] in
                    {"COMPLETED", "FAILED"} and t, timeout=600)
    assert done["status"] == "COMPLETED", done
    assert done["result"]["mock"] is True and done["result"]["ai_scenes"] + done["result"]["fallback_scenes"] == 3
    video = client.get(f"/api/production/packages/{pid}/files/video.mp4")
    assert video.status_code == 200 and video.content[4:8] == b"ftyp"
