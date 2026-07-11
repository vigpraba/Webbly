from celery.exceptions import TimeoutError

from tasks import demo


def main() -> None:
    message = "Hello from the producer"

    print("Producer is sending a task...")
    print(f"Message: {message}")

    # Send the task to Redis.
    # This does not execute demo() inside main.py.
    task_result = demo.delay(message)

    print("Task was sent to Redis.")
    print(f"Task ID: {task_result.id}")
    print(f"Current task state: {task_result.state}")
    print("Waiting for the worker to complete the task...")

    try:
        # Wait for the worker's return value.
        final_result = task_result.get(timeout=20)
    except TimeoutError:
        print("The task did not finish within 20 seconds.")
        print("Check that Redis and the Celery worker are running.")
        return

    print(f"Final task state: {task_result.state}")
    print(f"Worker returned: {final_result}")
    print(f"Final task state: {task_result}")


if __name__ == "__main__":
    main()
