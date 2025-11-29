"""Entry point for the topics Discord bot."""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

import discord
from discord.ext import commands

from . import commands as topic_commands
from . import config


class TopicBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await topic_commands.setup(self)
        await self.tree.sync()


def main() -> None:
    load_dotenv()  # load .env into process env
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print(config.MISSING_TOKEN_MESSAGE)
        sys.exit(1)

    bot = TopicBot()
    bot.run(token)


if __name__ == "__main__":
    main()
