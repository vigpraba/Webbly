import time

from errors import TemporaryError, CircuitOpenError


class CircuitBreaker:
    def __init__(self, failure_limit=3, reset_after=5):
        self.failure_limit = failure_limit
        self.reset_after = reset_after

        self.failure_count = 0
        self.state = "CLOSED"
        self.opened_at = None

    def call(self, func):
        # If circuit is OPEN, block calls for some time
        if self.state == "OPEN":
            time_passed = time.time() - self.opened_at

            if time_passed < self.reset_after:
                raise CircuitOpenError("Circuit is OPEN. Not calling service.")

            # After waiting, allow one test call
            self.state = "HALF_OPEN"
            print("Circuit is HALF_OPEN. Trying one test call.")

        try:
            result = func()

            # If call succeeds, reset circuit
            self.failure_count = 0
            self.state = "CLOSED"
            self.opened_at = None

            print("Circuit is CLOSED.")
            return result

        except TemporaryError:
            self.failure_count += 1
            print(f"Failure count: {self.failure_count}")

            # If too many failures, open the circuit
            if self.failure_count >= self.failure_limit:
                self.state = "OPEN"
                self.opened_at = time.time()
                print("Circuit is now OPEN.")

            raise