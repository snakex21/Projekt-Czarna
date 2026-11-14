"""Middleware bezpieczeństwa (czyste ASGI, bez buforowania odpowiedzi).

- ``BodySizeLimitMiddleware``: odrzuca żądania z ciałem większym niż limit (413),
  zarówno po nagłówku ``Content-Length``, jak i przy transferze chunked.
- ``SecurityHeadersMiddleware``: nagłówki ``X-Content-Type-Options``,
  ``X-Frame-Options``, ``Referrer-Policy``, ``Permissions-Policy`` oraz
  ostrożny ``Content-Security-Policy`` (frontend korzysta z CDN i skryptów
  inline, więc nie ograniczamy ``script-src``).
- ``OriginCheckMiddleware``: dla metod zmieniających stan odrzuca (403) żądania
  z obcym nagłówkiem ``Origin`` - dodatkowa ochrona CSRF obok ciasteczka
  ``SameSite=Strict``.
"""
from __future__ import annotations

import json
from typing import Callable, Iterable

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"content-security-policy", b"frame-ancestors 'self'; object-src 'none'; base-uri 'self'"),
)


async def _send_json(send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode()),
            *SECURITY_HEADERS,
        ],
    })
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    def __init__(self, app, max_bytes_getter: Callable[[], int]) -> None:
        self.app = app
        self._max_bytes = max_bytes_getter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = int(self._max_bytes())
        too_large = f"Żądanie za duże (limit {limit} B)"
        has_length = False
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                has_length = True
                try:
                    if int(value) > limit:
                        return await _send_json(send, 413, too_large)
                except ValueError:
                    return await _send_json(send, 400, "Nieprawidłowy Content-Length")
        if has_length:
            # Serwer ASGI (uvicorn/h11) nie przekaże więcej bajtów niż Content-Length.
            return await self.app(scope, receive, send)

        # Brak Content-Length (transfer chunked): buforujemy ciało do limitu,
        # a potem odtwarzamy je aplikacji. Wyjątek rzucony w trakcie czytania
        # ciała zostałby zamieniony przez FastAPI na 400, więc sprawdzamy wcześniej.
        messages = []
        received = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if received > limit:
                return await _send_json(send, 413, too_large)
            if not message.get("more_body", False):
                break

        async def replay():
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay, send)


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                for name, value in SECURITY_HEADERS:
                    if name not in present:
                        headers.append((name, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class OriginCheckMiddleware:
    def __init__(self, app, allowed_origins_getter: Callable[[], Iterable[str]]) -> None:
        self.app = app
        self._allowed = allowed_origins_getter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method", "GET").upper() not in UNSAFE_METHODS:
            return await self.app(scope, receive, send)
        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        origin_raw = headers.get(b"origin")
        if origin_raw is None:
            # Brak Origin: klient spoza przeglądarki (curl, testy) albo stara
            # przeglądarka. Ochronę zapewnia wtedy SameSite=Strict + auth.
            return await self.app(scope, receive, send)
        origin = origin_raw.decode("latin-1").strip().lower()
        host = headers.get(b"host", b"").decode("latin-1").strip().lower()
        scheme = scope.get("scheme", "http")
        same_origin = origin == f"{scheme}://{host}" if host else False
        allowed = {o.lower().rstrip("/") for o in self._allowed()}
        if same_origin or origin in allowed or "*" in allowed:
            return await self.app(scope, receive, send)
        return await _send_json(send, 403, "Niedozwolony Origin dla żądania zmieniającego dane")
