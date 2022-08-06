import sqlite3
import json
import os

class database:
    def __init__(self, file):
        self.db = sqlite3.connect(file)
        self.db.execute('''CREATE TABLE IF NOT EXISTS guilds(guild_id INT PRIMARY KEY, guild_name TEXT, guild_join_date TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS servers(guild_id INT REFERENCES guild,
                                                                server_address TEXT DEFAULT NULL,
                                                                server_category INT DEFAULT NULL,
                                                                server_statusChannel INT DEFAULT NULL,
                                                                server_playersChannel INT DEFAULT NULL,
                                                                server_message INT DEFAULT NULL,
                                                                PRIMARY KEY(guild_id, server_address))''')
        self.db.commit()
        self._guild_attr = ('id', 'name', 'join_date')
        self._server_attr = ('guild_id', 'address', 'category', 'statusChannel', 'playersChannel', 'message')
    
    def getInit(self):
        query = self.db.execute('SELECT guild_id FROM guilds ORDER BY guild_id').fetchall()
        guild_ids = [entity[0] for entity in query]
        query = self.db.execute('SELECT DISTINCT server_address FROM servers ORDER BY server_address').fetchall()
        addresses = [entity[0] for entity in query]
        return guild_ids, addresses
    
    def getGuilds(self, guild_id=None):
        if guild_id is None:
            query = self.db.execute('SELECT * FROM guilds ORDER BY guild_id').fetchall()
            return [dict(zip(self._guild_attr, entity)) for entity in query]
        else:
            query = self.db.execute('SELECT * FROM guilds WHERE guild_id = :guild_id', {'guild_id': guild_id}).fetchone()
            return dict(zip(self._guild_attr, query))

    def getGuildServers(self, guild_id=None, address=None):
        if guild_id is not None:
            if address is None:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id', {'guild_id': guild_id}).fetchall()
                return [dict(zip(self._server_attr[1:], entity[1:])) for entity in query]
            else:
                query = self.db.execute('SELECT * FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address}).fetchone()
                return dict(zip(self._server_attr[1:], query[1:]))
        query = self.db.execute('''SELECT *
                                    FROM guilds LEFT NATURAL JOIN servers
                                    ORDER BY guild_id''').fetchall()
        guildServers = dict.fromkeys([guild['id'] for guild in self.getGuilds()])
        for key in guildServers: guildServers[key] = []
        for entity in query:
            if entity[3] is not None: guildServers[entity[0]].append(dict(zip(self._server_attr[1:], entity[3:])))
        return guildServers
    
    def guildHasServer(self, guild_id, address):
        return self.db.execute('SELECT 1 FROM servers WHERE guild_id = :guild_id AND server_address = :address', {'guild_id': guild_id, 'address': address}).fetchone() is not None
    
    def addGuild(self, guild_id, name):
        self.db.execute('INSERT INTO guilds(guild_id, guild_name) VALUES(:guild_id, :name)', {'guild_id': guild_id, 'name': name})
        self.db.commit()

    def addServer(self, guild_id, address, category, statusChannel, playersChannel, message):
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
        with open(json_db) as file:
            guildServers = json.loads(file.read())
        print('Migrating...')
        db = database(sqlite_db)
        for guild in guildServers:
            db.addGuild(guild, None)
            for server in guildServers[guild]:
                db.addServer(guild, server['address'], server['category'], server['statusChannel'], server['playersChannel'], server['message'])
        db.close()
        print('Done')
    else: print('File does not exist')