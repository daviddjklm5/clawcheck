from __future__ import annotations

from contextlib import contextmanager
from typing import Any
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from automation.api.main import create_app


@contextmanager
def _patched_chat_service(service: Any):
    with patch("automation.api.routers.chat.get_chat_service", return_value=service):
        yield


class _FakeChatService:
    def __init__(self) -> None:
        self._session = {
            "sessionId": "s1",
            "title": "Session",
            "workspaceDir": "c:/repo",
            "modelProvider": "openai_compatible",
            "modelName": "gpt-5-mini",
            "status": "idle",
            "createdAt": "2026-03-21 10:00:00",
            "lastActiveAt": "2026-03-21 10:00:00",
        }
        self._detail = {
            "session": self._session,
            "messages": [],
            "running": False,
            "lastEventSeq": 2,
        }
        self.stream_after_seq_calls: list[int] = []

    def create_session(self, *, title: str = "", workspace_dir: str = "") -> dict[str, Any]:
        return {**self._session, "title": title or self._session["title"]}

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        _ = limit
        _ = offset
        return [self._session]

    def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        return self._detail if session_id == "s1" else None

    def submit_user_message(self, *, session_id: str, content: str) -> dict[str, Any]:
        if session_id != "s1":
            raise ValueError("Session not found")
        if content == "conflict":
            raise RuntimeError("already running")
        return {
            "sessionId": "s1",
            "userMessage": {
                "messageId": "u1",
                "sessionId": "s1",
                "role": "user",
                "content": content,
                "tokenCount": 1,
                "createdAt": "2026-03-21 10:00:01",
            },
            "assistantMessage": {
                "messageId": "a1",
                "sessionId": "s1",
                "role": "assistant",
                "content": "",
                "tokenCount": 0,
                "createdAt": "2026-03-21 10:00:01",
            },
            "run": {"runId": "r1", "status": "queued"},
        }

    def cancel_session_run(self, session_id: str) -> dict[str, Any]:
        if session_id != "s1":
            raise RuntimeError("no active run")
        return {"sessionId": "s1", "runId": "r1", "status": "cancel_requested"}

    def stream_events(self, session_id: str, *, after_seq: int = 0):
        self.stream_after_seq_calls.append(after_seq)
        if session_id != "s1":
            return
        yield {"seq": 1, "type": "status", "at": "now", "data": {"status": "running"}}
        yield {"seq": 2, "type": "done", "at": "now", "data": {"status": "succeeded"}}

    def get_config_summary(self) -> dict[str, Any]:
        return {"provider": "openai_compatible", "model": "gpt-5-mini"}

    def get_health(self) -> dict[str, Any]:
        return {"status": "ok", "codexCliAvailable": True}


class ChatRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(webui_dist_dir=None))
        self.service = _FakeChatService()

    def test_create_and_list_sessions(self) -> None:
        with _patched_chat_service(self.service):
            create_response = self.client.post("/api/chat/sessions", json={"title": "New Chat"})
            list_response = self.client.get("/api/chat/sessions")

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["session"]["title"], "New Chat")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["sessions"]), 1)

    def test_get_session_detail_404(self) -> None:
        with _patched_chat_service(self.service):
            response = self.client.get("/api/chat/sessions/not-found")
        self.assertEqual(response.status_code, 404)

    def test_get_session_detail_includes_last_event_seq(self) -> None:
        with _patched_chat_service(self.service):
            response = self.client.get("/api/chat/sessions/s1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lastEventSeq"], 2)

    def test_submit_message_maps_exceptions(self) -> None:
        with _patched_chat_service(self.service):
            ok_response = self.client.post("/api/chat/sessions/s1/messages", json={"content": "hello"})
            conflict_response = self.client.post(
                "/api/chat/sessions/s1/messages",
                json={"content": "conflict"},
            )
            missing_response = self.client.post(
                "/api/chat/sessions/s2/messages",
                json={"content": "hello"},
            )

        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(missing_response.status_code, 404)

    def test_cancel_and_stream(self) -> None:
        with _patched_chat_service(self.service):
            cancel_response = self.client.post("/api/chat/sessions/s1/cancel")
            stream_response = self.client.get("/api/chat/sessions/s1/stream")

        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(stream_response.status_code, 200)
        self.assertIn("event: status", stream_response.text)
        self.assertIn("event: done", stream_response.text)
        self.assertEqual(self.service.stream_after_seq_calls[-1], 0)

    def test_stream_uses_last_event_id_header_for_resume_offset(self) -> None:
        with _patched_chat_service(self.service):
            stream_response = self.client.get(
                "/api/chat/sessions/s1/stream?afterSeq=0",
                headers={"Last-Event-ID": "7"},
            )

        self.assertEqual(stream_response.status_code, 200)
        self.assertEqual(self.service.stream_after_seq_calls[-1], 7)

    def test_config_and_health(self) -> None:
        with _patched_chat_service(self.service):
            config_response = self.client.get("/api/chat/config-summary")
            health_response = self.client.get("/api/chat/health")

        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(config_response.json()["provider"], "openai_compatible")
        self.assertEqual(health_response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
