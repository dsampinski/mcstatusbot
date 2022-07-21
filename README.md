# MC Status Bot
A simple Python Discord bot that tracks Minecraft servers' statuses

# Setup
`pip install -r requirements.txt`

`python mcstatusbot.py`

# Config
> token

The bot's [token](https://www.writebots.com/discord-bot-token/)

> adminId

The Discord ID of the bot's admin (to bypass restrictions)

> pingInterval

Interval between each server ping

> updateInterval

Interval between each Discord status update (the voice channel update interval is constant at 5 minutes)

> addressesPerGuild

Maximum amount of servers that can be added per guild (bypassed by the bot's admin)

# Commands
> $ping

Ping the bot for its status

> $add *address name*

Add a server's status to the guild

> $rem *address*

Remove a server's status from the guild

> $list

List all servers in the guild
