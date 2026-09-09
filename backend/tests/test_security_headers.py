from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_security_headers_are_present():
    response = client.get("/")

    assert response.status_code == 200

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"

    assert (
        response.headers["Permissions-Policy"]
        == "camera=(), microphone=(), geolocation=()"
    )

    assert (
        response.headers["Cache-Control"]
        == "no-store, no-cache, must-revalidate, private"
    )

    assert response.headers["Pragma"] == "no-cache"

    assert (
        response.headers["Content-Security-Policy"]
        == (
            "default-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'none';"
        )
    )


def test_hsts_is_not_enabled_outside_production():
    response = client.get("/")

    assert response.status_code == 200

    assert "Strict-Transport-Security" not in response.headers