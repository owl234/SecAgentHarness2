# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""HTTP front end for harness2.responses_bridge: `/v1/responses` on a Chat endpoint.

Run it in front of any OpenAI-compatible endpoint that has no `/v1/responses`:

    harness2-responses-bridge --upstream https://host/v1 --api-key sk-...

The bridge prints the SEC_AGENT_HARNESS2_CODEX_* settings to put in `.env`, exactly like
`harness2-bridge`, but it does not need Vertex or LiteLLM.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from sec_agent_harness2 import config
from sec_agent_harness2 import i18n as I18N
from sec_agent_harness2.responses_bridge import (
    StreamTranslator,
    TranslationError,
    from_chat,
    to_chat,
)


DEFAULT_BRIDGE_HOST = "0.0.0.0"
DEFAULT_BRIDGE_PORT = 8765


def _free_port(host: str) -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1" if host in ("0.0.0.0", "127.0.0.1", "localhost") else host, 0))
        return s.getsockname()[1]


def is_bridge_healthy(host: str, port: int, timeout: float = 1.0) -> bool:
    """Test whether our responses bridge is alive on host:port."""
    import urllib.request

    probe_host = "127.0.0.1" if host in ("0.0.0.0", "127.0.0.1", "localhost") else host
    url = f"http://{probe_host}:{port}/healthz"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return data.get("status") == "ok"
    except Exception:
        pass
    return False


def _is_port_usable(host: str, port: int) -> bool:
    """Check if the port is either running our bridge or completely free to bind."""
    if is_bridge_healthy(host, port):
        return True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_host = "127.0.0.1" if host in ("0.0.0.0", "127.0.0.1", "localhost") else host
            s.bind((bind_host, port))
            return True
    except OSError:
        return False


