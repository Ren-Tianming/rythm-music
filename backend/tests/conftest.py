import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="rythm-music-tests-"))
DB_PATH = TEST_ROOT / "api.db"
os.environ["AUDIO_DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["AUDIO_AUTO_CREATE_TABLES"] = "true"
os.environ["AUDIO_ENVIRONMENT"] = "test"
os.environ["APP_SECRET"] = "test-only-app-secret-at-least-32-characters"
os.environ["AUDIO_REDIS_URL"] = ""
os.environ["AUDIO_AUTH_RATE_LIMIT_REQUESTS"] = "1000"
os.environ["AUDIO_RATE_LIMIT_REQUESTS"] = "1000"
os.environ["AUDIO_REGISTRATION_RATE_LIMIT_PER_HOUR"] = "100"
os.environ["AUDIO_VERIFICATION_RATE_LIMIT_PER_HOUR"] = "100"
os.environ["AUDIO_EMAIL_ACTION_RATE_LIMIT_PER_HOUR"] = "100"
os.environ["AUDIO_EMAIL_ACTION_IP_RATE_LIMIT_PER_HOUR"] = "500"
os.environ["AUDIO_UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["AUDIO_GENERATED_DIR"] = str(TEST_ROOT / "generated")

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
