import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:////tmp/inventory-auth-test.db"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def _reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
