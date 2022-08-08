import sqlite3
import json
import os

class database:
    def __init__(self, file):
        self.db = sqlite3.connect(file)
        self.db.execute('''CREATE TABLE IF NOT EXISTS servers(  guild_id INT,
                                                                server_address TEXT,
                                                                server_category INT DEFAULT NULL,
                                                                server_statusChannel INT DEFAULT NULL,
                                                                server_playersChannel INT DEFAULT NULL,
                                                                server_message INT DEFAULT NULL,
                                                                PRIMARY KEY(guild_id, server_address)   )''')
        self.db.commit()
        self._server_attr = ('guild_id', 'address', 'category', 'statusChannel', 'playersChannel', 'message')
    
    def getServers(self, address=None, addressOnly=False, guildIdOnly=False):
        if address is None:
            if addressOnly:
                query = self.db.execute('SELECT DISTINCT server_address FROM servers ORDER BY server_address').fetchall()
                return [entity[0] for entity in query]
            elif guildIdOnly:
                query = self.db.execute('SELECT DISTINCT guild_id FROM servers ORDER BY guild_id').fetchall()
                return [entity[0] for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers ORDER BY guild_id, server_address').fetchall()
                return [dict(zip(self._server_attr, entity)) for entity in query]
        else:
            query = self.db.execute('SELECT * FROM servers WHERE server_address = :address', {'address': address}).fetchone()
            return dict(zip(self._server_attr, query)) if query is not None else None

    def getGuildServers(self, guild_id=None, address=None):
        if guild_id is not None:
            if address is None:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id ORDER BY server_address', {'guild_id': guild_id}).fetchall()
                return [dict(zip(self._server_attr[1:], entity[1:])) for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address}).fetchone()
                return dict(zip(self._server_attr[1:], query[1:])) if query is not None else None
        else:
            query = self.db.execute('SELECT * FROM servers ORDER BY guild_id, server_address').fetchall()
            guildServers = dict.fromkeys(self.getServers(guildIdOnly=True))
            for entity in query:
                if type(guildServers[entity[0]]) is not list: guildServers[entity[0]] = []
                guildServers[entity[0]].append(dict(zip(self._server_attr[1:], entity[1:])))
            return guildServers

    def addServer(self, guild_id, address, category, statusChannel, playersChannel, message):
        if self.getGuildServers(guild_id, address) is None:
            attr = dict(zip(self._server_attr, (guild_id, address, category, statusChannel, playersChannel, message)))
            self.db.execute('INSERT INTO servers VALUES(:guild_id, :address, :category, :statusChannel, :playersChannel, :message)', attr)
            self.db.commit()

    def removeServer(self, guild_id, address):
        self.db.execute('DELETE FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address})
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()
    
def migrateFromJson(json_db='db.json', sqlite_db='database.db'):
    if os.path.exists(json_db):
        with open(json_db, 'r') as file:
            guildServers = json.loads(file.read())
        print('Migrating...')
        db = database(sqlite_db)
        for guild in guildServers:
            for server in guildServers[guild]:
                db.addServer(int(guild), server['address'], server['category'], server['statusChannel'], server['playersChannel'], server['message'])
        db.close()
        print('Done')
    else: print('File does not exist')