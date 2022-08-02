import os
import json

class cache:
    def __init__(self):
        self._path = './cache/'
        self.reset()
    
    def reset(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        self.Updates = self._Updates(self)

    class _Updates:
        def __init__(self, cache):
            self._path = cache._path + 'updates/'
            self.reset()
        
        def reset(self):
            if not os.path.exists(self._path):
                os.mkdir(self._path)
            cache.updates = {}
        
        def build(self, guilds):
            for guild in guilds:
                if os.path.exists(self._path + guild):
                    with open(self._path + guild, 'r') as file:
                        cache.updates[guild] = json.loads(file.read())
                else: cache.updates[guild] = {}
                for server in guilds[guild]:
                    if server['address'] not in cache.updates[guild].keys(): cache.updates[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

        def add(self, id, address):
            if id not in cache.updates.keys(): cache.updates[id] = {}
            if address not in cache.updates[id].keys(): cache.updates[id][address] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

        def write(self, id):
            with open(self._path + id, 'w') as file:
                file.write(json.dumps(cache.updates[id]))