import asyncio

class keylock:
    def __init__(self):
        self._lock = False
        self.reset()
    async def acquire(self, key):
        if self._lock: return
        while key in self.keys.keys(): await asyncio.sleep(0)
        self.keys[key] = None
    def release(self, key):
        if key in self.keys.keys(): self.keys.pop(key)
    def reset(self):
        self.keys = {}
    async def close(self):
        self._lock = True
        while self.keys.keys(): await asyncio.sleep(0)