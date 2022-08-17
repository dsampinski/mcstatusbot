import discord
from discord.ext import commands
from mcstatus.server import JavaServer as js
import asyncio
import os
import json
from datetime import datetime as dt, timedelta as td
from utils.keylock import keylock as kl
from utils.database import upgradeDB, database
import logging

intents=discord.Intents.default()
intents.message_content = True
bot = commands.Bot('$', intents=intents)
config = {'token': '<DISCORD BOT TOKEN>', 'adminId': '<DISCORD ID OF ADMIN>', 'pingInterval': 1, 'updateInterval': 1, 'serversPerGuild': 2, 'showPlayers': True}
if not os.path.exists('./logs/'): os.mkdir('./logs/')
logging.basicConfig(filename=f'./logs/{str(dt.date(dt.now()))}.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
logging.info('====================BEGIN====================')

async def init():
    global config
    global db
    global servers
    global tasks
    global lock
    lock = kl()

    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))
    
    await lock.acquire('master')
    print('--Logging in')
    loop.create_task(bot_login(config['token']))

    await lock.acquire('master')
    print('--Initializing database')
    upgradeDB('database.db')
    db = database('database.db')
    print('  Initializing servers')
    servers = dict.fromkeys(db.getServers(addressOnly=True))
    for address in servers:
        try: servers[address] = {'lookup': await js.async_lookup(address), 'time': None, 'reply': None}
        except Exception as e: logging.info(f'Error initializing {address}: {str(e)}')
    print('  Initializing tasks')
    tasks = {}
    tasks[ping] = loop.create_task(ping())
    tasks[update] = loop.create_task(update())
    tasks[bot_status] = loop.create_task(bot_status())
    loop.create_task(crash_handler(tasks))
    print('  Ready\n')
    lock.release('master')

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    print(f'  Logged in as {bot.user}')
    print('  Admin:', await bot.fetch_user(int(config['adminId'])) if config['adminId'].isnumeric() else None, '\n')
    lock.release('master')

