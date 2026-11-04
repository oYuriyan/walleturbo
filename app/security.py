import hashlib
import json
import secrets
from urllib.parse import urlparse
from fastapi import HTTPException, Request
from redis import Redis
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

store = Redis.from_url(settings().redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
COOKIE = "walleturbo_session"
SESSION_TTL = 1800
MAX_SESSION = 28800
LIMIT_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def session_key(sid):
    return "session:" + hashlib.sha256(sid.encode()).hexdigest()


def current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Entre na sua conta para continuar")
    return user


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        import time
        conf = settings()
        # Não confiar em X-Forwarded-For fornecido pelo cliente.
        peer = request.client.host if request.client else "unknown"
        path = request.url.path
        try:
            if path.startswith(("/api", "/auth")):
                key = "rate:" + hashlib.sha256(peer.encode()).hexdigest()
                limit = 120
                count = store.eval(LIMIT_SCRIPT, 1, key, 60)
                if count > limit:
                    return JSONResponse({"detail": "Muitas requisições. Tente em um minuto."}, 429, headers={"Retry-After": "60"})
            sid = request.cookies.get(COOKIE, "")
            raw = store.get(session_key(sid)) if len(sid) == 64 else None
            session = json.loads(raw) if raw else {}
            if session and time.time() - session.get("created", 0) > MAX_SESSION:
                store.delete(session_key(sid))
                session = {}
            request.scope["session"] = session
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request.headers.get("origin") != conf.base_url:
                    return JSONResponse({"detail": "Origem não autorizada"}, 403)
                if path.startswith("/api") and not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.get("csrf", secrets.token_hex(32))):
                    return JSONResponse({"detail": "Token de segurança inválido"}, 403)
            response = await call_next(request)
            if request.scope.get("logout"):
                if sid:
                    store.delete(session_key(sid))
                response.delete_cookie(COOKIE, path="/")
            elif session:
                if not raw or request.scope.get("rotate_session"):
                    if raw:
                        store.delete(session_key(sid))
                    sid = secrets.token_hex(32)
                session.setdefault("created", time.time())
                ttl = max(1, min(SESSION_TTL, int(MAX_SESSION - (time.time() - session["created"]))))
                store.setex(session_key(sid), ttl, json.dumps(session))
                response.set_cookie(COOKIE, sid, max_age=ttl, httponly=True, secure=conf.base_url.startswith("https://"), samesite="lax", path="/")
        except Exception as exc:
            from redis.exceptions import RedisError
            if isinstance(exc, RedisError):
                return JSONResponse({"detail": "Serviço temporariamente indisponível"}, 503)
            raise
        response.headers.update({
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store", "X-Frame-Options": "DENY",
        })
        if conf.base_url.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class BodyLimitMiddleware:
    """Limita também corpos chunked, antes de qualquer parser ou autenticação."""
    def __init__(self, app, limit=300_000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.limit:
                return await JSONResponse({"detail": "Corpo da requisição excede 300 KB"}, 413)(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        cursor = 0

        async def replay():
            nonlocal cursor
            if cursor < len(chunks):
                message = chunks[cursor]
                cursor += 1
                return message
            return await receive()

        await self.app(scope, replay, send)
