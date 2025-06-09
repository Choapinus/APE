import pytest
from fastapi.testclient import TestClient
from main import app
import base64

# A small 1x1 PNG base64 image (black pixel)
SAMPLE_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAn8B9pQn2wAAAABJRU5ErkJggg=="
)

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_prompt_text():
    resp = client.post("/prompt", json={"text": "Hello, world!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_image():
    resp = client.post("/prompt", json={"image_base64": SAMPLE_IMAGE_BASE64})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_text_and_image():
    resp = client.post("/prompt", json={"text": "What is in this image?", "image_base64": SAMPLE_IMAGE_BASE64})
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert data["text"]
    assert "session_id" in data

def test_prompt_no_input():
    resp = client.post("/prompt", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Please provide text and/or image input."
    assert "session_id" in data 