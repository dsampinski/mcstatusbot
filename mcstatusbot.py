import discord
from discord.ext import commands
from mcstatus.server import JavaServer as js
import asyncio
import os
import json
from datetime import datetime as dt, timedelta as td
from utils.keylock import keylock as kl
from utils.cache import cache as c
from utils.database import database

bot = commands.Bot('$')
config = {'token': '<DISCORD BOT TOKEN>', 'adminId': '<DISCORD ID OF ADMIN>', 'pingInterval': 1, 'updateInterval': 1, 'addressesPerGuild': 2, 'showPlayers': True}

async def init():
    global config
    global db
    global servers
    global tasks
    global lock
    global cache

    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))
    
    if not bot.is_ready():
        lock = kl()
        await lock.acquire('init')
        loop.create_task(bot_login(config['token']))

    await lock.acquire('init')
    print('--Initializing database')
    db = database('database.db')
    print('  Initializing servers')
    srv_addresses = db.getServers(addressOnly=True)
    servers = dict.fromkeys(srv_addresses)
    for address in srv_addresses:
        try: servers[address] = {'lookup': await js.async_lookup(address), 'time': None, 'reply': None}
        except Exception as e: print(e)
    print('  Initializing cache')
    cache = c()
    cache.Updates.build(db.getGuildServers())
    print('  Initializing tasks')
    tasks = {}
    tasks[ping] = loop.create_task(ping())
    tasks[update] = loop.create_task(update())
    loop.create_task(crash_handler(tasks))
    print('  Ready\n')
    lock.release('init')

@bot.event
async def on_ready():
    print('--Logged in as {0.user}'.format(bot))
    print('  Admin:', await bot.fetch_user(int(config['adminId'])) if config['adminId'].isnumeric() else None, '\n')
    await bot.change_presence(activity=discord.Activity(name='$help', type=discord.ActivityType.listening))
    lock.release('init')

@bot.command(name='ping', help='Pings the bot', brief='Pings the bot')
async def com_ping(ctx):
    for task in tasks.values():
        if task.done(): return
    await ctx.send('Pong')

@bot.command(name='info', help='Shows info about the bot', brief='Shows bot info')
async def com_info(ctx):
    await ctx.send('MC Status Bot by GitHub@dsampinski to display Minecraft servers\' statuses\n\
                    https://github.com/dsampinski/mcstatusbot')

@bot.group(name='admin', hidden=True)
async def grp_admin(ctx): pass

@grp_admin.command(name='export', help='Exports the database and cache as JSON to the filesystem')
async def com_export(ctx):
    if str(ctx.author.id) != config['adminId']:
        return
    
    if not os.path.exists('./export/'):
        os.mkdir('./export/')
    with open('./export/bot.guilds.json', 'w') as file:
        file.write(json.dumps(dict((guild.id, str(guild)) for guild in bot.guilds), indent=4))
    with open('./export/db.guildServers.json', 'w') as file:
        file.write(json.dumps(db.getGuildServers(), indent=4))
    with open('./export/cache.updates.json', 'w') as file:
        file.write(json.dumps(cache.Updates.updates, indent=4))
    await ctx.send('Exported database and cache')

@grp_admin.command(name='reload', help='Reloads the bot\'s config file')
async def com_reload(ctx):
    global config
    if str(ctx.author.id) != config['adminId']:
        return
    
    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))
    await ctx.send('Reloaded config')

@grp_admin.command(name='shutdown', help='Shuts down the bot')
async def com_shutdown(ctx):
    if str(ctx.author.id) != config['adminId']:
        return
    
    await ctx.send('Shutting down...')
    await lock.close()
    await bot.close()
    db.close()
    loop.stop()

@bot.command(name='add', help='Adds a server\'s status to the guild', brief='Adds a server')
async def com_add(ctx, address, name):
    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return
    
    await lock.acquire(ctx.guild.id)
    if db.getGuildServers(ctx.guild.id, address) is not None:
        await ctx.send('Address is already added')
        lock.release(ctx.guild.id)
        return
    if str(ctx.author.id) != config['adminId'] and len(db.getGuildServers(ctx.guild.id)) >= config['addressesPerGuild']:
        await ctx.send('Reached maximum amount of addresses in this guild')
        lock.release(ctx.guild.id)
        return
    
    try:
        if address not in servers:
            servers[address] = {'lookup': await js.async_lookup(address), 'time': None, 'reply': None}
    except Exception as e: await ctx.send('Error: ' + str(e))
    else:
        try:
            newCat = await ctx.guild.create_category(name)
            await newCat.set_permissions(bot.user, send_messages=True, connect=True)
            await newCat.set_permissions(ctx.guild.default_role, send_messages=False, connect=False)
            statChan = await ctx.guild.create_voice_channel('Pinging...', category=newCat, sync=True)
            if config['showPlayers']:
                playChan = await ctx.guild.create_text_channel('players', category=newCat, sync=True)
                msg = await bot.get_channel(id=playChan.id).send('Pinging...')
        except Exception as e: await ctx.send('Error: ' + str(e))
        else:
            db.addServer(guild_id=ctx.guild.id, address=address, category=newCat.id, statusChannel=statChan.id, playersChannel=(playChan.id if config['showPlayers'] else None), message=(msg.id if config['showPlayers'] else None))
            cache.Updates.add(ctx.guild.id, address)
            await ctx.send('Added {}\'s status to this guild'.format(address))
    finally: lock.release(ctx.guild.id)
