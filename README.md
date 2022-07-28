# MC Status Bot
A simple Python Discord bot that displays Minecraft servers' statuses and players

You can [add the public bot to your Discord](https://discord.com/oauth2/authorize?client_id=1001671313393463358&permissions=268435472&scope=bot)

# Setup
    A Python installation is required

`pip install -r requirements.txt`

## Run
`python mcstatusbot.py`

# Config
> token

The bot's [token](https://www.writebots.com/discord-bot-token/)

> adminId

The Discord ID of the bot's admin (to bypass restrictions)

> pingInterval

Interval (in seconds) between each server ping

> updateInterval

Interval (in seconds) between each status update

> addressesPerGuild

Maximum amount of servers that can be added per guild (bypassed by the bot's admin)

> showPlayers

Whether to show the players list or not

# Commands
## Everyone
> $ping

Ping the bot for its status

> $help

Links to this page

## Users with permission to manage channels
> $add *address name*

Add a server's status to the guild

> $rem *address*

Remove a server's status from the guild

> $list

List all servers in the guild

## Bot admin
> $reload

Reload the bot's config file

> $shutdown

Shutdown the bot

**The bot must have permission to manage channels and roles*
