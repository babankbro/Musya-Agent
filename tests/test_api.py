"""Test FastAPI endpoints via TestClient."""
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


class TestRootEndpoint:

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Musya Agent API"
        assert "version" in data


class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "services" in data
        assert "postgres" in data["services"]

    def test_health_postgres_connected(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["services"]["postgres"] == "ok", "PostgreSQL should be connected"


class TestChatEndpoint:

    def test_chat_empty_message_returns_400(self, client):
        resp = client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 400

    def test_chat_missing_message_returns_422(self, client):
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422

    def test_chat_valid_request_returns_200(self, client):
        """Full end-to-end test — calls CrewAI + Gemini (slow, ~30-60s)."""
        resp = client.post(
            "/api/chat",
            json={"message": "สรุปข้อมูลอุบัติเหตุปี 2024"},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert len(data["content"]) > 50, "Response should have substantial content"
        assert data["topic"] == "accident"
        assert isinstance(data["follow_ups"], list)

    def test_chat_with_session_id(self, client):
        resp = client.post(
            "/api/chat",
            json={"message": "จุดเสี่ยงอุบัติเหตุ", "session_id": "test-session-001"},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data


class TestChatStreamEndpoint:

    def test_stream_empty_message_returns_400(self, client):
        resp = client.post("/api/chat/stream", json={"message": ""})
        assert resp.status_code == 400

    def test_stream_returns_sse(self, client):
        """Test SSE streaming endpoint."""
        resp = client.post(
            "/api/chat/stream",
            json={"message": "สรุปอุบัติเหตุ"},
            timeout=120,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "data:" in body
