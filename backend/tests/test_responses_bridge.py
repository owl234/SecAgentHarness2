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

"""Unit tests for the Responses <-> Chat translation behind the Codex bridge."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from sec_agent_harness2.cli.responses_bridge import create_app
from sec_agent_harness2.responses_bridge import (
    StreamTranslator,
    TranslationError,
    from_chat,
    to_chat,
)


def _codex_request() -> dict:
    """A request shaped like the one Codex 0.144.6 actually sends."""
    return {
        "model": "m",
        "instructions": "You are a coding agent.",
        "input": [
            {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "be brief"}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "list files"}],
            },
        ],
        "tools": [
            {
                "type": "function",
                "name": "exec_command",
                "description": "run",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "type": "namespace",
                "name": "multi_agent_v1",
                "description": "agents",
                "tools": [
                    {
                        "type": "function",
                        "name": "spawn_agent",
                        "description": "spawn",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
            },
            {"type": "web_search", "external_web_access": True},
        ],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "stream": True,
    }


def test_instructions_become_a_system_message():
    chat = to_chat(_codex_request())
    assert chat["messages"][0] == {"role": "system", "content": "You are a coding agent."}


def test_developer_role_maps_to_system():
    chat = to_chat(_codex_request())
    assert chat["messages"][1] == {"role": "system", "content": "be brief"}


def test_namespace_tools_are_flattened():
    chat = to_chat(_codex_request())
    names = [t["function"]["name"] for t in chat["tools"]]
    assert names == ["exec_command", "spawn_agent"]


def test_builtin_tools_are_skipped_not_fatal():
    """web_search has no Chat equivalent; refusing the request would break every turn."""
    chat = to_chat(_codex_request())
    assert all(t["type"] == "function" for t in chat["tools"])


def test_function_call_output_becomes_a_tool_message():
    body = {
        "model": "m",
        "input": [
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "exec_command",
                "arguments": '{"cmd":"ls"}',
            },
            {"type": "function_call_output", "call_id": "c1", "output": "a.txt"},
        ],
    }
    chat = to_chat(body)
    assistant = [m for m in chat["messages"] if m.get("tool_calls")]
    assert assistant[0]["tool_calls"][0]["function"]["name"] == "exec_command"
    tool = [m for m in chat["messages"] if m["role"] == "tool"]
    assert tool[0]["tool_call_id"] == "c1"
    assert tool[0]["content"] == "a.txt"


def test_reasoning_items_are_dropped():
    body = {"model": "m", "input": [{"type": "reasoning", "summary": []}]}
    assert to_chat(body)["messages"] == []


def test_unknown_input_type_is_rejected():
    body = {"model": "m", "input": [{"type": "mystery"}]}
    with pytest.raises(TranslationError, match="unsupported input item type"):
        to_chat(body)


def test_max_output_tokens_maps_to_max_tokens():
    chat = to_chat({"model": "m", "input": "hi", "max_output_tokens": 42})
    assert chat["max_tokens"] == 42


def test_from_chat_builds_message_and_calls():
    reply = {
        "model": "m",
        "choices": [
            {
                "message": {
                    "content": "done",
                    "tool_calls": [
                        {"id": "c1", "function": {"name": "exec_command", "arguments": '{"cmd":"ls"}'}}
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }
    out = from_chat(reply, "m")
    assert out["object"] == "response"
    assert out["output"][0]["content"][0]["text"] == "done"
    assert out["output"][1]["type"] == "function_call"
    assert out["output"][1]["call_id"] == "c1"
    assert out["usage"]["input_tokens"] == 5


def test_from_chat_rejects_empty_choices():
    with pytest.raises(TranslationError, match="no choices"):
        from_chat({"choices": []}, "m")


def test_stream_translator_emits_only_a_terminal_event():
    """Codex parses every intermediate event into a strict enum; one bad frame
    aborts the turn, so the translator emits nothing until it has the full reply."""
    t = StreamTranslator("m")
    assert t.start() == b""
    events = []
    events += t.feed({"choices": [{"delta": {"content": "he"}}]})
    events += t.feed({"choices": [{"delta": {"content": "llo"}}]})
    assert events == []
    done = t.finish()
    assert len(done) == 1
    assert done[0].startswith(b"event: response.completed")
    payload = json.loads(done[0].split(b"data: ", 1)[1])
    assert payload["response"]["output"][0]["content"][0]["text"] == "hello"


def test_stream_translator_accumulates_tool_arguments():
    t = StreamTranslator("m")
    t.feed(
        {
            "choices": [
                {"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "run", "arguments": '{"a"'}}]}}
            ]
        }
    )
    t.feed({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ":1}"}}]}}]})
    payload = json.loads(t.finish()[0].split(b"data: ", 1)[1])
    call = payload["response"]["output"][0]
    assert call["name"] == "run"
    assert call["arguments"] == '{"a":1}'
    assert call["call_id"] == "c1"


def test_stream_translator_keeps_one_response_id():
    t = StreamTranslator("m")
    payload = json.loads(t.finish()[0].split(b"data: ", 1)[1])
    assert payload["response"]["id"] == t.response_id


def test_create_app_healthz():
    app = create_app("https://upstream.example.com/v1", "key")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "upstream": "https://upstream.example.com/v1/chat/completions"}


def test_create_app_models():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer mock-key"
        return httpx.Response(200, json={"data": [{"id": "model-1"}]})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app("https://upstream.example.com/v1", "mock-key", client=async_client)
    client = TestClient(app)
    r = client.get("/v1/models")
    assert r.status_code == 200
    assert r.json()["data"][0]["id"] == "model-1"


def test_create_app_responses_non_streaming():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer mock-key"
        body = json.loads(request.content)
        assert body["model"] == "my-model"
        return httpx.Response(
            200,
            json={
                "model": "my-model",
                "choices": [{"message": {"role": "assistant", "content": "hello world"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app("https://upstream.example.com/v1", "mock-key", client=async_client)
    client = TestClient(app)

    req = {"model": "my-model", "input": "hi"}
    r = client.post("/v1/responses", json=req)
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "response"
    assert data["output"][0]["content"][0]["text"] == "hello world"


def test_create_app_responses_streaming():
    def handler(request: httpx.Request) -> httpx.Response:
        stream_content = (
            b'data: {"choices":[{"delta":{"content":"chunk1"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"chunk2"}}]}\n\n'
            b"data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            content=stream_content,
            headers={"content-type": "text/event-stream"},
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app("https://upstream.example.com/v1", "mock-key", client=async_client)
    client = TestClient(app)

    req = {"model": "my-model", "input": "hi", "stream": True}
    r = client.post("/v1/responses", json=req)
    assert r.status_code == 200
    assert "event: response.completed" in r.text
    assert "chunk1chunk2" in r.text


def test_create_app_responses_error_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app("https://upstream.example.com/v1", "mock-key", client=async_client)
    client = TestClient(app)

    # 1. upstream 500 error
    r = client.post("/v1/responses", json={"model": "my-model", "input": "hi"})
    assert r.status_code == 500
    assert "upstream 500" in r.json()["error"]

    # 2. unsupported input type
    r = client.post("/v1/responses", json={"model": "my-model", "input": [{"type": "invalid"}]})
    assert r.status_code == 400
    assert "unsupported request" in r.json()["error"]


def test_main_cli_dispatch_responses_bridge():
    from sec_agent_harness2.cli import main as cli_main

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["responses-bridge", "--help"])
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["responses_bridge", "--help"])
    assert exc.value.code == 0


def test_inbound_bearer_auth_and_healthz():
    """Verify that inbound Bearer Token is enforced on endpoints while /healthz remains public."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"role": "assistant", "content": "authenticated response"}}],
            },
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = create_app(
        "https://upstream.example.com/v1",
        "upstream-key",
        local_key="test-bridge-token-12345",
        client=async_client,
    )
    client = TestClient(app)

    # 1. /healthz is open without authentication
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # 2. /v1/responses without auth token -> 401
    r = client.post("/v1/responses", json={"model": "m", "input": "hi"})
    assert r.status_code == 401
    assert "Unauthorized" in r.json()["error"]

    # 3. /v1/responses with wrong Bearer token -> 401
    r = client.post(
        "/v1/responses",
        json={"model": "m", "input": "hi"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401
    assert "Unauthorized" in r.json()["error"]

    # 4. /v1/responses with correct Bearer token -> 200
    r = client.post(
        "/v1/responses",
        json={"model": "m", "input": "hi"},
        headers={"Authorization": "Bearer test-bridge-token-12345"},
    )
    assert r.status_code == 200
    assert r.json()["output"][0]["content"][0]["text"] == "authenticated response"

    # 5. /v1/models without auth token -> 401
    r = client.get("/v1/models")
    assert r.status_code == 401


def test_ensure_bridge_running_concurrency_and_daemon(monkeypatch, tmp_path):
    """Verify ensure_bridge_running starts exactly one daemon process and reuses it under concurrent load."""
    import concurrent.futures
    from unittest.mock import MagicMock
    from sec_agent_harness2.cli import responses_bridge

    fake_dep = tmp_path / "dependencies" / "codex"
    fake_dep.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(responses_bridge.config, "DEPENDENCIES", tmp_path / "dependencies")

    calls = {"popen": 0, "healthy": 0}

    def fake_healthy(host, port, timeout=1.0):
        calls["healthy"] += 1
        # False on first check, True once popen has been called
        return calls["popen"] > 0

    monkeypatch.setattr(responses_bridge, "is_bridge_healthy", fake_healthy)

    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.poll.return_value = None

    def fake_popen(*args, **kwargs):
        calls["popen"] += 1
        return mock_proc

    import subprocess

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # Concurrently invoke ensure_bridge_running from 4 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [
            ex.submit(
                responses_bridge.ensure_bridge_running,
                upstream="https://upstream.example.com/v1",
                api_key="mock-key",
                port=8765,
            )
            for _ in range(4)
        ]
        results = [f.result() for f in futures]

    # Verify: Popen called exactly once despite 4 concurrent callers
    assert calls["popen"] == 1
    # Verify: All 4 callers received matching port and local key
    assert len(results) == 4
    for res in results:
        assert res["port"] == 8765
        assert res["key"] == results[0]["key"]
