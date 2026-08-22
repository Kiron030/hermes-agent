"""Mock HTTP helpers for Golden bounded-operation contracts. No live network."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse


class RecordingPoster:
    """Capture POSTs and return a canned JSON body. Never opens a socket."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.calls: list[dict[str, Any]] = []

    @property
    def count(self) -> int:
        return len(self.calls)

    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_s: float | None = None,
    ) -> "_FakeResp":
        parsed = urlparse(url)
        self.calls.append(
            {
                "url": url,
                "scheme": parsed.scheme,
                "hostname": parsed.hostname,
                "path": parsed.path,
                "headers": dict(headers),
                "json_body": dict(json_body),
                "timeout_s": timeout_s,
            }
        )
        return _FakeResp(self.status_code, self.payload)


class _FakeResp:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._data = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict[str, Any]:
        return dict(self._data)


def correlation_from_headers(headers: dict[str, str]) -> str | None:
    for key, value in headers.items():
        if key.lower() == "x-correlation-id":
            return value
    return None
