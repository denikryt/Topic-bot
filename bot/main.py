"""Entry point for the topics Discord bot."""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

import discord
from discord.ext import commands

from . import commands as topic_commands
from . import config, storage
from .services import topics as topic_service


class TopicBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        await storage.ensure_indexes()
        await topic_commands.setup(self)
        await self.tree.sync()

    async def on_message(self, message: discord.Message) -> None:
        # Always allow the bot and other bots to ignore this hook.
        if message.author.bot:
            return

        channel = message.channel
        guild = message.guild
        if guild is None or not isinstance(channel, discord.TextChannel):
            return

        if not config.is_allowed_guild(guild.id):
            return

        state = await topic_service.load_state(guild.id, channel.id)
        entry = state.entry
        if state.registry_dirty or state.topics_dirty:
            await topic_service.save_state(state)
        if entry is None:
            return

        # Process any prefix commands before removing the message.
        await self.process_commands(message)

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            return


def main() -> None:
    load_dotenv()  # load .env into process env
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print(config.MISSING_TOKEN_MESSAGE)
        sys.exit(1)

    bot = TopicBot()
    try:
        bot.run(token)
    except RuntimeError as exc:
        # Provide a clear message (e.g., Mongo not reachable) before exiting.
        print(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
