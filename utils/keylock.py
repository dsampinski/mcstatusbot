import asyncio

class keylock:
    def __init__(self):
        self._closed = False
        self.reset()
    async def acquire(self, key):
        if self._closed: return False
        while key in self.keys or 'init' in self.keys: await asyncio.sleep(0)
        self.keys[key] = None
        return True
    def release(self, key):
        if key in self.keys: self.keys.pop(key)
    def reset(self):
        self.keys = {}
    async def close(self):
        self._closed = True
        while self.keys: await asyncio.sleep(0)