@com_add.error
async def com_add_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$add <address> <name>')

@bot.command(name='rem', help='Removes a server\'s status from the guild', brief='Removes a server')
async def com_rem(ctx, address):
    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return
    
    await lock.acquire(ctx.guild.id)
    if db.getGuildServers(ctx.guild.id, address) is not None:
        try:
            server = db.getGuildServers(ctx.guild.id, address)
            if bot.get_channel(id=server['statusChannel']) is not None:
                await bot.get_channel(id=server['statusChannel']).delete()
            if bot.get_channel(id=server['playersChannel']) is not None:
                await bot.get_channel(id=server['playersChannel']).delete()
            if bot.get_channel(id=server['category']) is not None:
                await bot.get_channel(id=server['category']).delete()
        except Exception as e: await ctx.send('Error: ' + str(e))

        db.removeServer(ctx.guild.id, address)
        await ctx.send('Removed {}\'s status from this guild'.format(address))
        lock.release(ctx.guild.id)
        return
    await ctx.send('This server does not exist')
    lock.release(ctx.guild.id)
@com_rem.error
async def com_rem_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$rem <address>')

@bot.command(name='list', help='Lists all servers in the guild', brief='Lists servers')
async def com_list(ctx):
    if not isinstance(ctx.author, discord.member.Member):
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        await ctx.send('Not enough permissions')
        return
    
    await lock.acquire(ctx.guild.id)
    addresses = 'Addresses added to this guild:\n'
    for server in db.getGuildServers(ctx.guild.id):
        addresses += server['address'] + '\n'
    await ctx.send(addresses)
    lock.release(ctx.guild.id)

async def ping():
    while True:
        for server in servers.values():
            if server['time'] is None or dt.now() - server['time'] >= td(minutes=config['pingInterval']):
                server['time'] = dt.now()
                try: server['reply'] = await server['lookup'].async_status()
                except Exception: server['reply'] = 'offline'
            await asyncio.sleep(0)
        await asyncio.sleep(1)

async def update():
    while True:
        for guild in bot.guilds:
            writeCache = False
            for server in db.getGuildServers(guild.id):
                if server['address'] not in servers or servers[server['address']]['reply'] is None: continue
                try:
                    if cache.Updates.updates[guild.id][server['address']]['statusTime'] is None \
                        or dt.now() - dt.fromisoformat(cache.Updates.updates[guild.id][server['address']]['statusTime']) >= td(minutes=max(5, config['updateInterval'])):
                        if servers[server['address']]['reply'] != 'offline':
                            if servers[server['address']]['reply'].players.sample is not None:
                                status = '🟢 ONLINE: ' + str(servers[server['address']]['reply'].players.online) + ' / ' + str(servers[server['address']]['reply'].players.max)
                            else: status = '🟢 ONLINE: 0 / ' + str(servers[server['address']]['reply'].players.max)
                        else: status = '🔴 OFFLINE'
                        if status != cache.Updates.updates[guild.id][server['address']]['status'] and bot.get_channel(id=server['statusChannel']) is not None:
                            cache.Updates.updates[guild.id][server['address']]['statusTime'] = dt.isoformat(dt.now())
                            cache.Updates.updates[guild.id][server['address']]['status'] = status
                            await bot.get_channel(id=server['statusChannel']).edit(name=status)
                            writeCache = True
                    
                    if config['showPlayers'] and (cache.Updates.updates[guild.id][server['address']]['playersTime'] is None \
                        or dt.now() - dt.fromisoformat(cache.Updates.updates[guild.id][server['address']]['playersTime']) >= td(minutes=config['updateInterval'])):
                        if servers[server['address']]['reply'] != 'offline':
                            if servers[server['address']]['reply'].players.sample is not None:
                                players = 'Players:\n\n'
                                for player in servers[server['address']]['reply'].players.sample:
                                    players += player.name + '\n'
                            else: players = 'EMPTY'
                        else: players = 'OFFLINE'
                        if players != cache.Updates.updates[guild.id][server['address']]['players'] \
                            and bot.get_channel(id=server['playersChannel']) is not None \
                            and bot.get_channel(id=server['playersChannel']).get_partial_message(server['message']) is not None:
                            cache.Updates.updates[guild.id][server['address']]['playersTime'] = dt.isoformat(dt.now())
                            cache.Updates.updates[guild.id][server['address']]['players'] = players
                            await bot.get_channel(id=server['playersChannel']).get_partial_message(server['message']).edit(content=players)
                            writeCache = True
                except Exception as e: print(e)
                await asyncio.sleep(0)
            await asyncio.sleep(0)
            if writeCache: cache.Updates.write(guild.id)
        await asyncio.sleep(1)

async def crash_handler(tasks):
    while True:
        await asyncio.sleep(10)
        for method, task in tasks.items():
            if task.done():
                lock.reset()
                cache.reset()
                cache.Updates.build(db.getGuildServers())
                tasks[method] = loop.create_task(method())
                print('--Restarted task: {}'.format(method.__name__))

async def bot_login(token):
    try:
        await bot.start(token)
    except Exception as e:
        print(e)
        await bot.close()
        loop.stop()

loop = bot.loop
loop.create_task(init())
loop.run_forever()
