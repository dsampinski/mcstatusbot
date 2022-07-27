# MC Status Bot
A simple Python Discord bot that displays Minecraft servers' statuses and players

# Setup
    A Python installation is required

`git clone https://github.com/dsampinski/mcstatusbot.git && cd mcstatusbot`

`pip install -r requirements.txt`

## Run
`python mcstatusbot.py`

## Update
`git pull`

# Config
> token

The bot's [token](https://www.writebots.com/discord-bot-token/)

> adminId

The Discord ID of the bot's admin (to bypass restrictions)

> pingInterval

Interval (in seconds) between each server ping

> updateInterval

Interval (in seconds) between each Discord status update (the voice channel update interval is constant at 5 minutes)

> addressesPerGuild

Maximum amount of servers that can be added per guild (bypassed by the bot's admin)

> showPlayers

Whether to show the players list or not

# Commands
## Everyone
> $ping

Ping the bot for its status

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
