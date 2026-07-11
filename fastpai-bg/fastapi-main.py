# main.py
from fastapi import FastAPI, BackgroundTasks
import time

app = FastAPI()

def send_email(email: str):
    time.sleep(5)  # pretend this is slow
    print(f"Verification email sent to {email}")

@app.post("/signup")
def signup(email: str, background_tasks: BackgroundTasks):
    # FastAPI will run this after returning the response
    background_tasks.add_task(send_email, email)

    return {"message": "User created. Verification email will be sent soon."}