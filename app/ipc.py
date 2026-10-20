from __future__ import annotations

import hmac
import json
import os
import socket
import threading
from pathlib import Path
from typing import Callable

MAX_REQUEST = 65536


class Server:
    def __init__(self, path: Path, handlers: dict[str, Callable[[dict], dict]]) -> None:
        self.path = Path(path)
        self.handlers = handlers
        self.port: int | None = None
        self._token = os.urandom(16).hex()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stopping = False

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(16)
        sock.settimeout(0.5)
        self._socket = sock
        self.port = int(sock.getsockname()[1])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(
            json.dumps(
                {"port": self.port, "token": self._token, "pid": os.getpid()},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.replace(temp, self.path)
        self._thread = threading.Thread(target=self._accept, name="zgui-ipc", daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        while not self._stopping:
            sock = self._socket
            if sock is None:
                break
            try:
                connection, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._serve, args=(connection,), name="zgui-ipc-client", daemon=True
            ).start()

    def _serve(self, connection: socket.socket) -> None:
        try:
            connection.settimeout(20)
            data = b""
            while b"\n" not in data and len(data) < MAX_REQUEST:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data.strip():
                return
            request = json.loads(data.decode("utf-8").splitlines()[0])
            response: dict = {"ok": False, "error": "token"}
            token = str(request.get("token") or "")
            if hmac.compare_digest(token, self._token):
                handler = self.handlers.get(str(request.get("command") or ""))
                if handler is None:
                    response = {"ok": False, "error": "unknown"}
                else:
                    try:
                        response = handler(request.get("args") or {}) or {"ok": True}
                    except Exception as exc:
                        response = {"ok": False, "error": str(exc)}
            connection.sendall(
                (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
            )
        except (OSError, ValueError):
            pass
        finally:
            try:
                connection.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stopping = True
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        try:
            self.path.unlink()
        except OSError:
            pass


def read_endpoint(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "port" not in data or "token" not in data:
        return None
    return data


def call(
    command: str,
    args: dict | None = None,
    timeout: float = 4.0,
    path: Path | None = None,
) -> dict | None:
    endpoint = read_endpoint(path) if path is not None else None
    if endpoint is None:
        from . import paths

        endpoint = read_endpoint(paths.ipc_path())
    if endpoint is None:
        return None
    try:
        with socket.create_connection(
            ("127.0.0.1", int(endpoint["port"])), timeout=timeout
        ) as connection:
            connection.settimeout(timeout)
            payload = json.dumps(
                {
                    "token": endpoint.get("token"),
                    "command": command,
                    "args": args or {},
                }
            )
            connection.sendall(payload.encode("utf-8") + b"\n")
            data = b""
            while b"\n" not in data and len(data) < MAX_REQUEST:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data += chunk
        if not data.strip():
            return None
        return json.loads(data.decode("utf-8").splitlines()[0])
    except (OSError, ValueError):
        return None


def ping(timeout: float = 1.5) -> dict | None:
    response = call("ping", timeout=timeout)
    if response and response.get("ok"):
        return response
    return None
