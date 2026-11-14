"""Tugas latar belakang "Uji model AI" — berjalan di Task Manager (progress, riwayat, batal antar-prompt)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.evaluation import load_prompts, run_prompt, save_evaluation, summarize
from app.db.base import utcnow
from app.db.session import Database
from app.providers.base import LocalModelAdmin
from app.tasks.manager import TaskContext, TaskKind

KIND = "model_eval"
# Satu prompt di CPU lambat bisa memakan beberapa menit (termasuk memuat model ke RAM).
PROMPT_TIMEOUT_S = 900


def model_eval_kind(*, db: Database, admin: LocalModelAdmin, run_async: Callable[..., Any]) -> TaskKind:
    def run(ctx: TaskContext) -> dict[str, Any]:
        model = ctx.params["model"]
        provider = admin.with_model(model)  # instance terpisah: chat yang sedang berjalan tidak terganggu
        started = utcnow()
        version = run_async(admin.version())
        prompts = load_prompts()["prompts"]
        results = []
        for index, item in enumerate(prompts):
            ctx.progress(int(index / len(prompts) * 100), f"{model} · prompt {index + 1}/{len(prompts)} ({item['id']})")
            results.append(run_async(run_prompt(provider, item), timeout=PROMPT_TIMEOUT_S))
        ctx.check_cancelled()
        summary = summarize(results)
        saved = save_evaluation(db, model=model, ollama_version=version, started_at=started, results=results,
                                summary=summary)
        return {"evaluation_id": saved["id"], "model": model, "summary": summary}

    return TaskKind(kind=KIND, name="Uji model AI", func=run)

