import httpx


def client(timeout_s: float = 30.0) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout_s))