def _endpoint(path: Path, host: str = DEFAULT_BRIDGE_HOST, port: int = 0) -> dict:
    """Reuse the saved port and key so the Codex config written by setup stays valid."""
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}

    chosen_port = port or saved.get("port") or DEFAULT_BRIDGE_PORT
    if port == 0 and not saved.get("port"):
        if not _is_port_usable(host, chosen_port):
            chosen_port = _free_port(host)

    endpoint = {
        "host": host,
        "port": chosen_port,
        "key": saved.get("key") or secrets.token_urlsafe(24),
        "wire_mode": saved.get("wire_mode", "bridge"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(endpoint, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return endpoint


def create_app(
    upstream: str,
    api_key: str,
    *,
    local_key: str | None = None,
    timeout: float = 600.0,
    client: httpx.AsyncClient | None = None,
) -> FastAPI:
    """The bridge app; `upstream` is the Chat Completions base (…/v1)."""
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    url = upstream.rstrip("/") + "/chat/completions"

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await client.aclose()

    app = FastAPI(title="harness2 responses bridge", lifespan=lifespan)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path == "/healthz":
            return await call_next(request)
        if local_key:
            auth = (request.headers.get("authorization") or "").strip()
            parts = auth.split()
            if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != local_key:
                return JSONResponse(
                    {"error": "Unauthorized: invalid or missing bridge bearer token"},
                    status_code=401,
                )
        return await call_next(request)

    @app.get("/healthz")
    async def healthz(request: Request) -> dict:
        data = {"status": "ok", "upstream": url}
        if request.query_params.get("detailed"):
            data.update({
                "mode": "responses_bridge",
                "version": "1.0",
                "auth_enabled": bool(local_key),
            })
        return data

    @app.get("/v1/models")
    async def models() -> JSONResponse:
        try:
            r = await client.get(
                upstream.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return JSONResponse(r.json(), status_code=r.status_code)
        except httpx.HTTPError as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)

    @app.post("/v1/responses")
    async def responses(request: Request):
        try:
            body = await request.json()
        except ValueError:
            return JSONResponse({"error": "request body is not JSON"}, status_code=400)
        try:
            chat = to_chat(body)
        except TranslationError as exc:
            return JSONResponse({"error": f"unsupported request: {exc}"}, status_code=400)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if not chat.get("stream"):
            try:
                r = await client.post(url, json=chat, headers=headers)
            except httpx.HTTPError as exc:
                return JSONResponse({"error": f"upstream unreachable: {exc}"}, status_code=502)
            if r.status_code >= 400:
                return JSONResponse(
                    {"error": f"upstream {r.status_code}: {r.text[:500]}"},
                    status_code=r.status_code,
                )
            try:
                return JSONResponse(from_chat(r.json(), chat["model"]))
            except TranslationError as exc:
                return JSONResponse({"error": f"unusable reply: {exc}"}, status_code=502)

        async def stream():
            translator = StreamTranslator(chat["model"])
            yield translator.start()
            try:
                async with client.stream("POST", url, json=chat, headers=headers) as r:
                    if r.status_code >= 400:
                        text = (await r.aread()).decode("utf-8", "replace")[:500]
                        yield b"event: error\ndata: " + json.dumps(
                            {"type": "error", "error": {"message": f"upstream {r.status_code}: {text}"}}
                        ).encode() + b"\n\n"
                        return
                    async for line in r.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        for event in translator.feed(chunk):
                            yield event
                for event in translator.finish():
                    yield event
            except httpx.HTTPError as exc:
                yield b"event: error\ndata: " + json.dumps(
                    {"type": "error", "error": {"message": f"upstream error: {exc}"}}
                ).encode() + b"\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


def ensure_bridge_running(
    upstream: str | None = None,
    api_key: str | None = None,
    *,
    host: str = DEFAULT_BRIDGE_HOST,
    port: int = 0,
    timeout: float = 10.0,
) -> dict:
    """Ensure the responses bridge daemon is running, using fcntl file locking for concurrency."""
    import fcntl
    import subprocess
    import sys
    import time

    root = config.DEPENDENCIES / "codex"
    json_path = root / "responses-bridge.json"
    lock_path = root / ".bridge.lock"
    log_path = root / "responses-bridge.log"

    resolved_upstream = (
        upstream or os.environ.get("SEC_AGENT_HARNESS2_API_BASE_URL") or config.API_BASE_URL
    ).strip()
    resolved_key = (
        api_key or os.environ.get("SEC_AGENT_HARNESS2_API_KEY") or config.API_KEY
    ).strip()

    if not resolved_upstream or not resolved_key:
        raise config.ConfigError(
            "Upstream API URL (SEC_AGENT_HARNESS2_API_BASE_URL) and Key (SEC_AGENT_HARNESS2_API_KEY) "
            "are required to run Responses bridge"
        )

    # 1. Fast path: check if bridge is already healthy
    if json_path.is_file():
        try:
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            if not (saved.get("upstream") and saved.get("upstream") != resolved_upstream):
                saved_port = saved.get("port") or DEFAULT_BRIDGE_PORT
                if is_bridge_healthy(host, saved_port):
                    return saved
        except Exception:
            pass

    # 2. Acquire exclusive file lock
    root.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            endpoint = _endpoint(json_path, host, port)
            endpoint["upstream"] = resolved_upstream
            target_port = endpoint["port"]

            # Re-check under lock
            if is_bridge_healthy(host, target_port):
                return endpoint

            if not _is_port_usable(host, target_port):
                target_port = _free_port(host)
                endpoint["port"] = target_port
                json_path.write_text(json.dumps(endpoint, indent=2) + "\n", encoding="utf-8")

            cmd = [
                sys.executable,
                "-m",
                "sec_agent_harness2.cli.responses_bridge",
                "--upstream",
                resolved_upstream,
                "--api-key",
                resolved_key,
                "--host",
                host,
                "--port",
                str(target_port),
            ]
            sub_env = dict(os.environ)
            backend_dir = str(Path(__file__).resolve().parents[2])
            sub_env["PYTHONPATH"] = backend_dir + (
                os.pathsep + sub_env["PYTHONPATH"] if sub_env.get("PYTHONPATH") else ""
            )
            with open(log_path, "a", encoding="utf-8") as log_out:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_out,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                    env=sub_env,
                )

            t0 = time.time()
            while time.time() - t0 < timeout:
                if is_bridge_healthy(host, target_port, timeout=0.5):
                    endpoint["pid"] = proc.pid
                    json_path.write_text(json.dumps(endpoint, indent=2) + "\n", encoding="utf-8")
                    return endpoint
                if proc.poll() is not None:
                    break
                time.sleep(0.15)

            raise RuntimeError(
                f"Responses bridge failed to start on port {target_port} within {timeout}s (see {log_path})"
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main(argv=None):
    lang = I18N.get_lang()
    p = argparse.ArgumentParser(description=I18N.t("responses_bridge.desc", lang))
    p.add_argument("--lang", default=None, choices=("en", "zh"), help=I18N.t("cell.lang", lang))
    p.add_argument("--upstream", default=config.API_BASE_URL, help=I18N.t("responses_bridge.upstream", lang))
    p.add_argument("--api-key", default=config.API_KEY, help=I18N.t("responses_bridge.api_key", lang))
    p.add_argument("--host", default=DEFAULT_BRIDGE_HOST, help=I18N.t("responses_bridge.host", lang))
    p.add_argument("--port", type=int, default=0, help=I18N.t("responses_bridge.port", lang))
    p.add_argument("--timeout", type=float, default=600.0, help=I18N.t("responses_bridge.timeout", lang))
    args = p.parse_args(argv)
    lang = I18N.resolve_lang(args)

    if not args.upstream:
        p.exit(1, I18N.t("responses_bridge.no_upstream", lang) + "\n")
    if not args.api_key:
        p.exit(1, I18N.t("responses_bridge.no_key", lang) + "\n")

    root = config.DEPENDENCIES / "codex"
    endpoint = _endpoint(root / "responses-bridge.json", args.host, args.port)
    port = endpoint["port"]
    bind_host = "127.0.0.1" if args.host in ("0.0.0.0", "127.0.0.1", "localhost") else args.host
    base = f"http://{bind_host}:{port}/v1"
    settings = {
        "SEC_AGENT_HARNESS2_CODEX_BASE_URL": base,
        "SEC_AGENT_HARNESS2_CODEX_API_KEY": endpoint["key"],
        "SEC_AGENT_HARNESS2_CODEX_MODEL": config.SOLVER_MODEL_CX,
    }
    if args.host != "127.0.0.1":
        settings["SEC_AGENT_HARNESS2_CODEX_CONTAINER_URL"] = f"http://host.docker.internal:{port}/v1"
    print(I18N.t("responses_bridge.hint", lang), flush=True)
    print("\n".join(f"{k}={v}" for k, v in settings.items()), flush=True)

    import uvicorn

    app = create_app(args.upstream, args.api_key, local_key=endpoint["key"], timeout=args.timeout)
    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    raise SystemExit(main())
