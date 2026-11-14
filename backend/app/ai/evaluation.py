"""Uji kecocokan model (P3-8). Semua angka diukur langsung saat uji berjalan di mesin ini:
waktu ke token pertama (jam dinding), token/detik dan jumlah token (dilaporkan Ollama), validitas JSON,
ketepatan pemanggilan tool. Kualitas jawaban percakapan TIDAK dinilai otomatis — pengguna memberi 👍/👎.
"""

from __future__ import annotations

import json
import platform
import statistics
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.structured import StructuredOutputError, chat_json
from app.chat.service import SYSTEM_PROMPT
from app.db.base import utcnow
from app.db.models import ModelEvaluation
from app.db.session import Database
from app.providers.base import ChatMessage, ChatStats, LLMProvider, ToolSpec

PROMPTS_PATH = Path(__file__).resolve().parent / "eval_prompts.json"
RESPONSE_LIMIT = 2000


class EvalNotAllowed(RuntimeError):
    pass


# ── skema untuk prompt JSON ────────────────────────────────────────────────────
class Idea(BaseModel):
    judul: str = Field(min_length=3)
    alasan: str = Field(min_length=3)


class Ideas(BaseModel):
    ide: list[Idea] = Field(min_length=3, max_length=3)


class Sentiment(BaseModel):
    sentimen: Literal["positif", "netral", "negatif"]
    alasan: str = Field(min_length=3)


class Outline(BaseModel):
    judul: str = Field(min_length=3)
    bagian: list[str] = Field(min_length=3)


SCHEMAS: dict[str, type[BaseModel]] = {"ideas": Ideas, "sentiment": Sentiment, "outline": Outline}

TOOLS = [
    ToolSpec("buat_tugas", "Membuat tugas baru di Task Manager ZOI.",
             {"type": "object", "properties": {"judul": {"type": "string", "description": "Judul tugas"}},
              "required": ["judul"]}),
    ToolSpec("cari_video", "Mencari video YouTube berdasarkan kata kunci.",
             {"type": "object", "properties": {"kata_kunci": {"type": "string"}}, "required": ["kata_kunci"]}),
    ToolSpec("ubah_status_avatar", "Mengubah status avatar ZOI.",
             {"type": "object", "properties": {"status": {"type": "string",
                                                          "enum": ["IDLE", "THINKING", "SPEAKING"]}},
              "required": ["status"]}),
]


@cache
def load_prompts() -> dict[str, Any]:
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


@dataclass
class PromptResult:
    id: str
    category: str
    prompt: str
    passed: bool | None  # None = dinilai pengguna (kategori chat)
    response: str = ""
    error: str | None = None
    first_token_s: float | None = None
    tokens_per_s: float | None = None
    output_tokens: int | None = None
    thinking_chars: int = 0
    attempts: int | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Run:
    parts: list[str] = field(default_factory=list)
    thinking: int = 0
    first_token_s: float | None = None
    stats: ChatStats | None = None
    tool: tuple[str, dict[str, Any]] | None = None
    error: str | None = None


async def _stream(provider: LLMProvider, messages: list[ChatMessage], tools: list[ToolSpec] | None) -> _Run:
    run = _Run()
    start = time.monotonic()
    async for chunk in provider.chat(messages, tools=tools):
        if chunk.type in ("text", "thinking", "tool_call") and run.first_token_s is None:
            run.first_token_s = round(time.monotonic() - start, 2)
        if chunk.type == "text":
            run.parts.append(chunk.text)
        elif chunk.type == "thinking":
            run.thinking += len(chunk.text)
        elif chunk.type == "tool_call" and chunk.tool_call and run.tool is None:
            run.tool = (chunk.tool_call.name, chunk.tool_call.arguments)
        elif chunk.type == "error":
            run.error = chunk.error or "Penyedia AI gagal."
            break
        elif chunk.type == "done":
            run.stats = chunk.stats
            break
    return run


def _tool_ok(expect: dict[str, Any], got: tuple[str, dict[str, Any]] | None) -> tuple[bool, str]:
    if expect.get("name") is None:
        if got is None:
            return True, "tidak memanggil tool (benar)"
        return False, f"memanggil {got[0]} padahal tidak perlu"
    if got is None:
        return False, "tidak memanggil tool"
    name, args = got
    if name != expect["name"]:
        return False, f"memanggil {name}, seharusnya {expect['name']}"
    for key, value in expect.get("args", {}).items():
        actual = args.get(key)
        if not isinstance(actual, str) or not actual.strip() or (value != "*" and actual != value):
            return False, f"argumen {key} salah: {actual!r}"
    return True, f"memanggil {name} dengan argumen benar"