@bot.command(name='ping', help='Pings the bot', brief='Pings the bot')
async def com_ping(ctx):
    logging.info(f'{ctx.author} ran $ping in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    await ctx.send('Pong')

@bot.command(name='info', help='Shows info about the bot', brief='Shows bot info')
async def com_info(ctx):
    logging.info(f'{ctx.author} ran $info in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    await ctx.send('MC Status Bot by GitHub@dsampinski to display Minecraft servers\' statuses\n\
                    https://github.com/dsampinski/mcstatusbot')

@bot.group(name='admin', hidden=True)
async def grp_admin(ctx): pass

@grp_admin.command(name='status', help='Shows the status of the bot', brief='Shows bot status')
async def com_status(ctx):
    logging.info(f'{ctx.author} ran $admin status in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if str(ctx.author.id) != config['adminId']:
        logging.debug(f'{ctx.author} is not an admin')
        return

    taskStatus = 'All tasks are running'
    for task in tasks.values():
        if task.done(): taskStatus = 'Task(s) not running'
    await ctx.send(f'Bot status:\nCurrently in {len(bot.guilds)} guild(s)\nWatching {len(servers)} Minecraft server(s)\n{taskStatus}')
    

@grp_admin.command(name='export', help='Exports the database as JSON to the filesystem', brief='Exports database')
async def com_export(ctx):
    logging.info(f'{ctx.author} ran $admin export in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if str(ctx.author.id) != config['adminId']:
        logging.debug(f'{ctx.author} is not an admin')
        return
    
    if not os.path.exists('./export/'):
        os.mkdir('./export/')
    with open('./export/bot.guilds.json', 'w') as file:
        file.write(json.dumps(dict((guild.id, str(guild)) for guild in bot.guilds), indent=4))
    with open('./export/db.guildServers.json', 'w') as file:
        file.write(json.dumps(db.getGuildServers(), indent=4))
    logging.info('Exported database')
    await ctx.send('Exported database')

@grp_admin.command(name='reload', help='Reloads the bot\'s config file', brief='Reloads config')
async def com_reload(ctx):
    logging.info(f'{ctx.author} ran $admin reload in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    global config
    if str(ctx.author.id) != config['adminId']:
        logging.debug(f'{ctx.author} is not an admin')
        return
    
    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            config = json.loads(file.read())
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))
    logging.info('Reloaded config')
    await ctx.send('Reloaded config')

@grp_admin.command(name='shutdown', help='Shuts down the bot', brief='Shuts down bot')
async def com_shutdown(ctx):
    logging.info(f'{ctx.author} ran $admin shutdown in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if str(ctx.author.id) != config['adminId']:
        logging.debug(f'{ctx.author} is not an admin')
        return
    
    logging.info('Shutting down...')
    await ctx.send('Shutting down...')
    await lock.close()
    await bot.close()
    db.close()
    loop.stop()

@bot.command(name='add', help='Adds a server\'s status to the guild', brief='Adds a server')
async def com_add(ctx, address, name):
    logging.info(f'{ctx.author} ran $add {address} {name} in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if not isinstance(ctx.author, discord.member.Member):
        logging.debug(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.debug(f'{ctx.author} does not have permission to manage channels')
        await ctx.send('You do not have permission to manage channels')
        return
    
    if not await lock.acquire(ctx.guild.id): return
    if db.getGuildServers(ctx.guild.id, address) is not None:
        logging.debug(f'{address} is already added in {ctx.guild} ({ctx.guild.id})')
        await ctx.send('Server is already added')
        lock.release(ctx.guild.id)
        return
    if str(ctx.author.id) != config['adminId'] and len(db.getGuildServers(ctx.guild.id)) >= config['serversPerGuild']:
        logging.debug(f'{ctx.guild} ({ctx.guild.id}) reached maximum amount of servers')
        await ctx.send('Reached maximum amount of servers in this guild')
        lock.release(ctx.guild.id)
        return
    
    try:
        await lock.acquire(address)
        if address not in servers:
            servers[address] = {'lookup': await js.async_lookup(address), 'time': None, 'reply': None}
        lock.release(address)
    except Exception as e:
        lock.release(address)
        logging.debug(f'Error adding {address} to {ctx.guild} ({ctx.guild.id}): {str(e)}')
        await ctx.send('Error: ' + str(e))
    else:
        try:
            newCat = await ctx.guild.create_category(name)
            await newCat.set_permissions(bot.user, send_messages=True, connect=True)
            await newCat.set_permissions(ctx.guild.default_role, send_messages=False, connect=False)
            statChan = await ctx.guild.create_voice_channel('Pinging...', category=newCat)
            if config['showPlayers']:
                # playChan = await ctx.guild.create_text_channel('players', category=newCat)
                playChan = statChan
                msg = await playChan.send('Pinging...')
        except Exception as e:
            logging.debug(f'Error creating channels in {ctx.guild} ({ctx.guild.id}): {str(e)}')
            await ctx.send('Error: ' + str(e))
        else:
            db.addServer(guild_id=ctx.guild.id, address=address, category=newCat.id, statusChannel=statChan.id, playersChannel=(playChan.id if config['showPlayers'] else None), message=(msg.id if config['showPlayers'] else None))
            logging.debug(f'Added {db.getGuildServers(ctx.guild.id, address)}')
            logging.info(f'Added {address} to {ctx.guild} ({ctx.guild.id})')
            await ctx.send('Added {}\'s status to this guild'.format(address))
    lock.release(ctx.guild.id)
@com_add.error
async def com_add_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$add <address> <name>')

@bot.command(name='rem', help='Removes a server\'s status from the guild', brief='Removes a server')
async def com_rem(ctx, address):
    logging.info(f'{ctx.author} ran $rem {address} in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if not isinstance(ctx.author, discord.member.Member):
        logging.debug(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.debug(f'{ctx.author} does not have permission to manage channels')
        await ctx.send('You do not have permission to manage channels')
        return
    
    if not await lock.acquire(ctx.guild.id): return
    if db.getGuildServers(ctx.guild.id, address) is not None:
        try:
            server = db.getGuildServers(ctx.guild.id, address)
            if bot.get_channel(server['statusChannel']) is not None:
                await bot.get_channel(server['statusChannel']).delete()
            if bot.get_channel(server['playersChannel']) is not None:
                await bot.get_channel(server['playersChannel']).delete()
            if bot.get_channel(server['category']) is not None:
                await bot.get_channel(server['category']).delete()
        except Exception as e:
            logging.debug(f'Error deleting channels in {ctx.guild} ({ctx.guild.id}): {str(e)}')
            await ctx.send('Error: ' + str(e))

        db.removeServers(ctx.guild.id, address)
        await lock.acquire(address)
        if not db.getServers(address):
            servers.pop(address)
        lock.release(address)
        logging.debug(f'Removed {server}')
        logging.info(f'Removed {address} from {ctx.guild} ({ctx.guild.id})')
        await ctx.send('Removed {}\'s status from this guild'.format(address))
        lock.release(ctx.guild.id)
        return
    logging.debug(f'{address} does not exist in {ctx.guild} ({ctx.guild.id})')
    await ctx.send('This server does not exist')
    lock.release(ctx.guild.id)
@com_rem.error
async def com_rem_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Invalid arguments\n$rem <address>')

@bot.command(name='list', help='Lists all servers in the guild', brief='Lists servers')
async def com_list(ctx):
    logging.info(f'{ctx.author} ran $list in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if not isinstance(ctx.author, discord.member.Member):
        logging.debug(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.debug(f'{ctx.author} does not have permission to manage channels')
        await ctx.send('You do not have permission to manage channels')
        return
    
    if not await lock.acquire(ctx.guild.id): return
    addresses = 'Servers added to this guild:\n'
    for server in db.getGuildServers(ctx.guild.id):
        addresses += server['address'] + '\n'
    await ctx.send(addresses)
    lock.release(ctx.guild.id)

@bot.event
async def on_guild_join(guild):
    logging.info(f'Joined {guild} ({guild.id})')

@bot.event
async def on_guild_remove(guild):
    logging.info(f'Left {guild} ({guild.id})')
    await lock.acquire(guild.id)
    addresses = db.removeServers(guild.id)
    lock.release(guild.id)
    for address in addresses:
        await lock.acquire(address)
        if not db.getServers(address):
            servers.pop(address)
        lock.release(address)

async def ping():
    while True:
        for address, server in list(servers.items()):
            if server['time'] is None or dt.utcnow() - server['time'] >= td(minutes=config['pingInterval']):
                server['time'] = dt.utcnow()
                try: server['reply'] = await server['lookup'].async_status()
                except Exception: server['reply'] = 'offline'
                logging.debug(f'Pinged {address}')
            await asyncio.sleep(0)
        await asyncio.sleep(1)

async def update():
    while True:
        for guild in bot.guilds:
            for server in db.getGuildServers(guild.id):
                if server['address'] not in servers or servers[server['address']]['reply'] is None: continue
                srv = servers[server['address']]
                try:
                    if server['statusTime'] is None \
                        or dt.utcnow() - dt.fromisoformat(server['statusTime']) >= td(minutes=max(6, config['updateInterval'])):
                        if srv['reply'] != 'offline':
                            status = '🟢 ONLINE: ' + str(srv['reply'].players.online) + ' / ' + str(srv['reply'].players.max)
                        else: status = '🔴 OFFLINE'
                        statChan = bot.get_channel(server['statusChannel'])
                        if status != server['status'] and statChan is not None:
                            db.updateServerStatus(guild.id, server['address'], status)
                            await statChan.edit(name=status)
                            logging.debug(f'Updated status channel of {server["address"]} in {guild} ({guild.id})')
                    
                    if config['showPlayers'] and (server['playersTime'] is None \
                        or dt.utcnow() - dt.fromisoformat(server['playersTime']) >= td(minutes=config['updateInterval'])):
                        if srv['reply'] != 'offline':
                            players = '-===ONLINE===-\n'
                            if srv['reply'].players.sample is not None:
                                for player in srv['reply'].players.sample:
                                    players += player.name + '\n'
                        else: players = '-===OFFLINE===-'
                        msg = [playChan.get_partial_message(server['message']) if playChan else None for playChan in [bot.get_channel(server['playersChannel'])]][0]
                        if players != server['players'] and msg is not None:
                            db.updateServerPlayers(guild.id, server['address'], players)
                            await msg.edit(content=players)
                            logging.debug(f'Updated players message of {server["address"]} in {guild} ({guild.id})')
                except Exception as e:
                    logging.info(f'Error updating status of {server["address"]} in {guild} ({guild.id}): {str(e)}')
                await asyncio.sleep(0)
            await asyncio.sleep(0)
        await asyncio.sleep(1)

async def bot_login(token):
    try:
        await bot.start(token)
    except Exception as e:
        logging.error(f'Error logging in: {str(e)}')
        print('  ' + str(e))
        await bot.close()
        loop.stop()

async def bot_status():
    num = None
    while True:
        if bot.is_ready() and (num is None or len(servers) != num):
            num = len(servers)
            try:
                await bot.change_presence(activity=discord.Activity(name=f'{num if num > 1 else ""} MC servers | $info', type=discord.ActivityType.watching))
                logging.info('Updated bot status')
            except Exception as e: logging.info(f'Error updating bot status: {str(e)}')
        await asyncio.sleep(3600)

async def crash_handler(tasks):
    while True:
        await asyncio.sleep(10)
        for method, task in tasks.items():
            if task.done():
                lock.reset()
                tasks[method] = loop.create_task(method())
                logging.warning(f'{method.__name__} task has crashed and been restarted')
                print(f'--Restarted task: {method.__name__}')

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(init())
loop.run_forever()

logging.info('=====================END=====================')
