import sqlite3
import json
import os

db_version = 2

class database:
    def __init__(self, file='database.db'):
        self.db = sqlite3.connect(file)
        self.db.execute('PRAGMA journal_mode = MEMORY')
        self.db.execute('CREATE TABLE IF NOT EXISTS _variables(name TEXT PRIMARY KEY, intValue INT, realValue REAL, textValue TEXT)')
        version = self.db.execute('SELECT intValue FROM _variables WHERE name = "version"').fetchone()
        if version is None: self.db.execute('INSERT INTO _variables(name, intValue) VALUES("version", ?)', (db_version,))
        self.db.execute('''CREATE TABLE IF NOT EXISTS servers(  guild_id INT,
                                                                server_address TEXT,
                                                                server_category INT DEFAULT NULL,
                                                                server_statusChannel INT DEFAULT NULL,
                                                                server_playersChannel INT DEFAULT NULL,
                                                                server_message INT DEFAULT NULL,
                                                                server_statusTime TEXT DEFAULT NULL,
                                                                server_status TEXT DEFAULT NULL,
                                                                server_playersTime TEXT DEFAULT NULL,
                                                                server_players TEXT DEFAULT NULL,
                                                                PRIMARY KEY(guild_id, server_address)   )''')
        self.db.commit()
        self._server_attr = ('guild_id', 'address', 'category', 'statusChannel', 'playersChannel', 'message', 'statusTime', 'status', 'playersTime', 'players')
    
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
            query = self.db.execute('SELECT * FROM servers WHERE server_address = :address ORDER BY server_address', {'address': address}).fetchall()
            return [dict(zip(self._server_attr, entity)) for entity in query]

    def getGuildServers(self, guild_id=None, address=None):
        if guild_id is not None:
            if address is None:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id ORDER BY server_address', {'guild_id': guild_id}).fetchall()
                return [dict(zip(self._server_attr[1:], entity[1:])) for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address}).fetchone()
                return dict(zip(self._server_attr[1:], query[1:])) if query is not None else None
        else:
            guildServers = dict.fromkeys(self.getServers(guildIdOnly=True))
            for guild in guildServers: guildServers[guild] = self.getGuildServers(guild)
            return guildServers

    def addServer(self, guild_id, address, category, statusChannel, playersChannel, message):
        if self.getGuildServers(guild_id, address) is None:
            self.db.execute('''INSERT INTO servers(guild_id, server_address, server_category, server_statusChannel, server_playersChannel, server_message)
                                            VALUES(?, ?, ?, ?, ?, ?)''', (guild_id, address, category, statusChannel, playersChannel, message))
            self.db.commit()

    def updateServerStatus(self, guild_id, address, status):
        self.db.execute('''UPDATE servers SET server_statusTime = strftime("%Y-%m-%dT%H:%M:%S", 'NOW'), server_status = ?
                            WHERE guild_id = ? AND server_address = ?''', (status, guild_id, address))
        self.db.commit()
    
    def updateServerPlayers(self, guild_id, address, players):
        self.db.execute('''UPDATE servers SET server_playersTime = strftime("%Y-%m-%dT%H:%M:%S", 'NOW'), server_players = ?
                            WHERE guild_id = ? AND server_address = ?''', (players, guild_id, address))
        self.db.commit()

    def removeServers(self, guild_id, address=None):
        if address is None:
            addresses = [server['address'] for server in self.getGuildServers(guild_id)]
            self.db.execute('DELETE FROM servers WHERE guild_id = :guild_id', {'guild_id': guild_id})
            self.db.commit()
            return addresses
        else: self.db.execute('DELETE FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address})
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

def upgradeDB(file='database.db', version=None):
    if not os.path.exists(file): return
    if version is None:
        db = sqlite3.connect(file)
        if db.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="_variables"').fetchone() is not None:
            version = db.execute('SELECT intValue FROM _variables WHERE name = "version"').fetchone()
            version = version[0] if version is not None else None
        else: version = 1
        db.close()
    if version == 1:
        print('  Upgrading database')
        db = database(file)
        db.db.execute('ALTER TABLE servers ADD server_statusTime TEXT DEFAULT NULL')
        db.db.execute('ALTER TABLE servers ADD server_status TEXT DEFAULT NULL')
        db.db.execute('ALTER TABLE servers ADD server_playersTime TEXT DEFAULT NULL')
        db.db.execute('ALTER TABLE servers ADD server_players TEXT DEFAULT NULL')
        db.db.execute('UPDATE _variables SET intValue = ? WHERE name = "version"', (db_version,))
        db.close()