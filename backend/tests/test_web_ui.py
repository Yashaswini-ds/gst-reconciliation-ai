import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_serve_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GST Reconciliation" in response.text
    assert "id=\"gstDropzone\"" in response.text


def test_serve_static_styles_css():
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert "--bg-dark" in response.text


def test_serve_static_app_js():
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"] or "text/javascript" in response.headers["content-type"]
    assert "executeReconciliation" in response.text


def test_favicon_endpoint():
    response = client.get("/favicon.ico")
    assert response.status_code == 204

