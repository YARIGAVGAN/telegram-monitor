import time
from collections import deque

class RateLimiter:
    def __init__(self, max_per_minute=20):
        self.max_per_minute = max_per_minute
        self.timestamps = deque()

    def allow(self):
        now = time.time()
        # Удаляем метки старше 60 секунд
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()
        if len(self.timestamps) < self.max_per_minute:
            self.timestamps.append(now)
            return True
        return False