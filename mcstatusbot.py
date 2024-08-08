import discord
from discord.ext import commands
from discord import app_commands as app
from mcstatus.server import JavaServer as js
import asyncio
import os
import sys
import json
import logging
from datetime import datetime as dt, timedelta as td
from utils.keylock import keylock as kl
from utils.database import database


config = {'token': '<DISCORD BOT TOKEN>', 'adminId': '<DISCORD ID OF ADMIN>', 'updateInterval': 5, "updateDelays": {"day": 25, "week": 55}, 'serversPerGuild': 2, 'showPlayers': True, 'debug': False}

intents=discord.Intents.default()
# intents.message_content = True
bot = commands.AutoShardedBot('$', intents=intents, help_command=commands.DefaultHelpCommand(no_category='Commands'))

async def init():
    global db
    global tasks
    global lock
    lock = kl()

    await lock.acquire('master')
    loop.create_task(bot_login())

    await lock.acquire('master')
    print('--Initializing database')
    if database.updateDB('database.db'): print('  Updated database')
    db = database('database.db')
    print('  Initializing tasks')
    tasks = {tracker: loop.create_task(tracker()),
             bot_status: loop.create_task(bot_status()),
             cli: loop.create_task(cli())}
    loop.create_task(crash_handler())
    print('  Ready\n')
    lock.release('master')

