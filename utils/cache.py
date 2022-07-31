import os
import json

class cache:
    def __init__(self):
        self.reset()
    def reset(self):
        self.update = {}
        if not os.path.exists('./cache/update/'):
            if not os.path.exists('./cache/'):
                os.mkdir('./cache/')
            os.mkdir('./cache/update/')
    def buildUpdate(self, guilds):
        for guild in guilds:
            if os.path.exists('./cache/update/'+guild):
                with open('./cache/update/'+guild, 'r') as file:
                    self.update[guild] = json.loads(file.read())
            else: self.update[guild] = {}
            for server in guilds[guild]:
                if server['address'] not in self.update[guild].keys(): self.update[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}
    