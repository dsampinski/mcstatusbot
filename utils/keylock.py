import asyncio

class keylock:
    def __init__(self):
        self.reset()
    async def acquire(self, key):
        while key in self.keys.keys(): await asyncio.sleep(0)
        self.keys[key] = None
    def release(self, key):
        if key in self.keys.keys(): self.keys.pop(key)
    def reset(self):
        self.keys = {}