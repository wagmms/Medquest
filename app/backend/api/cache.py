"""Cache em memória com TTL e invalidação segura por usuário."""
import time
from threading import Lock


class SimpleTTLCache:
    def __init__(self, ttl_seconds: int, max_size: int = 500):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache = {}
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            entry = self.cache.get(key)
            if entry is not None:
                value, expiry = entry
                if time.time() < expiry:
                    return value
                del self.cache[key]
            return None

    def set(self, key, value):
        with self.lock:
            now = time.time()
            stale = [k for k, (_, exp) in self.cache.items() if now >= exp]
            for k in stale:
                del self.cache[k]
            if len(self.cache) >= self.max_size:
                oldest = min(self.cache.keys(), key=lambda k: self.cache[k][1])
                del self.cache[oldest]
            self.cache[key] = (value, now + self.ttl)

    def clear_user(self, user_id):
        uid_str = str(user_id)
        with self.lock:
            keys = [
                key
                for key in self.cache
                if (isinstance(key, tuple) and len(key) > 0 and key[0] == user_id)
                or (isinstance(key, str) and (key == uid_str or key.startswith(f"{uid_str}:") or key.startswith(f"{uid_str}_")))
            ]
            for key in keys:
                del self.cache[key]
