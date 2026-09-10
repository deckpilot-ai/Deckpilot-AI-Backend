"""Tests for lifecycle handling of in-process generation work."""

from sqlalchemy.orm import Session

from app.models.job import AgentTask, GenerationJob
from app.services.background_tasks import fail_interrupted_jobs
from tests.test_projects import create_authenticated_user


def test_interrupted_jobs_are_made_terminal(client, db_session: Session):
    headers = create_authenticated_user(client, "recovery@example.com")
    project_id = client.post(
        "/api/v1/projects",
        json={"title": "Recovery Project"},
        headers=headers,
    ).json()["id"]
    job = GenerationJob(project_id=project_id, status="running", mode="generate")
    db_session.add(job)
    db_session.flush()
    task = AgentTask(job_id=job.id, agent_type="deck_planner", status="running")
    db_session.add(task)
    db_session.commit()

    assert fail_interrupted_jobs(db_session) >= 1
    db_session.refresh(job)
    db_session.refresh(task)

    assert job.status == "permanently_failed"
    assert job.completed_at is not None
    assert task.status == "failed"
    assert task.error_code == "worker_interrupted"
