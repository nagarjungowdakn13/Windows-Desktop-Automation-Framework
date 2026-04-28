"""Service-layer tests using an isolated SQLite database per test."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import database as db_module
from app.db.models import TaskStatus
from app.schemas.task import StepConfig, TaskRequest
from app.services.task_service import TaskService


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the engine at a fresh SQLite file under tmp_path and rebuild tables."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)

    db_module.init_db()
    yield


def _request(name: str = "demo") -> TaskRequest:
    return TaskRequest(
        name=name,
        steps=[StepConfig(type="wait", params={"seconds": 0.0})],
    )


def test_create_and_get_status(isolated_db: None) -> None:
    svc = TaskService()
    task_id = svc.create(_request("alpha"))
    status = svc.get_status(task_id)
    assert status.id == task_id
    assert status.name == "alpha"
    assert status.status == TaskStatus.QUEUED.value
    assert status.steps == []


def test_cancel_queued_task(isolated_db: None) -> None:
    svc = TaskService()
    task_id = svc.create(_request())
    cancelled, current, _ = svc.cancel(task_id)
    assert cancelled is True
    assert current == TaskStatus.CANCELLED
    again_cancelled, current2, _ = svc.cancel(task_id)
    assert again_cancelled is False
    assert current2 == TaskStatus.CANCELLED


def test_list_tasks_filter_by_status(isolated_db: None) -> None:
    svc = TaskService()
    queued_id = svc.create(_request("q"))
    cancelled_id = svc.create(_request("c"))
    svc.cancel(cancelled_id)

    queued = svc.list_tasks(status="queued")
    cancelled = svc.list_tasks(status="cancelled")
    assert {t.id for t in queued} == {queued_id}
    assert {t.id for t in cancelled} == {cancelled_id}


def test_list_tasks_search_query(isolated_db: None) -> None:
    svc = TaskService()
    svc.create(_request("alpha-pipeline"))
    svc.create(_request("beta-pipeline"))
    matches = svc.list_tasks(query="alpha")
    assert len(matches) == 1
    assert matches[0].name == "alpha-pipeline"


def test_stats_reflects_status_counts(isolated_db: None) -> None:
    svc = TaskService()
    queued_id = svc.create(_request("q"))
    cancelled_id = svc.create(_request("c"))
    svc.cancel(cancelled_id)

    stats = svc.stats(queue_depth=2, running_task_id=queued_id)
    assert stats.total == 2
    assert stats.by_status["queued"] == 1
    assert stats.by_status["cancelled"] == 1
    assert stats.queue_depth == 2
    assert stats.running_task_id == queued_id
