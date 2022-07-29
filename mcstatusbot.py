import discord
from discord.ext import commands
import asyncio
import mcstatus
from mcstatus.server import JavaServer as js
import os
import json
from datetime import datetime as dt, timedelta as td
from utils.keylock import keylock as kl

bot = commands.Bot('$')
config = {'token': '<DISCORD BOT TOKEN>', 'adminId': '<DISCORD ID OF ADMIN>', 'pingInterval': 1, 'updateInterval': 1, 'addressesPerGuild': 2, 'showPlayers': True}
guilds = {}
lastUpdate = {}
servers = {}
dbUpdate = True
lock = kl()

async def db_updater():
    global dbUpdate

    while True:
        if dbUpdate:
            with open('db.json', 'w') as file:
                file.write(json.dumps(guilds))
            dbUpdate = False
        with open('lastUpdate.dat', 'w') as file:
            file.write(json.dumps(lastUpdate))
        await asyncio.sleep(60)


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
                if guild not in lastUpdate.keys(): lastUpdate[guild] = {}
                for server in guilds[guild]:
                    if server['address'] not in servers.keys():
                        try: servers[server['address']] = {'lookup': await js.async_lookup(server['address']), 'time': None, 'reply': None}
                        except Exception as e: print(e)
                    if server['address'] not in lastUpdate[guild].keys(): lastUpdate[guild][server['address']] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}
    
    pingTask = loop.create_task(ping())
    updateTask = loop.create_task(update())
    dbUpdaterTask = loop.create_task(db_updater())
    loop.create_task(crash_handler())

@bot.event
async def on_ready():
    print('Logged in as {0.user}'.format(bot))
    print('Admin:', await bot.fetch_user(int(config['adminId'])) if config['adminId'].isnumeric() else None, '\n')

@bot.command(help='Ping the bot for its status', brief='Ping')
async def ping(ctx):
    if not (pingTask.done() or updateTask.done() or dbUpdaterTask.done()):
        await ctx.send('MC Status Bot is running')
    else: await ctx.send('An error has occured in MC Status Bot (task(s) not running)')

@bot.command(hidden=True, help='Reload the bot\'s config file', brief='Reload config')
async def reload(ctx):
    global config

    if str(ctx.author.id) != config['adminId']:
        return
    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config))
    await ctx.send('Reloaded config')

@bot.command(hidden=True, help='Shutdown the bot', brief='Shutdown bot')
async def shutdown(ctx):
    if str(ctx.author.id) != config['adminId']:
        return
    await ctx.send('Shutting down...')
    loop.stop()
    with open('db.json', 'w') as file:
        file.write(json.dumps(guilds))

@bot.command(help='Add a server\'s status to the guild', brief='Add server')
async def add(ctx, address, name):
    global dbUpdate

    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return

    await lock.acquire(ctx.guild.id)
    if str(ctx.guild.id) in guilds.keys():
        for server in guilds[str(ctx.guild.id)]:
            if address == server['address']:
                await ctx.send('Address is already added')
                lock.release(ctx.guild.id)
                return
        if str(ctx.author.id) != config['adminId'] and len(guilds[str(ctx.guild.id)]) >= config['addressesPerGuild']:
            await ctx.send('Reached maximum amount of addresses in this guild')
            lock.release(ctx.guild.id)
            return
    else: guilds[str(ctx.guild.id)] = []

    try:
        if address not in servers.keys():
            servers[address] = {'lookup': await js.async_lookup(address), 'time': None, 'reply': None}
    except Exception as e: await ctx.send('Error: ' + str(e))
    else:
        try:
            newCat = await ctx.guild.create_category(name)
            statChan = await ctx.guild.create_voice_channel('Pinging...', category=newCat)
            await statChan.set_permissions(bot.user, connect=True)
            await statChan.set_permissions(ctx.guild.default_role, connect=False)
            if config['showPlayers']:
                playChan = await ctx.guild.create_text_channel('players', category=newCat)
                await playChan.set_permissions(bot.user, send_messages=True)
                await playChan.set_permissions(ctx.guild.default_role, send_messages=False)
                msg = await bot.get_channel(id=playChan.id).send('Pinging...')
        except Exception as e: await ctx.send('Error: ' + str(e))
        else:
            guilds[str(ctx.guild.id)].append({'address': address, 'category': newCat.id, 'statusChannel': statChan.id, 'playersChannel': (playChan.id if config['showPlayers'] else None), 'message': (msg.id if config['showPlayers'] else None)})
            if str(ctx.guild.id) not in lastUpdate.keys(): lastUpdate[str(ctx.guild.id)] = {}
            if address not in lastUpdate[str(ctx.guild.id)].keys(): lastUpdate[str(ctx.guild.id)][address] = {'statusTime': None, 'status': None, 'playersTime': None, 'players': None}
            await ctx.send('Added {}\'s status to this guild'.format(address))
            dbUpdate = True
    finally: lock.release(ctx.guild.id)
