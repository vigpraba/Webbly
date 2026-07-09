from errors import TemporaryError


responses = ["fail", "fail", "fail", "success"]


def call_api():
    response = responses.pop(0)

    print(f"API response: {response}")

    if response == "fail":
        raise TemporaryError("API failed temporarily.")

    return "API success"