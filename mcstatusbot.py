import discord
import asyncio
from mcstatus.server import JavaServer as js
import os
import json
from datetime import datetime as dt, timedelta as td

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
config = {'token': '<DISCORD BOT TOKEN>', 'adminId': '<DISCORD ID OF ADMIN>', 'pingInterval': 10, 'updateInterval': 10, 'addressesPerGuild': 2, 'showPlayers': True}
guilds = {}
lastUpdate = {}
servers = {}
dbUpdate = True

async def db_updater():
    global dbUpdate

    while True:
        if dbUpdate:
            with open('db.json', 'w') as file:
                file.write(json.dumps(guilds))
            dbUpdate = False
        with open('lastUpdate.dat', 'w') as file:
            file.write(json.dumps(lastUpdate))
        await asyncio.sleep(10)


async def init():
    global config
    global guilds
    global lastUpdate
    global pingTask
    global updateTask
    global dbUpdaterTask
    
    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config))

    loop.create_task(login())

    if os.path.exists('db.json'):
        with open('db.json', 'r') as file:
            guilds = json.loads(file.read())
        
        if len(guilds.keys()):
            if os.path.exists('lastUpdate.dat'):
                with open('lastUpdate.dat', 'r') as file:
                    lastUpdate = json.loads(file.read())
            
            for guild in guilds:
                if not os.path.exists('lastUpdate.dat') or guild not in lastUpdate.keys(): lastUpdate[guild] = {}
                for server in guilds[guild]:
                    if server['address'] not in servers.keys():
                        try: servers[server['address']] = {'lookup': await js.async_lookup(server['address']), 'time': None, 'reply': None}
                        except Exception as e: print(e)
                    if not os.path.exists('lastUpdate.dat') or server['address'] not in lastUpdate[guild].keys(): lastUpdate[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}
    
    pingTask = loop.create_task(ping())
    updateTask = loop.create_task(update())
    dbUpdaterTask = loop.create_task(db_updater())
    loop.create_task(crash_handler())

@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))
    print('Admin:', client.get_user(int(config['adminId']) if config['adminId'].isnumeric() else None), '\n')

@client.event
async def on_message(message):
    global config
    global dbUpdate

    if message.author == client.user:
        return

    if message.content.startswith('$ping'):
        if not (pingTask.done() or updateTask.done() or dbUpdaterTask.done()):
            await message.channel.send('MC Status Bot is running')
        else: await message.channel.send('An error has occured in MC Status Bot (task(s) not running)')
    
    if message.content.startswith('$help'):
        await message.channel.send('https://github.com/dsampinski/mcstatusbot#commands')
    
    if message.content.startswith('$reload'):
        if str(message.author.id) != config['adminId']:
            return
        if os.path.exists('config.json'):
            with open('config.json', 'r') as file:
                config = json.loads(file.read())
        else:
            with open('config.json', 'w') as file:
                file.write(json.dumps(config))
        await message.channel.send('Reloaded config')

    if message.content.startswith('$shutdown'):
        if str(message.author.id) != config['adminId']:
            return
        await message.channel.send('Shutting down...')
        loop.stop()
        with open('db.json', 'w') as file:
            file.write(json.dumps(guilds))

    if message.content.startswith('$add'):
        if str(message.author.id) != config['adminId'] and not message.guild.get_member(message.author.id).guild_permissions.manage_channels:
            await message.channel.send('Not enough permissions')
            return
        if len(message.content.split(' ')) != 3:
            await message.channel.send('Invalid arguments\n$add <address> <name>')
            return

        if str(message.guild.id) in guilds.keys():
            for server in guilds[str(message.guild.id)]:
                if message.content.split(' ')[1] == server['address']:
                    await message.channel.send('Address is already added')
                    return
            if str(message.author.id) != config['adminId'] and len(guilds[str(message.guild.id)]) >= config['addressesPerGuild']:
                await message.channel.send('Reached maximum amount of addresses in this guild')
                return
        else: guilds[str(message.guild.id)] = []

        try:
            if message.content.split(' ')[1] not in servers.keys():
                servers[message.content.split(' ')[1]] = {'lookup': await js.async_lookup(message.content.split(' ')[1]), 'time': None, 'reply': None}
        except Exception as e: await message.channel.send('Error: ' + str(e))
        else:
            try:
                newCat = await message.guild.create_category(message.content.split(' ')[2])
                statChan = await message.guild.create_voice_channel('Pinging...', category=newCat)
                await statChan.set_permissions(client.user, connect=True)
                await statChan.set_permissions(message.guild.default_role, connect=False)
                if config['showPlayers']:
                    playChan = await message.guild.create_text_channel('players', category=newCat)
                    await playChan.set_permissions(client.user, send_messages=True)
                    await playChan.set_permissions(message.guild.default_role, send_messages=False)
                    msg = await client.get_channel(id=playChan.id).send('Pinging...')
            except Exception as e: await message.channel.send('Error: ' + str(e))
            else:
                guilds[str(message.guild.id)].append({'address': message.content.split(' ')[1], 'category': newCat.id, 'statusChannel': statChan.id, 'playersChannel': (playChan.id if config['showPlayers'] else None), 'message': (msg.id if config['showPlayers'] else None)})
                if str(message.guild.id) not in lastUpdate.keys(): lastUpdate[str(message.guild.id)] = {}
                if message.content.split(' ')[1] not in lastUpdate[str(message.guild.id)].keys(): lastUpdate[str(message.guild.id)][message.content.split(' ')[1]] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}
                await message.channel.send('Added {}\'s status to this guild'.format(message.content.split(' ')[1]))
                dbUpdate = True
    
    if message.content.startswith('$rem'):
        if str(message.author.id) != config['adminId'] and not message.guild.get_member(message.author.id).guild_permissions.manage_channels:
            await message.channel.send('Not enough permissions')
            return
        if len(message.content.split(' ')) != 2:
            await message.channel.send('Invalid arguments\n$rem <address>')
            return

        if str(message.guild.id) in guilds.keys() and len(guilds[str(message.guild.id)]):
            for c, server in enumerate(guilds[str(message.guild.id)]):
                if server['address'] == message.content.split(' ')[1]:
                    try:
                        if client.get_channel(id=guilds[str(message.guild.id)][c]['statusChannel']) is not None:
                            await client.get_channel(id=guilds[str(message.guild.id)][c]['statusChannel']).delete()
                        if client.get_channel(id=guilds[str(message.guild.id)][c]['playersChannel']) is not None:
                            await client.get_channel(id=guilds[str(message.guild.id)][c]['playersChannel']).delete()
                        if client.get_channel(id=guilds[str(message.guild.id)][c]['category']) is not None:
                            await client.get_channel(id=guilds[str(message.guild.id)][c]['category']).delete()
                    except Exception as e: await message.channel.send('Error: ' + str(e))
                    
                    guilds[str(message.guild.id)].pop(c)
                    await message.channel.send('Removed {}\'s status from this guild'.format(message.content.split(' ')[1]))
                    dbUpdate = True
                    break
    
    if message.content.startswith('$list'):
        if str(message.author.id) != config['adminId'] and not message.guild.get_member(message.author.id).guild_permissions.manage_channels:
            await message.channel.send('Not enough permissions')
            return

        if str(message.guild.id) in guilds.keys():
            addresses = 'Addresses added to this guild:\n'
            for server in guilds[str(message.guild.id)]:
                addresses += server['address'] + '\n'
            await message.channel.send(addresses)


