import time

from celery.exceptions import TimeoutError

from tasks_withDelay import demo


TASK_COUNT = 8
TASK_DURATION_SECONDS = 3


def main() -> None:
    print(
        f"Submitting {TASK_COUNT} tasks. "
        f"Each task takes approximately "
        f"{TASK_DURATION_SECONDS} seconds."
    )

    start_time = time.perf_counter()

    # Store each AsyncResult so we can retrieve its result later.
    task_results = []

    # Submit all eight tasks without waiting between submissions.
    for task_number in range(1, TASK_COUNT + 1):
        message = f"Task {task_number}"

        async_result = demo.delay(
            message,
            TASK_DURATION_SECONDS,
        )

        task_results.append(async_result)

        print(
            f"Submitted {message}: "
            f"task_id={async_result.id}"
        )

    submission_time = time.perf_counter() - start_time

    print()
    print(
        f"All tasks were submitted in "
        f"{submission_time:.2f} seconds."
    )
    print("Waiting for worker results...")
    print()

    completed_results = []

    # All tasks have already been submitted.
    # This loop only waits for and displays their results.
    for task_number, async_result in enumerate(
        task_results,
        start=1,
    ):
        try:
            result = async_result.get(timeout=30)
        except TimeoutError:
            print(
                f"Task {task_number} did not finish "
                f"within 30 seconds."
            )
            return

        completed_results.append(result)

        print(
            f"Task {task_number} completed: "
            f"worker={result['worker']}, "
            f"duration={result['duration_seconds']} seconds"
        )

    total_time = time.perf_counter() - start_time

    print()
    print(f"Completed tasks: {len(completed_results)}")
    print(f"Total elapsed time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()
