from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

class TemporaryError(Exception):
    pass

class PermanentError(Exception):
    pass


responses = [500, 502, 200]  # pretend API responses


@retry(
    retry=retry_if_exception_type(TemporaryError),   # retry only temporary failures
    stop=stop_after_attempt(3),                      # stop after 3 attempts
    wait=wait_exponential_jitter(                    # exponential backoff + jitter
        initial=1,                                   # first wait is around 1 second
        max=10                                      # never wait more than 10 seconds
    ),
    reraise=True                                     # raise the final error if all retries fail
)
def call_api():
    status_code = responses.pop(0)

    print(f"API returned: {status_code}")

    if status_code >= 500:
        raise TemporaryError("Server problem, retry this")

    if status_code >= 400:
        raise PermanentError("Client problem, do not retry this")

    return "Success!"


result = call_api()
print(result)