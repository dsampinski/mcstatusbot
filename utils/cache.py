import os
import json

class cache:
    def __init__(self):
        self._path = './cache/'
        self.reset()
    
    def reset(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        self.Updates = _Updates(self)

class _Updates:
    def __init__(self, cache):
        self._path = cache._path + 'updates/'
        self.reset()
    
    def reset(self):
        if not os.path.exists(self._path):
            os.mkdir(self._path)
        self.updates = {}
    
    def build(self, guildServers):
        self.updates = dict.fromkeys(guildServers.keys(), {})
        for guild in guildServers:
            if os.path.exists(self._path + str(guild)):
                with open(self._path + str(guild), 'r') as file:
                    self.updates[guild] = json.loads(file.read())
            else: self.updates[guild] = {}
            for server in guildServers[guild]:
                if server['address'] not in self.updates[guild]: self.updates[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

    def add(self, guild_id, address):
        if guild_id not in self.updates: self.updates[guild_id] = {}
        self.updates[guild_id][address] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}

    def write(self, guild_id):
        with open(self._path + str(guild_id), 'w') as file:
            file.write(json.dumps(self.updates[guild_id]))