@bot.hybrid_command(name='ping', help='Pings the bot', brief='Pings the bot')
async def com_ping(ctx:commands.Context):
    logging.info(f'{ctx.author} ran $ping in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    try: await ctx.send(f'Pong ({int(bot.latency*1000)}ms)', ephemeral=True)
    except Exception: pass

@bot.hybrid_group(name='admin', hidden=True)
async def grp_admin(ctx): pass

@grp_admin.command(name='status', help='Shows the status of the bot', brief='Shows bot status')
async def com_status(ctx:commands.Context):
    logging.info(f'{ctx.author} ran $admin status in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if str(ctx.author.id) != config['adminId']:
        logging.info(f'{ctx.author} is not an admin')
        return

    taskStatus = '\n'.join([f'❌ {func.__name__} task is not running' for func, task in tasks.items() if task.done()])
    try: await ctx.send(f'Bot status:\nIn {len(bot.guilds)} guild(s)\nWatching {db.countServers()} MC server(s)\
        \nLocks: {list(lock._keys.keys())}\n{taskStatus}', ephemeral=True)
    except Exception: pass

@bot.hybrid_command(name='add', help='Adds a server\'s status to the guild', brief='Adds a server')
async def com_add(ctx:commands.Context, address, name=None):
    logging.info(f'{ctx.author} ran $add {address} {name} in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if ctx.guild is None:
        logging.info(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.info(f'{ctx.author} does not have permission to manage channels')
        try: await ctx.send('You do not have permission to manage channels', ephemeral=True)
        except Exception: pass
        return
    
    if not await lock.acquire(ctx.guild.id): return
    if db.getGuildServers(ctx.guild.id, address):
        logging.info(f'{address} is already added in {ctx.guild} ({ctx.guild.id})')
        try: await ctx.send('Server is already added', ephemeral=True)
        except Exception: pass
        lock.release(ctx.guild.id)
        return
    if str(ctx.author.id) != config['adminId'] and db.countServers(ctx.guild.id) >= config['serversPerGuild']:
        logging.info(f'{ctx.guild} ({ctx.guild.id}) reached maximum amount of servers')
        try: await ctx.send('Reached maximum amount of servers in this guild', ephemeral=True)
        except Exception: pass
        lock.release(ctx.guild.id)
        return
    
    try:
        _ = await js.async_lookup(address)
        newCat = await ctx.guild.create_category(name if name is not None else address)
        await newCat.set_permissions(bot.user, send_messages=True, connect=True)
        await newCat.set_permissions(ctx.guild.default_role, send_messages=False, connect=False)
        statChan = await ctx.guild.create_voice_channel('Pinging...', category=newCat)
        if config['showPlayers']:
            # playChan = await ctx.guild.create_text_channel('players', category=newCat)
            playChan = statChan
            msg = await playChan.send('Pinging...')
    except Exception as e:
        # if not isinstance(e, discord.DiscordException): logging.warning(f'Error looking up {address}: {str(e)}')
        logging.debug(f'Error adding {address} to {ctx.guild} ({ctx.guild.id}): {str(e)}')
        try: await ctx.send('Error: ' + str(e), ephemeral=True)
        except Exception: pass
    else:
        db.addServer(guildId=ctx.guild.id, address=address, categoryId=newCat.id, statusChannelId=statChan.id, playersChannelId=(playChan.id if config['showPlayers'] else None), messageId=(msg.id if config['showPlayers'] else None))
        logging.debug(f'Added {db.getGuildServers(ctx.guild.id, address)}')
        logging.info(f'Added {address} to {ctx.guild} ({ctx.guild.id})')
        try: await ctx.send(f'Added {address}\'s status to this guild', ephemeral=True)
        except Exception: pass
    lock.release(ctx.guild.id)
@com_add.error
async def com_add_error(ctx:commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        try: await ctx.send('Invalid arguments\n$add <address> <name>')
        except Exception: pass

@bot.hybrid_command(name='rem', help='Removes a server\'s status from the guild', brief='Removes a server')
async def com_rem(ctx:commands.Context, address):
    logging.info(f'{ctx.author} ran $rem {address} in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if ctx.guild is None:
        logging.info(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.info(f'{ctx.author} does not have permission to manage channels')
        try: await ctx.send('You do not have permission to manage channels', ephemeral=True)
        except Exception: pass
        return
    
    if not await lock.acquire(ctx.guild.id): return
    if db.getGuildServers(ctx.guild.id, address):
        try:
            server = db.getGuildServers(ctx.guild.id, address)
            if bot.get_channel(server['statusChannelId']):
                await bot.get_channel(server['statusChannelId']).delete()
            if bot.get_channel(server['playersChannelId']):
                await bot.get_channel(server['playersChannelId']).delete()
            if bot.get_channel(server['categoryId']):
                await bot.get_channel(server['categoryId']).delete()
        except Exception as e: logging.debug(f'Error deleting channels in {ctx.guild} ({ctx.guild.id}): {str(e)}')
        db.removeServers(ctx.guild.id, address)
        logging.debug(f'Removed {server}')
        logging.info(f'Removed {address} from {ctx.guild} ({ctx.guild.id})')
        try: await ctx.send(f'Removed {address}\'s status from this guild', ephemeral=True)
        except Exception: pass
    else:
        logging.info(f'{address} does not exist in {ctx.guild} ({ctx.guild.id})')
        try: await ctx.send('This server does not exist', ephemeral=True)
        except Exception: pass
    lock.release(ctx.guild.id)
@com_rem.error
async def com_rem_error(ctx:commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        try: await ctx.send('Invalid arguments\n$rem <address>')
        except Exception: pass
@com_rem.autocomplete('address')
async def com_rem_autocomplete(interaction:discord.Interaction, current:str) -> list[app.Choice[str]]:
    if interaction.guild is None:
        return [app.Choice(name='Not available in DMs', value='')]
    if str(interaction.user.id) != config['adminId'] and not interaction.user.guild_permissions.manage_channels:
        return [app.Choice(name='Insufficient permissions', value='')]
    addresses = [server['address'] for server in db.getGuildServers(interaction.guild.id)]
    return [app.Choice(name=address, value=address) for address in addresses if current.lower() in address.lower()]

@bot.hybrid_command(name='list', help='Lists all servers in the guild', brief='Lists servers')
async def com_list(ctx:commands.Context):
    logging.info(f'{ctx.author} ran $list in {ctx.guild or "DM"} ({ctx.guild.id if ctx.guild is not None else ""})')
    if ctx.guild is None:
        logging.info(f'{ctx.author} is in a DM channel')
        return
    if str(ctx.author.id) != config['adminId'] and not ctx.author.guild_permissions.manage_channels:
        logging.info(f'{ctx.author} does not have permission to manage channels')
        try: await ctx.send('You do not have permission to manage channels', ephemeral=True)
        except Exception: pass
        return
    
    if not await lock.acquire(ctx.guild.id): return
    addresses = 'Servers added to this guild:\n'
    for server in db.getGuildServers(ctx.guild.id):
        addresses += server['address'] + '\n'
    try: await ctx.send(addresses, ephemeral=True)
    except Exception: pass
    lock.release(ctx.guild.id)

# @bot.event
# async def on_guild_channel_delete(channel:discord.VoiceChannel):
#     address = db.removeServers(channel.guild.id, statusChannelId=channel.id)
#     if address: logging.info(f'Removed {address} from {channel.guild} ({channel.guild.id}): Status channel deleted')

@bot.event
async def on_guild_join(guild:discord.Guild):
    logging.info(f'Joined {guild} ({guild.id})')

@bot.event
async def on_guild_remove(guild:discord.Guild):
    logging.info(f'Left {guild} ({guild.id})')
    addresses = db.removeServers(guild.id)
    if addresses: logging.info(f'Removed {addresses} from {guild} ({guild.id})')

async def tracker():
    while True:
        for guild in bot.guilds:
            for server in db.getGuildServers(guild.id):
                await asyncio.sleep(0)
                if not bot.get_channel(server['statusChannelId']): continue
                interval = td(minutes=max(config['updateInterval'], 5.1))
                if server['statusTime'] is not None:
                    statusTime = dt.fromisoformat(server['statusTime'])
                    if dt.now() - statusTime >= td(days=7): interval += td(minutes=config['updateDelays']['week'])
                    elif dt.now() - statusTime >= td(days=1): interval += td(minutes=config['updateDelays']['day'])
                if server['pingTime'] is None or dt.now() - dt.fromisoformat(server['pingTime']) >= interval:
                    logging.debug(f'Determined interval of {server["address"]} in {guild} ({guild.id}): {interval}')
                    loop.create_task(update(guild, server))
            await asyncio.sleep(0)
        await asyncio.sleep(1)

async def update(guild:discord.Guild, server):
    await lock.acquire(f'{guild.id}:{server['address']}')
    db.pingServer(guild.id, server['address'])
    try:
        lookup = await js.async_lookup(server['address'])
        logging.debug(f'Looked up {server["address"]} in {guild} ({guild.id})')
    except Exception as e:
        logging.warning(f'Error looking up {server["address"]} in {guild} ({guild.id}): {str(e)}')
        lock.release(f'{guild.id}:{server['address']}')
        return
    else:
        try: reply = await lookup.async_status()
        except Exception: reply = None
        logging.debug(f'Pinged {server["address"]} in {guild} ({guild.id}): {"ONLINE" if reply else "OFFLINE"}')
    
    try:
        if reply is not None:
            status = '🟢 ONLINE: ' + str(reply.players.online) + ' / ' + str(reply.players.max)
        else: status = '🔴 OFFLINE'
        if status != server['status']:
            await bot.get_channel(server['statusChannelId']).edit(name=status)
            db.updateServerStatus(guild.id, server['address'], status)
            logging.debug(f'Updated status channel of {server["address"]} in {guild} ({guild.id}): {status}')
    except Exception as e: logging.debug(f'Error updating status of {server["address"]} in {guild} ({guild.id}): {str(e)}')
    
    try:
        if config['showPlayers']:
            msg = [playChan.get_partial_message(server['messageId']) if playChan else None for playChan in [bot.get_channel(server['playersChannelId'])]][0]
            if msg is None:
                lock.release(f'{guild.id}:{server['address']}')
                return
            if reply is not None:
                players = '-===ONLINE===-'
                if reply.players.sample is not None:
                    for player in reply.players.sample:
                        players += '\n' + player.name
            else: players = '-===OFFLINE===-'
            if players != server['players']:
                await msg.edit(content=players)
                db.updateServerPlayers(guild.id, server['address'], players)
                logging.debug(f'Updated players message of {server["address"]} in {guild} ({guild.id}): {players}')
    except Exception as e: logging.debug(f'Error updating players of {server["address"]} in {guild} ({guild.id}): {str(e)}')
    lock.release(f'{guild.id}:{server['address']}')

async def bot_login():
    if not config['token'].startswith('//'):
        try:
            await bot.start(config['token'])
        except Exception as e:
            logging.error(f'Error logging in: {str(e)}')
            print(f'  Error logging in: {str(e)}')
            await bot.close()
            loop.stop()
    else: lock.release('master')

@bot.event
async def on_connect():
    logging.info('Connecting')
    print('\r--Connecting')
    await bot.tree.sync()

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    print(f'  Logged in as {bot.user}')
    print('  Admin:', await bot.fetch_user(int(config['adminId'])) if config['adminId'].isnumeric() else None, '\n')
    lock.release('master')

async def bot_status():
    num = None
    while True:
        if bot.is_ready() and (num is None or db.countServers() != num):
            num = db.countServers()
            try:
                await bot.change_presence(activity=discord.Activity(name=f'{num if num > 1 else ""} MC servers', type=discord.ActivityType.watching))
                logging.info(f'Updated bot status ({num})')
            except Exception as e: logging.warning(f'Error updating bot status ({num}): {str(e)}')
        await asyncio.sleep(3600)

async def cli():
    while True:
        print('\r> ', end='')
        command = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        command = command.strip()

        match command:
            case 'export':
                if not os.path.exists('./export/'):
                    os.mkdir('./export/')
                with open('./export/bot.guilds.json', 'w') as file:
                    file.write(json.dumps(dict((guild.id, str(guild)) for guild in bot.guilds), indent=4))
                with open('./export/db.guildServers.json', 'w') as file:
                    file.write(json.dumps(db.getGuildServers(), indent=4))
                logging.info('Exported database')
                print('  Exported database')
            
            case 'reload':
                global config
                if os.path.exists('config.json'):
                    with open('config.json', 'r') as file:
                        tempConfig = json.loads(file.read())
                    if list(config) != list(tempConfig):
                        os.replace('config.json', 'config.json.old')
                        with open('config.json', 'w') as file:
                            file.write(json.dumps(config, indent=4))
                    else: config = tempConfig
                else:
                    with open('config.json', 'w') as file:
                        file.write(json.dumps(config, indent=4))
                logging.info('Reloaded config')
                print('  Reloaded config')
            
            case 'shutdown':
                print('  Shutting down')
                logging.info('Shutting down...')
                await lock.close()
                try: await bot.close()
                except Exception: pass
                db.close()
                loop.stop()
                return
            
            case 'help':
                print('  Commands: export reload shutdown')
        
        if command.startswith('py '):
            try: exec(command[3:])
            except Exception as e: print(f'  Error: {e}')

async def crash_handler():
    while True:
        await asyncio.sleep(10)
        for method, task in tasks.items():
            if task.done():
                lock.reset()
                tasks[method] = loop.create_task(method())
                logging.error(f'{method.__name__} task has crashed and been restarted')
                print(f'\r--Restarted task: {method.__name__}')

if __name__ == '__main__':
    if os.path.exists('config.json'):
        with open('config.json', 'r') as file:
            tempConfig = json.loads(file.read())
        if list(config) != list(tempConfig):
            os.replace('config.json', 'config.json.old')
            with open('config.json', 'w') as file:
                file.write(json.dumps(config, indent=4))
        else: config = tempConfig
    else:
        with open('config.json', 'w') as file:
            file.write(json.dumps(config, indent=4))

    if not os.path.exists('./logs/'): os.mkdir('./logs/')
    logging.basicConfig(filename=f'./logs/{str(dt.date(dt.now()))}.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO if not config['debug'] else logging.DEBUG)
    logging.info('====================BEGIN====================')

    loop = asyncio.new_event_loop()
    loop.create_task(init())
    loop.run_forever()

    logging.info('=====================END=====================')
