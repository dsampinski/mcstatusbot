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
            self.updates = {}
        
        def build(self, guilds):
            for guild in guilds:
                if os.path.exists(self._path + guild):
                    with open(self._path + guild, 'r') as file:
                        self.updates[guild] = json.loads(file.read())
                else: self.updates[guild] = {}
                for server in guilds[guild]:
                    if server['address'] not in self.updates[guild].keys(): self.updates[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

        def add(self, id, address):
            if id not in self.updates.keys(): self.updates[id] = {}
            if address not in self.updates[id].keys(): self.updates[id][address] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

        def write(self, id):
            with open(self._path + id, 'w') as file:
                file.write(json.dumps(self.updates[id]))