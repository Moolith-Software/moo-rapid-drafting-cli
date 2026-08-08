"""
Preview manager — the 'Setup preview / build tools' box from the diagram.

Each workspace is a full CoW clone (node_modules and all), so previewing it is
just `npm run dev` on its own port. This module starts one Vite dev server per
target ("base" or "feature-<id>"), tracks it, and returns its URL. Because the
dev server watches the folder, a later refinement hot-reloads in the open tab.

Ports are deterministic: base -> 5200, feature-<id> -> 5200 + id. Enough for a
prototype; no fancy allocation.
"""

import os
import socket
import subprocess
import time
from pathlib import Path

BASE_PORT = 5200

# key ("base" | "feature-3") -> {"proc": Popen, "port": int, "url": str}
_servers: dict[str, dict] = {}


def _port_for(key: str) -> int:
    if key == "base":
        return BASE_PORT
    # "feature-7" -> 5207
    return BASE_PORT + int(key.split("-")[1])


def _alive(entry: dict) -> bool:
    return entry["proc"].poll() is None


def _wait_ready(port: int, timeout: float = 40.0) -> bool:
    """
    Poll the port until the dev server accepts connections (or we give up).
    We connect to "localhost" (not "127.0.0.1") because Vite binds to IPv6 [::1]
    by default — an IPv4-only probe would never see it.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def start_preview(key: str, cwd: Path) -> dict:
    """Start (or reuse) a Vite dev server for `key` rooted at `cwd`. Returns {url, port}."""
    existing = _servers.get(key)
    if existing and _alive(existing):
        return {"url": existing["url"], "port": existing["port"]}

    port = _port_for(key)
    url = f"http://localhost:{port}"
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(cwd),
        env={**os.environ, "PORT": str(port)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _servers[key] = {"proc": proc, "port": port, "url": url}

    if not _wait_ready(port):
        stop_preview(key)
        raise RuntimeError(f"preview for {key} did not start on port {port}")
    return {"url": url, "port": port}


def stop_preview(key: str) -> None:
    entry = _servers.pop(key, None)
    if entry and _alive(entry):
        entry["proc"].terminate()


def stop_all() -> None:
    for key in list(_servers):
        stop_preview(key)
