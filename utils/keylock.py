import asyncio

class keylock:
    def __init__(self):
        self._closed = False
        self.reset()
    async def acquire(self, key):
        if self._closed: return False
        if key in self.keys:
            trig = self.keys[key][-1] + 1
            self.keys[key].append(trig)
        else:
            trig = 0
            self.keys[key] = [0]
        while self.keys[key][0] != trig or (key != 'init' and 'init' in self.keys): await asyncio.sleep(0)
        return True
    def release(self, key):
        if key in self.keys:
            if len(self.keys[key]) > 1: self.keys[key].pop(0)
            else: self.keys.pop(key)
    def reset(self):
        self.keys = {}
    async def close(self):
        self._closed = True
        while self.keys: await asyncio.sleep(0)