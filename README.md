# MC Status Bot
A simple Python Discord bot that displays Minecraft servers' statuses and players

You can [add the public bot to your Discord](https://discord.com/oauth2/authorize?client_id=1001671313393463358&permissions=268435472&scope=bot)

# Setup
    Git and Python 3.8+ are required

`git clone https://github.com/dsampinski/mcstatusbot.git && cd mcstatusbot`

`pip install -U -r requirements.txt`

## Run
`python mcstatusbot.py`

# Config
> token

The bot's [token](https://www.writebots.com/discord-bot-token/)

> adminId

The Discord ID of the bot's admin (to bypass restrictions)

> pingInterval

Interval (in minutes) between each server ping

> updateInterval

Interval (in minutes) between each status update

> serversPerGuild

Maximum amount of servers that can be added per guild (bypassed by the bot's admin)

> showPlayers

Whether to show the players list or not

# Slash Commands
## Everyone
> /ping

Pings the bot

## Users with permission to manage channels
> /add *address name*

Adds a server's status to the guild

> /rem *address*

Removes a server's status from the guild

> /list

Lists all servers in the guild

## Bot admin
> /admin reload

Reloads the bot's config file

> /admin shutdown

Shuts down the bot

> /admin status

Shows the status of the bot

> /admin export

Exports the database as JSON to the filesystem

**The bot must have permission to manage channels and roles*
