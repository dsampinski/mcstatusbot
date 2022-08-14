import asyncio

class keylock:
    def __init__(self):
        self._closed = False
        self.reset()
    async def acquire(self, key):
        if self._closed: return False
        if key in self._keys:
            trig = self._keys[key][-1] + 1
            self._keys[key].append(trig)
        else:
            trig = 0
            self._keys[key] = [trig]
        while self._keys[key][0] != trig or (key != 'master' and 'master' in self._keys): await asyncio.sleep(0)
        return True
    def release(self, key):
        if key in self._keys:
            if len(self._keys[key]) > 1: self._keys[key].pop(0)
            else: self._keys.pop(key)
    def reset(self):
        self._keys = {}
    async def close(self):
        self._closed = True
        while self._keys: await asyncio.sleep(0)