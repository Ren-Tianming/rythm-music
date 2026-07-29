from datetime import timedelta
from unittest.mock import patch

from app.api.routes import auth as auth_routes
from app.api.routes import songs
from app.core.database import SessionLocal
from app.core.security import token_digest, utc_now
from app.models import AuthSession, User
from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> dict:
    with patch.object(auth_routes, "send_verification_email") as send_email:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": "制作者",
                "password": "secure-pass-123",
                "password_confirmation": "secure-pass-123",
            },
        )
    assert response.status_code == 202
    verification_token = send_email.call_args.args[1]
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert verified.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secure-pass-123"},
    )
    assert login.status_code == 200
    assert client.cookies.get("rythm_session")
    assert client.cookies.get("rythm_csrf")
    assert not client.cookies.get("rythm_refresh")
    return login.json()["user"]


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("rythm_csrf")
    assert token
    return {"X-CSRF-Token": token}


def fake_analysis(_: object) -> dict:
    return {
        "file_format": "wav",
        "duration_sec": 3.0,
        "sample_rate": 44100,
        "channels": 2,
        "bpm": 128.0,
        "musical_key": "F# マイナー",
        "rms": 0.124,
        "lufs": -12.4,
        "waveform": [0.1, -0.1],
        "spectrogram": [[-20.0, -10.0]],
        "genre": "electronic",
        "genre_confidence": 0.94,
        "genre_model_status": "READY",
        "genre_model_version": "test-onnx",
        "lyrics": "test lyric",
        "lyrics_status": "READY",
        "ai_summary": "test summary",
        "ai_summary_source": "LOCAL",
    }


def test_email_verification_opaque_session_devices_and_logout(client: TestClient) -> None:
    client.cookies.clear()
    with patch.object(auth_routes, "send_verification_email") as send_email:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "cookie@example.com",
                "username": "制作者",
                "password": "secure-pass-123",
                "password_confirmation": "secure-pass-123",
            },
        )
    assert registered.status_code == 202
    assert not client.cookies.get("rythm_session")
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "cookie@example.com", "password": "secure-pass-123"},
    ).json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    verification_token = send_email.call_args.args[1]
    assert client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    ).status_code == 200
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "cookie@example.com", "password": "secure-pass-123"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["email"] == "cookie@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200
    with SessionLocal() as db:
        stored_user = db.query(User).filter(User.email == "cookie@example.com").one()
        stored_session = db.query(AuthSession).filter(AuthSession.user_id == stored_user.id).one()
        assert stored_user.hashed_password.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
        assert stored_session.token_hash == token_digest(client.cookies.get("rythm_session"))
        assert stored_session.csrf_hash == token_digest(client.cookies.get("rythm_csrf"))
        assert client.cookies.get("rythm_session") not in stored_session.token_hash

    sessions = client.get("/api/v1/auth/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 1
    assert sessions.json()[0]["current"] is True

    # A second login creates a separately revocable device session.
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "cookie@example.com", "password": "secure-pass-123"},
    ).status_code == 200
    devices = client.get("/api/v1/auth/sessions").json()
    assert len(devices) == 2
    previous_device = next(device for device in devices if not device["current"])
    revoked = client.delete(
        f"/api/v1/auth/sessions/{previous_device['id']}",
        headers=csrf_headers(client),
    )
    assert revoked.status_code == 200
    assert len(client.get("/api/v1/auth/sessions").json()) == 1

    rejected = client.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"

    logged_out = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert logged_out.status_code == 200
    assert not client.cookies.get("rythm_session")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_operational_endpoints_expose_readiness_request_id_and_metrics(client: TestClient) -> None:
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"
    health = client.get("/health", headers={"X-Request-ID": "test-trace-id"})
    assert health.headers["X-Request-ID"] == "test-trace-id"
    metrics = client.get("/metrics")
    assert "aas_http_requests_total" in metrics.text


def test_session_idle_and_absolute_expiry_are_enforced_server_side(client: TestClient) -> None:
    register(client, "expiry@example.com")
    session_hash = token_digest(client.cookies.get("rythm_session"))
    with SessionLocal() as db:
        stored = db.query(AuthSession).filter(AuthSession.token_hash == session_hash).one()
        stored.last_seen_at = utc_now() - timedelta(hours=25)
        db.commit()
    assert client.get("/api/v1/auth/me").json()["error"]["code"] == "SESSION_EXPIRED"

    assert client.post(
        "/api/v1/auth/login",
        json={"email": "expiry@example.com", "password": "secure-pass-123"},
    ).status_code == 200
    session_hash = token_digest(client.cookies.get("rythm_session"))
    with SessionLocal() as db:
        stored = db.query(AuthSession).filter(AuthSession.token_hash == session_hash).one()
        stored.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").json()["error"]["code"] == "SESSION_EXPIRED"


def test_analysis_is_free_csrf_protected_and_user_isolated(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(songs, "analyze_audio", fake_analysis)
    register(client, "owner@example.com")

    missing_csrf = client.post(
        "/api/v1/songs/analyze",
        files={"file": ("pulse.wav", b"test-signal", "audio/wav")},
    )
    assert missing_csrf.status_code == 403

    response = client.post(
        "/api/v1/songs/analyze",
        files={"file": ("pulse.wav", b"test-signal", "audio/wav")},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    assert response.json()["points_cost"] == 0
    analysis_id = response.json()["id"]
    assert response.json()["genre_model_status"] == "READY"

    register(client, "other@example.com")
    assert client.get(f"/api/v1/songs/history/{analysis_id}").status_code == 404


def test_demo_generation_publish_and_public_feed(client: TestClient) -> None:
    register(client, "music-maker@example.com")
    generated = client.post(
        "/api/v1/music/generations",
        json={
            "title": "Neon Run",
            "prompt": "Tokyo highway at night with synthwave drums",
            "instrumental": True,
            "duration_sec": 5,
        },
        headers=csrf_headers(client),
    )
    assert generated.status_code == 201
    track = generated.json()
    assert track["provider"] == "demo"
    assert track["status"] == "SUCCESS"
    assert track["audio_url"].startswith("/media/generated/demo-")
    assert track["points_cost"] == 0

    published = client.post(
        "/api/v1/music/works",
        json={
            "generation_id": track["id"],
            "description": "MVP demo track",
            "cover_gradient": "violet",
        },
        headers=csrf_headers(client),
    )
    assert published.status_code == 201
    work = published.json()
    assert work["title"] == "Neon Run"
    assert work["creator_name"] == "制作者"

    feed = client.get("/api/v1/music/works")
    assert any(item["id"] == work["id"] for item in feed.json())
    liked = client.post(f"/api/v1/music/works/{work['id']}/like", headers=csrf_headers(client))
    assert liked.json()["likes_count"] == 1
    liked_again = client.post(f"/api/v1/music/works/{work['id']}/like", headers=csrf_headers(client))
    assert liked_again.json()["likes_count"] == 1


def test_payment_routes_are_not_part_of_v01(client: TestClient) -> None:
    register(client, "no-payment@example.com")
    assert client.get("/api/v1/pricing/packages").status_code == 404
    assert client.post("/api/v1/orders", json={"package_id": 1}, headers=csrf_headers(client)).status_code == 404
    assert client.get("/api/v1/admin/orders").status_code == 404


def test_founder_profile_is_public(client: TestClient) -> None:
    response = client.get("/api/v1/music/founder")
    assert response.status_code == 200
    assert response.json()["artist_name"] == "RyThM"
