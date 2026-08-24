#!/usr/bin/env python3
"""Inbound-only TCP reverse proxy for official Hermes Desktop.

Listens on one port and forwards to a fixed Developer-Hermes backend.
It is not an HTTP CONNECT proxy and does not choose destinations.
"""

from __future__ import annotations

import os
import socket
import threading


LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(os.environ.get("R5_DESKTOP_LISTEN_PORT", "9119"))
BACKEND_HOST = os.environ.get("R5_DESKTOP_BACKEND_HOST", "r5-developer-hermes")
BACKEND_PORT = int(os.environ.get("R5_DESKTOP_BACKEND_PORT", "9119"))
BUFFER = 65536


def _pipe(source: socket.socket, dest: socket.socket) -> None:
    try:
        while True:
            data = source.recv(BUFFER)
            if not data:
                break
            dest.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dest.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _handle(client: socket.socket) -> None:
    upstream = None
    try:
        upstream = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=10)
        upstream.settimeout(None)
        client.settimeout(None)
        to_backend = threading.Thread(target=_pipe, args=(client, upstream), daemon=True)
        to_client = threading.Thread(target=_pipe, args=(upstream, client), daemon=True)
        to_backend.start()
        to_client.start()
        to_backend.join()
        to_client.join()
    except OSError:
        pass
    finally:
        if upstream is not None:
            try:
                upstream.close()
            except OSError:
                pass
        try:
            client.close()
        except OSError:
            pass


def main() -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((LISTEN_HOST, LISTEN_PORT))
    listener.listen(128)
    while True:
        client, _addr = listener.accept()
        threading.Thread(target=_handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    raise SystemExit(main())
