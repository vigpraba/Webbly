import time

from circuit_breaker import CircuitBreaker
from fake_api import call_api
from errors import TemporaryError, CircuitOpenError


breaker = CircuitBreaker(failure_limit=3, reset_after=5)


for i in range(4):
    print(f"\nCall {i + 1}")

    try:
        result = breaker.call(call_api)
        print(result)

    except TemporaryError as error:
        print(error)

    except CircuitOpenError as error:
        print(error)


print("\nWaiting for circuit to reset...")
time.sleep(6)


print("\nTrying again after waiting")

try:
    result = breaker.call(call_api)
    print(result)

except TemporaryError as error:
    print(error)

except CircuitOpenError as error:
    print(error)