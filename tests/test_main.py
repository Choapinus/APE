import pytest
from fastapi.testclient import TestClient
import base64
import os
import uuid
from main import app
from ape.session import SessionManager, get_session_manager

# A small 1x1 PNG base64 image (black pixel)
SAMPLE_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAn8B9pQn2wAAAABJRU5ErkJggg=="
)

@pytest.fixture(scope="function")
def client():
    TEST_DB_PATH = "test_sessions.db"
    
    def override_get_session_manager():
        return SessionManager(db_path=TEST_DB_PATH)

    app.dependency_overrides[get_session_manager] = override_get_session_manager

    with TestClient(app) as c:
        yield c

    # Teardown
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Clear the override
    app.dependency_overrides.clear()

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_prompt_text(client):
    resp = client.post("/prompt", json={"text": "Hello, world!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_image(client):
    resp = client.post("/prompt", json={"image_base64": SAMPLE_IMAGE_BASE64})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_text_and_image(client):
    resp = client.post("/prompt", json={"text": "What is in this image?", "image_base64": SAMPLE_IMAGE_BASE64})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_no_input(client):
    resp = client.post("/prompt", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Please provide text and/or image input."
    assert "session_id" in data

def test_prompt_stream(client):
    """Tests the streaming endpoint."""
    with client.stream("POST", "/prompt/stream", json={"text": "Hello, stream!"}) as response:
        assert response.status_code == 200
        response_text = ""
        for chunk in response.iter_text():
            response_text += chunk
        assert len(response_text) > 0

def test_session_history(client):
    """Tests if conversation history is correctly created and retrieved."""
    session_id = f"test-session-{uuid.uuid4()}"

    # 1. First turn
    resp1 = client.post("/prompt", json={"text": "My name is Claude", "session_id": session_id})
    assert resp1.status_code == 200

    # 2. Second turn
    resp2 = client.post("/prompt", json={"text": "What did I say my name was?", "session_id": session_id})
    assert resp2.status_code == 200
    
    # 3. Check the session history from the API
    resp_session = client.get("/session")
    assert resp_session.status_code == 200
    sessions = resp_session.json()
    
    assert session_id in sessions
    history = sessions[session_id]
    
    assert len(history) == 4  # user, assistant, user, assistant
    
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "My name is Claude"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    assert history[2]["content"] == "What did I say my name was?"
    assert history[3]["role"] == "assistant" 