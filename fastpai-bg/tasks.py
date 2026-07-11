# tasks.py
from celery import Celery
import time

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

@celery_app.task
def send_email(email: str):
    time.sleep(5)  # pretend this is slow
    print(f"Verification email sent to {email}")
    return "email sent"