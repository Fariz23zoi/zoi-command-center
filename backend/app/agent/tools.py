"""Registry tool agen. Setiap tool punya skema argumen (Pydantic) dan tingkat izin.

Tingkat `publish` (upload, publikasi, kirim ke orang lain) TIDAK ADA: registry menolak mendaftarkannya,
termasuk tool yang namanya mengarah ke publikasi.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class Permission(StrEnum):
    READ = "read"  # otomatis setelah rencana disetujui
    WRITE_LOCAL = "write_local"  # izin per langkah (bisa diubah jadi otomatis per tool)
    EXTERNAL = "external"  # selalu minta izin (mis. kuota YouTube API, Phase 6)


FORBIDDEN_NAME = re.compile(r"publish|publikasi|terbit|upload|unggah|posting|post_|kirim_pesan|send_|share|bagikan",
                            re.IGNORECASE)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolError(RuntimeError):
    """Kegagalan tool yang dilaporkan apa adanya."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    permission: Permission
    args_model: type[BaseModel]
    run: Callable[[Any], Awaitable[dict[str, Any]]]

    def validate(self, args: dict[str, Any]) -> BaseModel:
        return self.args_model.model_validate(args)

    def spec(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "permission": self.permission.value,
                "args_schema": schema}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not isinstance(tool.permission, Permission):
            raise ValueError(f"Tingkat izin tidak dikenal untuk {tool.name}: {tool.permission!r}")
        if FORBIDDEN_NAME.search(tool.name):
            raise ValueError(f"Tool '{tool.name}' tampak seperti tool publikasi — ZOI tidak punya tool publikasi.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", tool.name):
            raise ValueError(f"Nama tool tidak valid: {tool.name!r}")
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' sudah terdaftar.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def check_step(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """None bila langkah valid; selain itu alasan (Bahasa Indonesia)."""
        tool = self.get(tool_name)
        if tool is None:
            return f"tool '{tool_name}' tidak ada"
        try:
            tool.validate(args)
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'argumen'}: {e['msg']}" for e in exc.errors()[:3])
            return f"argumen {tool_name} tidak valid ({problems})"
        return None
