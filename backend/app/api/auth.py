"""API login mode online. Di mode development/local auth nonaktif dan endpoint ini menjawab apa adanya."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.context import AppContext, get_ctx
from app.core.errors import ZoiError
from app.security.auth import SESSION_COOKIE, SESSION_DAYS, AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


class SetupBody(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)


def _set_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=secure, samesite="lax", path="/")


def _secure(ctx: AppContext) -> bool:
    return ctx.runtime.is_online and ctx.runtime.public_url.startswith("https://")


@router.get("/status")
def status(request: Request) -> dict:
    ctx = get_ctx(request)
    body = ctx.auth.status()
    body["logged_in"] = ctx.auth.check(request.cookies.get(SESSION_COOKIE))
    return body


@router.post("/setup")
def setup(body: SetupBody, request: Request, response: Response) -> dict:
    ctx = get_ctx(request)
    try:
        token = ctx.auth.setup(body.token, body.password)
    except AuthError as exc:
        raise ZoiError(exc.message, code=exc.code,
                       status_code=403 if exc.code == "setup_token_salah" else 400) from exc
    _set_cookie(response, token, secure=_secure(ctx))
    return {"ok": True}


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict:
    ctx = get_ctx(request)
    try:
        token = ctx.auth.login(body.password)
    except AuthError as exc:
        raise ZoiError(exc.message, code=exc.code, status_code=429 if exc.code == "terkunci" else 401) from exc
    _set_cookie(response, token, secure=_secure(ctx))
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    ctx = get_ctx(request)
    ctx.auth.logout(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.post("/logout-all")
def logout_all(request: Request, response: Response) -> dict:
    ctx = get_ctx(request)
    ctx.auth.logout_all()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
