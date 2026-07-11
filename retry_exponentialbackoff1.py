from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)


# Custom error for temporary problems
class TemporaryError(Exception):
    pass


# Custom error for permanent problems
class PermanentError(Exception):
    pass


# Common retry rule:
# - retry only TemporaryError
# - stop after 4 attempts
# - use exponential backoff + jitter
retry_temporary_errors = retry(
    retry=retry_if_exception_type(TemporaryError),
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=8),
    reraise=True,
)


# Example 1: API succeeds after temporary server errors
api_responses = [500, 503, 200]

@retry_temporary_errors
def call_api():
    status_code = api_responses.pop(0)

    print(f"API status: {status_code}")

    if status_code >= 500:
        raise TemporaryError("Server error. Retry this.")

    if status_code >= 400:
        raise PermanentError("Client error. Do not retry this.")

    return "API success"


# Example 2: Database connection succeeds after temporary failures
db_results = ["timeout", "connection lost", "connected"]

@retry_temporary_errors
def connect_to_database():
    result = db_results.pop(0)

    print(f"Database result: {result}")

    if result in ["timeout", "connection lost"]:
        raise TemporaryError("Database temporarily unavailable.")

    return "Database connected"


# Example 3: Wrong password should not be retried
@retry_temporary_errors
def login():
    print("Trying login...")

    raise PermanentError("Wrong password. Do not retry.")


print("\n--- Example 1: API ---")
print(call_api())

print("\n--- Example 2: Database ---")
print(connect_to_database())

print("\n--- Example 3: Login ---")
try:
    login()
except PermanentError as error:
    print(error)