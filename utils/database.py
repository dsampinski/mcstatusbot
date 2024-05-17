import sqlite3
import json
import os

class database:
    _db_version = 3
    _server_attr = ('address', 'categoryId', 'statusChannelId', 'playersChannelId', 'messageId', 'statusTime', 'status', 'playersTime', 'players', 'pingTime')
    def __init__(self, file='database.db'):
        self.db = sqlite3.connect(file)
        self.db.execute('PRAGMA journal_mode = MEMORY')
        self.db.execute('CREATE TABLE IF NOT EXISTS _variables(name TEXT PRIMARY KEY, intValue INT, realValue REAL, textValue TEXT)')
        version = self.db.execute('SELECT intValue FROM _variables WHERE name = "version"').fetchone()
        if version is None: self.db.execute('INSERT INTO _variables(name, intValue) VALUES("version", ?)', (database._db_version,))
        self.db.execute('''CREATE TABLE IF NOT EXISTS servers(  guild_id INT,
                                                                server_address TEXT,
                                                                server_categoryId INT DEFAULT NULL,
                                                                server_statusChannelId INT DEFAULT NULL,
                                                                server_playersChannelId INT DEFAULT NULL,
                                                                server_messageId INT DEFAULT NULL,
                                                                server_statusTime TEXT DEFAULT NULL,
                                                                server_status TEXT DEFAULT NULL,
                                                                server_playersTime TEXT DEFAULT NULL,
                                                                server_players TEXT DEFAULT NULL,
                                                                server_pingTime TEXT DEFAULT NULL,
                                                                PRIMARY KEY(guild_id, server_address)   )''')
        self.db.commit()
    
    def getServers(self, address=None, addressOnly=False, guildIdOnly=False):
        if address is None:
            if addressOnly:
                query = self.db.execute('SELECT DISTINCT server_address FROM servers').fetchall()
                return [entity[0] for entity in query]
            elif guildIdOnly:
                query = self.db.execute('SELECT DISTINCT guild_id FROM servers').fetchall()
                return [entity[0] for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers').fetchall()
                return [tuple(entity) for entity in query]
        else:
            query = self.db.execute('SELECT * FROM servers WHERE server_address = :address', {'address': address}).fetchall()
            return [tuple(entity) for entity in query]

    def countServers(self, guildId=None):
        if guildId is None:
            query = self.db.execute('SELECT COUNT(server_address) FROM servers').fetchone()
        else: query = self.db.execute('SELECT COUNT(server_address) FROM servers WHERE guild_id = ?', (guildId,)).fetchone()
        return query[0]

    def getGuildServers(self, guildId=None, address=None):
        if guildId is not None:
            if address is None:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guildId', {'guildId': guildId}).fetchall()
                return [dict(zip(database._server_attr, entity[1:])) for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guildId AND server_address = :address', {'guildId': guildId, 'address': address}).fetchone()
                return dict(zip(database._server_attr, query[1:])) if query is not None else None
        else:
            guildServers = dict.fromkeys(self.getServers(guildIdOnly=True))
            for guild in guildServers: guildServers[guild] = self.getGuildServers(guild)
            return guildServers

    def addServer(self, guildId, address, categoryId, statusChannelId, playersChannelId, messageId):
        if self.getGuildServers(guildId, address) is None:
            self.db.execute('''INSERT INTO servers(guild_id, server_address, server_categoryId, server_statusChannelId, server_playersChannelId, server_messageId)
                                            VALUES(?, ?, ?, ?, ?, ?)''', (guildId, address, categoryId, statusChannelId, playersChannelId, messageId))
            self.db.commit()

    def updateServerStatus(self, guildId, address, status):
        self.db.execute('''UPDATE servers SET server_statusTime = strftime("%Y-%m-%dT%H:%M:%S", datetime('now', 'localtime')), server_status = ?
                            WHERE guild_id = ? AND server_address = ?''', (status, guildId, address))
        self.db.commit()
    
    def updateServerPlayers(self, guildId, address, players):
        self.db.execute('''UPDATE servers SET server_playersTime = strftime("%Y-%m-%dT%H:%M:%S", datetime('now', 'localtime')), server_players = ?
                            WHERE guild_id = ? AND server_address = ?''', (players, guildId, address))
        self.db.commit()
    
    def pingServer(self, guildId, address):
        self.db.execute('''UPDATE servers SET server_pingTime = strftime("%Y-%m-%dT%H:%M:%S", datetime('now', 'localtime'))
                            WHERE guild_id = ? AND server_address = ?''', (guildId, address))
        self.db.commit()

    def removeServers(self, guildId, address=None, statusChannelId=None):
        if address is None:
            if statusChannelId is not None:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guildId AND server_statusChannelId = :statusChannelId', {'guildId': guildId, 'statusChannelId': statusChannelId}).fetchone()
                if query is not None:
                    self.removeServers(guildId, query[1])
                    return query[1]
                else: return None
            addresses = [server['address'] for server in self.getGuildServers(guildId)]
            self.db.execute('DELETE FROM servers WHERE guild_id = :guildId', {'guildId': guildId})
            self.db.commit()
            return addresses
        else: self.db.execute('DELETE FROM servers WHERE guild_id = :guildId AND server_address = :address', {'guildId': guildId, 'address': address})
        self.db.commit()
            

    def close(self):
        self.db.commit()
        self.db.close()
    
    @classmethod
    def jsonToSqlite(self, json_db='db.json', sqlite_db='database.db'):
        if os.path.exists(json_db):
            with open(json_db, 'r') as file:
                guildServers = json.loads(file.read())
            print('Migrating...')
            db = database(sqlite_db)
            for guild in guildServers:
                for server in guildServers[guild]:
                    db.addServer(int(guild), server['address'], server['categoryId'], server['statusChannelId'], server['playersChannelId'], server['messageId'])
            db.close()
            print('Done')
        else: print('File does not exist')

    @classmethod
    def updateDB(self, file='database.db', version=None):
        if not os.path.exists(file): return
        if version is None:
            db = sqlite3.connect(file)
            if db.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="_variables"').fetchone() is not None:
                version = db.execute('SELECT intValue FROM _variables WHERE name = "version"').fetchone()
                version = version[0] if version is not None else None
            else: version = 1
            db.close()
        if version == 1:
            db = database(file)
            db.db.execute('ALTER TABLE servers ADD server_statusTime TEXT DEFAULT NULL')
            db.db.execute('ALTER TABLE servers ADD server_status TEXT DEFAULT NULL')
            db.db.execute('ALTER TABLE servers ADD server_playersTime TEXT DEFAULT NULL')
            db.db.execute('ALTER TABLE servers ADD server_players TEXT DEFAULT NULL')
            db.db.execute('UPDATE _variables SET intValue = ? WHERE name = "version"', (2,))
            db.close()
            version = 2
        if version == 2:
            db = database(file)
            db.db.execute('ALTER TABLE servers RENAME server_category TO server_categoryId')
            db.db.execute('ALTER TABLE servers RENAME server_statusChannel TO server_statusChannelId')
            db.db.execute('ALTER TABLE servers RENAME server_playersChannel TO server_playersChannelId')
            db.db.execute('ALTER TABLE servers RENAME server_message TO server_messageId')
            db.db.execute('ALTER TABLE servers ADD server_pingTime TEXT DEFAULT NULL')
            db.db.execute('UPDATE _variables SET intValue = ? WHERE name = "version"', (3,))
            db.close()
            version = 3
            return True