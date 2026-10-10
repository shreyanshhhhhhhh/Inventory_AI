import os
import tempfile
from collections.abc import Generator
from pathlib import Path

_test_db_path = Path(tempfile.gettempdir()) / "inventory-auth-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path.as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["LLM_MODEL"] = "fake-model"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.main import app


def _reset_schema() -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)


@pytest.fixture(autouse=True)
def _reset_database() -> Generator[None, None, None]:
    _reset_schema()
    yield
    _reset_schema()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