async def ping():
    while True:
        for guild in guilds:
            for server in guilds[guild]:
                if servers[server['address']]['time'] is None or dt.now() - servers[server['address']]['time'] >= td(seconds=config['pingInterval']):
                    servers[server['address']]['time'] = dt.now()
                    try:
                        servers[server['address']]['reply'] = await servers[server['address']]['lookup'].async_status()
                    except Exception:
                        servers[server['address']]['reply'] = None
                await asyncio.sleep(0)
        await asyncio.sleep(1)

async def update():
    while True:
        for guild in guilds:
            for server in guilds[guild]:
                if servers[server['address']]['reply'] is not None:
                    if servers[server['address']]['reply'].players.sample is not None:
                        if config['showPlayers']:
                            players = 'Players:\n\n'
                            for player in servers[server['address']]['reply'].players.sample:
                                players += player.name + '\n'
                        status = '🟢 ONLINE: ' + str(servers[server['address']]['reply'].players.online) + ' / ' + str(servers[server['address']]['reply'].players.max)
                    else:
                        if config['showPlayers']: players = 'EMPTY'
                        status = '🟢 ONLINE: 0 / ' + str(servers[server['address']]['reply'].players.max)
                else:
                    if config['showPlayers']: players = 'OFFLINE'
                    status = '🔴 OFFLINE'

                try:
                    if (lastUpdate[guild][server['address']]['statusTime'] is None \
                        or dt.now() - dt.fromisoformat(lastUpdate[guild][server['address']]['statusTime']) >= td(seconds=max(300, config['updateInterval']))) \
                        and status != lastUpdate[guild][server['address']]['status'] and client.get_channel(id=server['statusChannel']) is not None:
                            lastUpdate[guild][server['address']]['statusTime'] = dt.isoformat(dt.now())
                            lastUpdate[guild][server['address']]['status'] = status
                            await client.get_channel(id=server['statusChannel']).edit(name=status)
                    if config['showPlayers'] and (lastUpdate[guild][server['address']]['playersTime'] is None \
                        or dt.now() - dt.fromisoformat(lastUpdate[guild][server['address']]['playersTime']) >= td(seconds=config['updateInterval'])) \
                        and players != lastUpdate[guild][server['address']]['players'] and client.get_channel(id=server['playersChannel']) is not None \
                        and server['message'] is not None and client.get_channel(id=server['playersChannel']).get_partial_message(server['message']) is not None:
                            lastUpdate[guild][server['address']]['playersTime'] = dt.isoformat(dt.now())
                            lastUpdate[guild][server['address']]['players'] = players
                            await client.get_channel(id=server['playersChannel']).get_partial_message(server['message']).edit(content=players)
                except Exception as e: print(e)
                await asyncio.sleep(0)
        await asyncio.sleep(1)

async def crash_handler():
    while True:
        await asyncio.sleep(10)
        if updateTask.done():
            loop.create_task(update())
            print('Restarted update task')
        if pingTask.done():
            loop.create_task(ping())
            print('Restarted ping task')
        if dbUpdaterTask.done():
            loop.create_task(db_updater())
            print('Restarted db_updater task')

async def login():
    try:
        await client.start(config['token'])
    except Exception as e:
        print(e)
        loop.stop()
    
loop = asyncio.get_event_loop()
loop.create_task(init())
loop.run_forever()
