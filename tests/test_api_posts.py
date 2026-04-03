"""
Тесты для /api/posts/republish.
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.routers.posts import router
from fastapi import FastAPI

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)


def _future(delta_seconds=2):
    return (datetime.now() + timedelta(seconds=delta_seconds)).strftime("%Y-%m-%dT%H:%M:%S")


def _past(delta_seconds=2):
    return (datetime.now() - timedelta(seconds=delta_seconds)).strftime("%Y-%m-%dT%H:%M:%S")


# Фиктивные ORM-объекты, которые вернёт db.get()
def _mock_channel():
    ch = MagicMock()
    ch.post_id = 1
    ch.source_type = "telegram"
    ch.source_id = 10
    ch.title = None
    ch.description = None
    return ch


def _mock_post():
    p = MagicMock()
    p.id = 1
    return p


def _make_db_context(channel, post):
    """Возвращает контекст-менеджер, имитирующий SessionLocal()."""
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.get = MagicMock(side_effect=lambda model, pk: channel if "Channel" in model.__name__ else post)
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


# ---------------------------------------------------------------------------

def test_future_date_accepted():
    """Дата 'сейчас + 2 с' не отклоняется как прошедшая."""
    db = _make_db_context(_mock_channel(), _mock_post())
    with patch("app.routers.posts.SessionLocal", return_value=db):
        resp = client.post("/api/posts/republish", json={
            "post_id": 1,
            "channel_id": 5,
            "dates": [_future()],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True, data


def test_past_date_rejected():
    """Дата 'сейчас - 2 с' отклоняется с сообщением об ошибке."""
    resp = client.post("/api/posts/republish", json={
        "post_id": 1,
        "channel_id": 5,
        "dates": [_past()],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "уже прошла" in data["error"]


def test_empty_dates_rejected():
    """Пустой список дат отклоняется."""
    resp = client.post("/api/posts/republish", json={
        "post_id": 1,
        "channel_id": 5,
        "dates": [],
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_invalid_date_format_rejected():
    """Неверный формат даты отклоняется."""
    resp = client.post("/api/posts/republish", json={
        "post_id": 1,
        "channel_id": 5,
        "dates": ["not-a-date"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "формат" in data["error"].lower()
