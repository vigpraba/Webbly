import time
from typing import Any

from celery import Celery


app = Celery(
    "tasks_withDelay",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/1",
)


app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


@app.task(
    bind=True,
    name="tasks_withDelay.demo",
)
def demo(
    self,
    message: str,
    seconds: int = 3,
) -> dict[str, Any]:
    """
    Simulate a task that takes some time.

    The task returns information about which worker executed it.
    """
    task_id = self.request.id
    worker_name = self.request.hostname

    print(
        f"[{worker_name}] Starting task {task_id}: {message}",
        flush=True,
    )

    # Simulate work that takes time.
    time.sleep(seconds)

    print(
        f"[{worker_name}] Completed task {task_id}: {message}",
        flush=True,
    )

    return {
        "task_id": task_id,
        "worker": worker_name,
        "message": message,
        "duration_seconds": seconds,
        "status": "completed",
    }
