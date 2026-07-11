# main.py
from fastapi import FastAPI
from celery.result import AsyncResult
from tasks import celery_app, send_email

app = FastAPI()

@app.post("/signup")
def signup(email: str):
    task = send_email.delay(email)
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }