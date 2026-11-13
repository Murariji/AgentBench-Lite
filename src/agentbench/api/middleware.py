"""Low-level protections that wrap the whole app (Phase 9.3).

BodySizeLimit: the request body may be at most MAX_BODY_BYTES (64 KB). Checked against the bytes that
ACTUALLY arrive - not only the Content-Length header, which a client may leave out (chunked uploads) or
get wrong. A too-large body is answered with 413 in the usual error shape, and the app never sees it.
"""

import json

MAX_BODY_BYTES = 64 * 1024


async def _send_json(send, status: int, body: dict, extra_headers: list | None = None) -> None:
    payload = json.dumps(body).encode("utf-8")
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra_headers or [])})
    await send({"type": "http.response.body", "body": payload})


def too_large_body(limit: int) -> dict:
    return {"error": {"code": "payload_too_large",
                      "message": f"the request body is larger than the limit of {limit} bytes",
                      "details": {"limit_bytes": limit}}}


class BodySizeLimit:
    """ASGI middleware: read the body (up to `limit` bytes), then hand it to the app unchanged."""

    def __init__(self, app, limit: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            return await _send_json(send, 413, too_large_body(self.limit))     # refused before reading

        body = bytearray()
        while True:                                     # count what REALLY arrives (also chunked bodies)
            message = await receive()
            if message["type"] == "http.disconnect":
                return                                  # the client went away: nothing to answer
            body += message.get("body", b"")
            if len(body) > self.limit:
                return await _send_json(send, 413, too_large_body(self.limit))
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:                           # the app gets the whole body in one piece
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()                      # afterwards: real events (e.g. disconnect)

        await self.app(scope, replay, send)
