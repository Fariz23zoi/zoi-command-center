"""Phase 4 — suara: konfigurasi, Mock, Whisper (tanpa unduh), Piper (proses terpisah), layanan, API."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

from app.config.modes import ConfigError, resolve_runtime
from app.config.settings import Settings
from app.security.cost_guard import CostGuard
from app.voice.base import MAX_AUDIO_BYTES, MAX_TTS_CHARS, VoiceError
from app.voice.mock import MOCK_TRANSCRIPT, MockSTT, MockTTS
from app.voice.piper import PiperHttpTTS
from app.voice.service import VoicePreferences, VoiceService
from app.voice.wav import is_wav, tone_wav, wav_seconds
from app.voice.whisper import WhisperSTT
from tests.fake_piper import FakePiper

PIPER = "http://127.0.0.1:5000"


def guard() -> CostGuard:
    return CostGuard.build(ollama_url="http://127.0.0.1:11434", extra_hosts=[], recorder=None)


# ── konfigurasi ──────────────────────────────────────────────────────────────
def test_voice_defaults_per_mode():
    dev = resolve_runtime(Settings())
    assert (dev.stt, dev.tts) == ("mock", "mock")
    local = resolve_runtime(Settings(mode="local", ollama_model="qwen3:4b"))
    assert (local.stt, local.tts) == ("whisper", "piper")
    assert any("ZOI_WHISPER_MODEL_DIR" in w for w in local.warnings)


@pytest.mark.parametrize("field", ["stt", "tts"])
def test_mock_voice_rejected_in_local_mode(field):
    with pytest.raises(ConfigError, match="Mock"):
        resolve_runtime(Settings(mode="local", ollama_model="qwen3:4b", **{field: "mock"}))


def test_invalid_piper_url_rejected():
    with pytest.raises(ConfigError, match="ZOI_PIPER_URL"):
        resolve_runtime(Settings(piper_url="bukan-url"))


# ── Mock ─────────────────────────────────────────────────────────────────────
async def test_mock_stt_is_labeled_and_has_no_digits():
    result = await MockSTT().transcribe(tone_wav(1.0), "id")
    assert result.text == MOCK_TRANSCRIPT and result.is_mock and result.text.startswith("[MOCK]")
    assert not any(ch.isdigit() for ch in result.text)
    assert result.audio_seconds == pytest.approx(1.0, abs=0.01)


async def test_mock_tts_returns_wav_scaled_by_speed():
    slow = await MockTTS().synthesize("Halo, saya ZOI.", 1.0)
    fast = await MockTTS().synthesize("Halo, saya ZOI.", 2.0)
    assert is_wav(slow) and is_wav(fast)
    assert wav_seconds(fast) < wav_seconds(slow)


# ── Whisper: hanya dari folder lokal, tidak pernah mengunduh ─────────────────
async def test_whisper_without_folder_reports_honestly():
    status = await WhisperSTT(None).status()
    assert not status.available and "ZOI_WHISPER_MODEL_DIR" in status.detail
    with pytest.raises(VoiceError, match="ZOI_WHISPER_MODEL_DIR"):
        await WhisperSTT(None).transcribe(b"x", "id")


async def test_whisper_incomplete_folder(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    status = await WhisperSTT(tmp_path).status()
    assert not status.available and "model.bin" in status.detail


async def test_whisper_package_missing(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    status = await WhisperSTT(tmp_path).status()
    assert not status.available and "requirements-voice.txt" in status.detail


class FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeWhisperModel:
    created: list[dict] = []

    def __init__(self, path: str, **kwargs) -> None:
        FakeWhisperModel.created.append({"path": path, **kwargs})
        self.duration = 2.0

    def transcribe(self, audio, language=None, **kwargs):
        assert audio.read(4) == b"RIFF"
        info = types.SimpleNamespace(duration=self.duration, language=language or "id")
        return iter([FakeSegment(" Halo ZOI, "), FakeSegment("apa kabar? ")]), info


@pytest.fixture
def whisper_dir(tmp_path, monkeypatch) -> Path:
    for name in ("model.bin", "config.json"):
        (tmp_path / name).write_bytes(b"x")
    FakeWhisperModel.created.clear()
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    return tmp_path


async def test_whisper_loads_only_local_files_on_cpu_int8(whisper_dir):
    stt = WhisperSTT(whisper_dir)
    assert (await stt.status()).available
    result = await stt.transcribe(tone_wav(0.5), "id")
    assert result.text == "Halo ZOI, apa kabar?" and result.language == "id" and not result.is_mock
    created = FakeWhisperModel.created
    assert len(created) == 1 and created[0]["local_files_only"] is True
    assert created[0]["path"] == str(whisper_dir)  # path folder, bukan nama model yang bisa memicu unduhan
    assert (created[0]["device"], created[0]["compute_type"]) == ("cpu", "int8")
    await stt.transcribe(tone_wav(0.5), "auto")
    assert len(FakeWhisperModel.created) == 1  # model dimuat sekali


async def test_whisper_rejects_too_long_audio(whisper_dir, monkeypatch):
    monkeypatch.setattr(FakeWhisperModel, "__init__", lambda self, path, **kw: setattr(self, "duration", 120.0))
    with pytest.raises(VoiceError, match="terlalu panjang"):
        await WhisperSTT(whisper_dir).transcribe(tone_wav(0.2), "id")


# ── Piper: server terpisah ───────────────────────────────────────────────────
async def test_piper_status_and_synthesis_with_speed():
    fake = FakePiper()
    tts = PiperHttpTTS(PIPER, guard(), transport=fake.transport())
    status = await tts.status()
    assert status.available and status.model == "id_ID-news_tts-medium"
    audio = await tts.synthesize("Halo, saya ZOI.", 2.0)
    assert is_wav(audio) and fake.requests[-1]["length_scale"] == 0.5


async def test_piper_non_wav_and_unreachable_are_errors():
    with pytest.raises(VoiceError, match="WAV"):
        await PiperHttpTTS(PIPER, guard(), transport=FakePiper(broken_audio=True).transport()).synthesize("a", 1.0)
    down = PiperHttpTTS("http://127.0.0.1:9", guard())
    assert "tidak dapat dihubungi" in (await down.status()).detail
    with pytest.raises(VoiceError, match="tidak dapat dihubungi"):
        await down.synthesize("halo", 1.0)


@pytest.mark.parametrize("path", ["/download", "/all-voices"])
async def test_piper_download_endpoints_blocked(path):
    from app.voice.piper import ForbiddenPiperCall

    fake = FakePiper()
    tts = PiperHttpTTS(PIPER, guard(), transport=fake.transport())
    with pytest.raises(ForbiddenPiperCall):
        async with tts._client() as client:
            await client.post(path, json={"voice": "id_ID-news_tts-medium"})
    assert fake.requests == []


def test_zoi_never_imports_piper_code():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = [p for p in root.rglob("*.py") if "import piper" in p.read_text() or "from piper" in p.read_text()]
    assert offenders == []


# ── layanan ──────────────────────────────────────────────────────────────────
@pytest.fixture
def db(tmp_path):
    from app.db.migrations import upgrade_database
    from app.db.session import Database

    path = tmp_path / "zoi.db"
    upgrade_database(path)
    database = Database(path)
    yield database
    database.dispose()


async def test_real_piper_requires_license_acceptance(db):
    service = VoiceService(stt=MockSTT(), tts=PiperHttpTTS(PIPER, guard(), transport=FakePiper().transport()), db=db)
    with pytest.raises(VoiceError, match="lisensi"):
        await service.speak("Halo")
    assert (await service.status())["reply_engine"] == "browser"
    service.save_preferences(VoicePreferences(piper_license_accepted=True, speech_rate=1.5))
    assert is_wav(await service.speak("Halo"))
    assert (await service.status())["reply_engine"] == "piper"
    service.save_preferences(VoicePreferences(piper_license_accepted=True, tts_engine="browser"))
    assert (await service.status())["reply_engine"] == "browser"


async def test_service_limits(db):
    service = VoiceService(stt=MockSTT(), tts=MockTTS(), db=db)
    with pytest.raises(VoiceError, match="kosong"):
        await service.transcribe(b"", None)
    with pytest.raises(VoiceError, match="terlalu besar"):
        await service.transcribe(b"x" * (MAX_AUDIO_BYTES + 1), None)
    with pytest.raises(VoiceError, match="terlalu panjang"):
        await service.speak("a" * (MAX_TTS_CHARS + 1))
    with pytest.raises(VoiceError, match="Tidak ada teks"):
        await service.speak("   ")


# ── API ──────────────────────────────────────────────────────────────────────
def test_api_development_mock_flow(client):
    status = client.get("/api/voice/status").json()
    assert status["stt"]["is_mock"] and status["tts"]["is_mock"] and status["reply_engine"] == "piper"
    assert status["can_download"] is False and status["stores_recordings"] is False
    assert "malayalam" in status["catalog"]["piper"]["license_note"]

    result = client.post("/api/voice/transcribe?language=id", content=tone_wav(0.5),
                         headers={"Content-Type": "audio/wav"}).json()
    assert result["text"] == MOCK_TRANSCRIPT and result["is_mock"]

    audio = client.post("/api/voice/speak", json={"text": "Halo, saya ZOI."})
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav" and is_wav(audio.content)
    assert audio.headers["cache-control"] == "no-store"


def test_api_limits_and_validation(client):
    too_big = client.post("/api/voice/transcribe", content=b"x",
                          headers={"Content-Type": "audio/webm", "Content-Length": str(MAX_AUDIO_BYTES + 1)})
    assert too_big.status_code == 413
    assert client.post("/api/voice/transcribe", content=b"").status_code == 400
    assert client.post("/api/voice/transcribe?language=fr", content=b"x").status_code == 422
    assert client.post("/api/voice/speak", json={"text": "a" * (MAX_TTS_CHARS + 1)}).status_code == 400


def test_api_preferences_roundtrip(client):
    assert client.get("/api/voice/preferences").json() == VoicePreferences().model_dump()
    prefs = {**VoicePreferences().model_dump(), "speak_replies": True, "speech_rate": 1.25, "language": "auto"}
    assert client.put("/api/voice/preferences", json=prefs).json() == prefs
    assert client.get("/api/voice/preferences").json() == prefs
    assert client.put("/api/voice/preferences", json={**prefs, "speech_rate": 3}).status_code == 422
    assert client.put("/api/voice/preferences", json={**prefs, "cloud_voice": True}).status_code == 422


def test_api_requires_client_header_for_recording(client):
    response = client.post("/api/voice/transcribe", content=b"x", headers={"X-ZOI-Client": ""})
    assert response.status_code == 403


def test_api_local_mode_is_honest_without_models(client_factory):
    client = client_factory(mode="local", ollama_model="qwen3:4b", piper_url="http://127.0.0.1:9")
    status = client.get("/api/voice/status").json()
    assert not status["stt"]["available"] and not status["tts"]["available"]
    assert status["reply_engine"] == "browser"
    failed = client.post("/api/voice/transcribe", content=tone_wav(0.2))
    assert failed.status_code == 400 and "ZOI_WHISPER_MODEL_DIR" in failed.json()["error"]["message"]


# ── integrasi dengan model sungguhan (opsional) ──────────────────────────────
REAL_WHISPER = os.environ.get("ZOI_TEST_WHISPER_DIR")
REAL_PIPER = os.environ.get("ZOI_TEST_PIPER_URL")


@pytest.mark.skipif(not (REAL_WHISPER and REAL_PIPER),
                    reason="Butuh model sungguhan: ZOI_TEST_WHISPER_DIR dan ZOI_TEST_PIPER_URL")
async def test_real_roundtrip_piper_to_whisper_in_indonesian():
    sentence = "Selamat pagi, hari ini kita membuat video tentang memasak nasi goreng."
    tts = PiperHttpTTS(REAL_PIPER or "", CostGuard.build(ollama_url="http://127.0.0.1:11434", extra_hosts=[],
                                                         recorder=None))
    audio = await tts.synthesize(sentence, 1.0)
    result = await WhisperSTT(Path(REAL_WHISPER or "")).transcribe(audio, "id")
    heard = {w.strip(".,").lower() for w in result.text.split()}
    expected = {w.strip(".,").lower() for w in sentence.split()}
    assert len(heard & expected) >= len(expected) // 2, result.text


def test_browser_recording_formats_decode_with_real_faster_whisper():
    """Rekaman browser (webm/opus) harus bisa didekode. Menangkap ketidakcocokan versi PyAV (mis. av 19)."""
    av = pytest.importorskip("av")
    audio_mod = pytest.importorskip("faster_whisper.audio")
    import io

    import numpy as np

    buffer = io.BytesIO()
    container = av.open(buffer, "w", format="webm")
    stream = container.add_stream("libopus", rate=48_000)
    stream.layout = "mono"
    samples = (np.sin(2 * np.pi * 220 * np.arange(48_000) / 48_000) * 0.3).astype(np.float32)
    for i in range(0, len(samples), 960):
        frame = av.AudioFrame.from_ndarray(samples[i:i + 960].reshape(1, -1), format="flt", layout="mono")
        frame.rate = 48_000
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    decoded = audio_mod.decode_audio(io.BytesIO(buffer.getvalue()), sampling_rate=16_000)
    assert len(decoded) / 16_000 == pytest.approx(1.0, abs=0.05)


def test_voice_requirements_pin_compatible_pyav():
    text = (Path(__file__).resolve().parents[1] / "requirements-voice.txt").read_text()
    assert "faster-whisper==1.2.1" in text and "av==18.0.0" in text
