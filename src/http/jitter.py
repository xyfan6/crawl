import random


def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    delay = min(base * (2 ** attempt), cap)
    return delay + random.uniform(-delay * 0.3, delay * 0.3)