@add.error
async def add_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$add <address> <name>')

@bot.command(help='Remove a server\'s status from the guild', brief='Remove server')
async def rem(ctx, address):
    global dbUpdate

    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return

    await lock.acquire(ctx.guild.id)
    if str(ctx.guild.id) in guilds.keys() and len(guilds[str(ctx.guild.id)]):
        for c, server in enumerate(guilds[str(ctx.guild.id)]):
            if server['address'] == address:
                try:
                    if bot.get_channel(id=guilds[str(ctx.guild.id)][c]['statusChannel']) is not None:
                        await bot.get_channel(id=guilds[str(ctx.guild.id)][c]['statusChannel']).delete()
                    if bot.get_channel(id=guilds[str(ctx.guild.id)][c]['playersChannel']) is not None:
                        await bot.get_channel(id=guilds[str(ctx.guild.id)][c]['playersChannel']).delete()
                    if bot.get_channel(id=guilds[str(ctx.guild.id)][c]['category']) is not None:
                        await bot.get_channel(id=guilds[str(ctx.guild.id)][c]['category']).delete()
                except Exception as e: await ctx.send('Error: ' + str(e))
                
                guilds[str(ctx.guild.id)].pop(c)
                await ctx.send('Removed {}\'s status from this guild'.format(address))
                dbUpdate = True
                break
    lock.release(ctx.guild.id)
@rem.error
async def rem_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$rem <address>')

@bot.command(help='List all servers in the guild', brief='List servers')
async def list(ctx):
    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return

    await lock.acquire(ctx.guild.id)
    if str(ctx.guild.id) in guilds.keys():
        addresses = 'Addresses added to this guild:\n'
        for server in guilds[str(ctx.guild.id)]:
            addresses += server['address'] + '\n'
        await ctx.send(addresses)
    lock.release(ctx.guild.id)

async def ping():
    while True:
        for guild in guilds:
            for server in guilds[guild]:
                if servers[server['address']]['time'] is None or dt.now() - servers[server['address']]['time'] >= td(minutes=config['pingInterval']):
                    servers[server['address']]['time'] = dt.now()
                    try: servers[server['address']]['reply'] = await servers[server['address']]['lookup'].async_status()
                    except Exception: servers[server['address']]['reply'] = 'offline'
                await asyncio.sleep(0)
        await asyncio.sleep(1)

async def update():
    while True:
        for guild in guilds:
            for server in guilds[guild]:
                if servers[server['address']]['reply'] is None: continue
                try:
                    if lastUpdate[guild][server['address']]['statusTime'] is None \
                        or dt.now() - dt.fromisoformat(lastUpdate[guild][server['address']]['statusTime']) >= td(minutes=max(5, config['updateInterval'])):
                        if servers[server['address']]['reply'] != 'offline':
                            if servers[server['address']]['reply'].players.sample is not None:
                                status = '🟢 ONLINE: ' + str(servers[server['address']]['reply'].players.online) + ' / ' + str(servers[server['address']]['reply'].players.max)
                            else: status = '🟢 ONLINE: 0 / ' + str(servers[server['address']]['reply'].players.max)
                        else: status = '🔴 OFFLINE'
                        if status != lastUpdate[guild][server['address']]['status'] and bot.get_channel(id=server['statusChannel']) is not None:
                            lastUpdate[guild][server['address']]['statusTime'] = dt.isoformat(dt.now())
                            lastUpdate[guild][server['address']]['status'] = status
                            await bot.get_channel(id=server['statusChannel']).edit(name=status)

                    if config['showPlayers'] and server['message'] is not None and (lastUpdate[guild][server['address']]['playersTime'] is None \
                        or dt.now() - dt.fromisoformat(lastUpdate[guild][server['address']]['playersTime']) >= td(minutes=config['updateInterval'])):
                        if servers[server['address']]['reply'] != 'offline':
                            if servers[server['address']]['reply'].players.sample is not None:
                                players = 'Players:\n\n'
                                for player in servers[server['address']]['reply'].players.sample:
                                    players += player.name + '\n'
                            else: players = 'EMPTY'
                        else: players = 'OFFLINE'
                        if players != lastUpdate[guild][server['address']]['players'] \
                            and bot.get_channel(id=server['playersChannel']) is not None \
                            and bot.get_channel(id=server['playersChannel']).get_partial_message(server['message']) is not None:
                            lastUpdate[guild][server['address']]['playersTime'] = dt.isoformat(dt.now())
                            lastUpdate[guild][server['address']]['players'] = players
                            await bot.get_channel(id=server['playersChannel']).get_partial_message(server['message']).edit(content=players)
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
        await bot.start(config['token'])
    except Exception as e:
        print(e)
        loop.stop()
    
loop = asyncio.get_event_loop()
loop.create_task(init())
loop.run_forever()