async def run_prompt(provider: LLMProvider, item: dict[str, Any]) -> PromptResult:
    system = ChatMessage("system", SYSTEM_PROMPT)
    user = ChatMessage("user", item["prompt"])
    category = item["category"]
    result = PromptResult(id=item["id"], category=category, prompt=item["prompt"], passed=None)
    if category == "json":
        start = time.monotonic()
        try:
            out = await chat_json(provider, [system, user], SCHEMAS[item["schema"]])
        except StructuredOutputError as exc:
            result.passed, result.error = False, str(exc)
            return result
        stats = out.stats
        result.passed, result.attempts = True, out.attempts
        result.response = out.raw[:RESPONSE_LIMIT]
        result.detail = "JSON valid" + (" setelah diulang" if out.attempts > 1 else "")
        result.detail += f" · {round(time.monotonic() - start, 1)} dtk total"
    else:
        run = await _stream(provider, [system, user], TOOLS if category == "tool" else None)
        stats = run.stats
        result.response = "".join(run.parts)[:RESPONSE_LIMIT]
        result.first_token_s, result.thinking_chars, result.error = run.first_token_s, run.thinking, run.error
        if run.error:
            result.passed = False
        elif category == "tool":
            result.passed, result.detail = _tool_ok(item["expect"], run.tool)
    if stats is not None:
        rate = stats.tokens_per_second
        result.tokens_per_s = round(rate, 2) if rate else None
        result.output_tokens = stats.output_tokens
    return result


def summarize(results: list[PromptResult]) -> dict[str, Any]:
    def count(category: str) -> dict[str, int]:
        items = [r for r in results if r.category == category]
        return {"passed": sum(1 for r in items if r.passed), "total": len(items)}

    first = [r.first_token_s for r in results if r.first_token_s is not None]
    rates = [r.tokens_per_s for r in results if r.tokens_per_s is not None]
    return {
        "json": count("json"), "tool": count("tool"),
        "chat_errors": sum(1 for r in results if r.category == "chat" and r.error),
        "median_first_token_s": round(statistics.median(first), 2) if first else None,
        "median_tokens_per_s": round(statistics.median(rates), 2) if rates else None,
        "errors": sum(1 for r in results if r.error),
    }


async def evaluate(
    provider: LLMProvider, *, on_progress: Callable[[int, str], None] | None = None,
) -> tuple[list[PromptResult], dict[str, Any]]:
    """`provider` adalah instance khusus uji (model sudah diset) agar chat yang sedang berjalan tidak terganggu."""
    if provider.is_mock or provider.name != "ollama":
        raise EvalNotAllowed("Uji model hanya untuk Ollama — Mock tidak boleh menghasilkan angka performa.")
    results: list[PromptResult] = []
    prompts = load_prompts()["prompts"]
    for index, item in enumerate(prompts):
        if on_progress:
            on_progress(int(index / len(prompts) * 100), f"Prompt {index + 1}/{len(prompts)}: {item['id']}")
        results.append(await run_prompt(provider, item))
    return results, summarize(results)


def save_evaluation(db: Database, *, model: str, ollama_version: str | None, started_at: Any,
                    results: list[PromptResult], summary: dict[str, Any]) -> dict[str, Any]:
    with db.session() as s:
        row = ModelEvaluation(
            id=str(uuid.uuid4()), model=model, machine=platform.node()[:120] or "tidak diketahui",
            ollama_version=ollama_version, prompts_version=load_prompts()["version"], started_at=started_at,
            finished_at=utcnow(), summary_json=json.dumps(summary),
            results_json=json.dumps([r.to_dict() for r in results], ensure_ascii=False), ratings_json="{}",
        )
        s.add(row)
        s.flush()
        return evaluation_dict(row, with_results=False)


def list_evaluations(db: Database, limit: int = 20) -> list[dict[str, Any]]:
    with db.session() as s:
        rows = s.scalars(select(ModelEvaluation).order_by(ModelEvaluation.finished_at.desc()).limit(limit)).all()
        return [evaluation_dict(r, with_results=False) for r in rows]


def get_evaluation(db: Database, evaluation_id: str) -> dict[str, Any] | None:
    with db.session() as s:
        row = s.get(ModelEvaluation, evaluation_id)
        return evaluation_dict(row, with_results=True) if row else None


def rate(
    db: Database, evaluation_id: str, prompt_id: str, rating: Literal["up", "down"] | None,
) -> dict[str, Any] | None:
    with db.session() as s:
        row = s.get(ModelEvaluation, evaluation_id)
        if row is None:
            return None
        chat_ids = {r["id"] for r in json.loads(row.results_json) if r["category"] == "chat"}
        if prompt_id not in chat_ids:
            raise KeyError(prompt_id)
        ratings = json.loads(row.ratings_json)
        if rating is None:
            ratings.pop(prompt_id, None)
        else:
            ratings[prompt_id] = rating
        row.ratings_json = json.dumps(ratings)
        return evaluation_dict(row, with_results=True)


def evaluation_dict(row: ModelEvaluation, *, with_results: bool) -> dict[str, Any]:
    ratings = json.loads(row.ratings_json)
    data: dict[str, Any] = {
        "id": row.id, "model": row.model, "machine": row.machine, "ollama_version": row.ollama_version,
        "prompts_version": row.prompts_version, "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat(), "summary": json.loads(row.summary_json),
        "ratings": {"up": sum(1 for v in ratings.values() if v == "up"),
                    "down": sum(1 for v in ratings.values() if v == "down")},
    }
    if with_results:
        data["results"] = json.loads(row.results_json)
        data["rating_by_prompt"] = ratings
    return data
