"""Slash commands and rendering logic for the topics bot."""
from __future__ import annotations

import logging
from typing import List, Optional

import discord
import emoji as emoji_lib
from discord import app_commands
from discord.ext import commands

from . import config, rendering, storage
from .models import GuildEntry, Topic
from .services import topics as topic_service

logger = logging.getLogger(__name__)


async def _resolve_text_channel(
    bot: commands.Bot, guild: Optional[discord.Guild], channel_id: int
) -> Optional[discord.TextChannel]:
    """Return a text channel for *channel_id* in *guild* if accessible."""
    if guild is None:
        return None
    try:
        channel = guild.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return None
    return channel if isinstance(channel, discord.TextChannel) else None


async def _fetch_message(channel: discord.TextChannel, message_id: int) -> Optional[discord.Message]:
    """Fetch a message by id, handling common Discord errors."""
    try:
        return await channel.fetch_message(message_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return None


async def _delete_message_safely(
    channel: Optional[discord.TextChannel], message_id: Optional[str | int]
) -> None:
    """Delete a message if it can be fetched; ignore missing or inaccessible ones."""
    if channel is None or not message_id:
        return

    message = await _fetch_message(channel, int(message_id))
    if message is None:
        return

    try:
        await message.delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return


async def _delete_notification_message(
    channel: Optional[discord.TextChannel], message_id: str
) -> None:
    """Delete the stored notification message if it exists."""
    if channel is None or not message_id:
        return

    message = await _fetch_message(channel, int(message_id))
    if message is None:
        return

    try:
        await message.delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return


async def _send_notification_message(
    channel: Optional[discord.TextChannel], content: str
) -> Optional[discord.Message]:
    """Send a notification message, returning the created message if successful."""
    if channel is None:
        return None

    try:
        return await channel.send(content)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        logger.warning("Failed to send notification message to channel %s", channel.id)
        return None


def _collect_contributor_ids(topics: List[Topic]) -> List[str]:
    """Return sorted list of contributor IDs present in *topics*."""
    contributors = {topic.author_id for topic in topics if topic.author_id}
    return sorted(contributors)


async def _render_contributors_message(
    bot: commands.Bot, guild_id: int, entry: Optional[GuildEntry], topics: List[Topic]
) -> None:
    """Render the dedicated contributors message for *guild_id*."""
    if not entry or not entry.userlist_message_id:
        return

    guild = bot.get_guild(guild_id)
    channel_id = int(entry.channel_id or 0)
    channel = await _resolve_text_channel(bot, guild, channel_id)
    if channel is None:
        return

    message = await _fetch_message(channel, int(entry.userlist_message_id))
    if message is None:
        return

    contributor_ids = _collect_contributor_ids(topics)
    lines = [config.CONTRIBUTORS_HEADER]
    if contributor_ids:
        lines.append(" ".join(f"<@{user_id}>" for user_id in contributor_ids))
    else:
        lines.append(config.CONTRIBUTORS_EMPTY_STATE)

    content = "\n".join(lines)
    try:
        await message.edit(content=content)
    except discord.HTTPException:
        logger.warning("Failed to render contributors message for guild %s", guild_id)
        return


async def _remove_reaction_fully(message: discord.Message, emoji: str) -> None:
    """Remove *emoji* reaction (all users) from *message*."""
    target = next((reaction for reaction in message.reactions if str(reaction.emoji) == str(emoji)), None)
    if target is None:
        return

    try:
        users = [user async for user in target.users()]
    except discord.HTTPException:
        users = []

    for user in users:
        try:
            await target.remove(user)
        except discord.HTTPException:
            continue

    # Ensure no reaction record is left behind if bot has permission.
    try:
        await message.clear_reaction(target.emoji)
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass


async def render_topics_message(
    bot: commands.Bot, guild_id: int, target_message_id: Optional[str] = None
) -> None:
    """Render one or all managed topics messages for *guild_id* and sync reactions."""
    async with topic_service.locked_state(guild_id) as state:
        entry = state.entry
        if not entry:
            return
        topics_snapshot = list(state.topics)
        messages_to_render = entry.messages
        if target_message_id is not None:
            messages_to_render = [
                message for message in entry.messages if str(message.message_id) == str(target_message_id)
            ]
        channel_id = int(entry.channel_id or 0)

    guild = bot.get_guild(guild_id)
    channel = await _resolve_text_channel(bot, guild, channel_id)
    if channel is None:
        return

    await _render_contributors_message(bot, guild_id, entry, topics_snapshot)

    for message_entry in messages_to_render:
        message_id = message_entry.message_id
        message = await _fetch_message(channel, int(message_id))
        if message is None:
            continue

        rendered = rendering.build_topics_payload(
            topics_snapshot, message_entry.message_id
        )
        await message.edit(content=rendered.content)

        used_emojis = set(rendered.emojis)
        existing_reactions = list(message.reactions)
        existing_emojis = {str(reaction.emoji) for reaction in existing_reactions}

        for emoji in used_emojis - existing_emojis:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                continue

        # Remove reactions for unused emojis. Prefer clearing all users; if not permitted,
        # fall back to removing only the bot's own reaction.
        for reaction in existing_reactions:
            emoji_str = str(reaction.emoji)
            if emoji_str in used_emojis:
                continue

            try:
                await message.clear_reaction(reaction.emoji)
                continue
            except discord.Forbidden:
                pass  # Try removing only the bot's own reaction below.
            except discord.HTTPException:
                continue

            try:
                if reaction.me and message.guild and message.guild.me:
                    await reaction.remove(message.guild.me)
            except discord.HTTPException:
                logger.debug(
                    "Failed to remove reaction %s from message %s in guild %s",
                    emoji_str,
                    message.id,
                    guild_id,
                )
                continue


class WelcomeMessageModal(discord.ui.Modal):
    """Modal for editing the welcome message content."""

    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int,
        channel_id: int,
        welcome_message_id: int,
        current_content: str,
    ) -> None:
        super().__init__(title=config.WELCOME_MODAL_TITLE)
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.welcome_message_id = welcome_message_id
        self.message_input = discord.ui.TextInput(
            label=config.WELCOME_MODAL_LABEL,
            style=discord.TextStyle.paragraph,
            required=True,
            default=current_content,
            max_length=2000,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or guild.id != self.guild_id:
            await interaction.response.send_message(
                config.ACTION_ONLY_IN_CONFIGURED_SERVER, ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                config.MANAGE_SERVER_REQUIRED_EDIT_WELCOME, ephemeral=True
            )
            return

        channel = await _resolve_text_channel(self.bot, guild, self.channel_id)
        if channel is None:
            await interaction.response.send_message(
                config.CONFIGURED_CHANNEL_INACCESSIBLE, ephemeral=True
            )
            return

        message = await _fetch_message(channel, int(self.welcome_message_id))
        if message is None:
            await interaction.response.send_message(
                config.WELCOME_MESSAGE_INACCESSIBLE, ephemeral=True
            )
            return

        try:
            await message.edit(content=self.message_input.value)
        except discord.HTTPException:
            await interaction.response.send_message(
                config.WELCOME_MESSAGE_UPDATE_FAILED, ephemeral=True
            )
            return

        # Acknowledge the modal submission without sending a confirmation message.
        await interaction.response.defer(ephemeral=True)


class WelcomeMessageEditView(discord.ui.View):
    """Ephemeral view providing a button to open the welcome modal."""

    def __init__(self, bot: commands.Bot, guild_id: int, channel_id: int, welcome_message_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.welcome_message_id = welcome_message_id

    @discord.ui.button(label=config.WELCOME_EDIT_BUTTON_LABEL, style=discord.ButtonStyle.primary)
    async def edit_welcome(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        guild = interaction.guild
        if guild is None or guild.id != self.guild_id:
            await interaction.response.send_message(
                config.ACTION_ONLY_IN_CONFIGURED_SERVER, ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                config.MANAGE_SERVER_REQUIRED_EDIT_WELCOME, ephemeral=True
            )
            return

        channel = await _resolve_text_channel(self.bot, guild, self.channel_id)
        if channel is None:
            await interaction.response.send_message(
                config.CONFIGURED_CHANNEL_INACCESSIBLE, ephemeral=True
            )
            return

        message = await _fetch_message(channel, int(self.welcome_message_id))
        if message is None:
            await interaction.response.send_message(
                config.WELCOME_MESSAGE_INACCESSIBLE, ephemeral=True
            )
            return

        modal = WelcomeMessageModal(
            self.bot,
            guild.id,
            channel.id,
            int(self.welcome_message_id),
            message.content or "",
        )
        await interaction.response.send_modal(modal)


class Topics(commands.Cog):
    """Cog containing topics board commands and helpers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _require_registered(self, interaction: discord.Interaction) -> Optional[GuildEntry]:
        """Ensure the guild is registered; inform the user if not."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return None

        state = topic_service.load_state(guild.id)
        entry = state.entry
        if state.registry_dirty or state.topics_dirty:
            topic_service.save_state(state)
        if not entry:
            await interaction.response.send_message(
                config.SERVER_NOT_INITIALIZED, ephemeral=True
            )
            return None
        return entry

    @app_commands.command(name="init", description=config.INIT_COMMAND_DESCRIPTION)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def init(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return

        channel = interaction.channel
        state = topic_service.load_state(guild.id)
        entry = state.entry
        if (
            entry
            and channel is not None
            and isinstance(channel, discord.TextChannel)
            and str(channel.id) == str(entry.channel_id)
        ):
            await interaction.response.send_message(
                config.INIT_ALREADY_EXISTS, ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        if channel is None or not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(config.TEXT_CHANNEL_ONLY_COMMAND, ephemeral=True)
            return

        welcome_text = config.DEFAULT_WELCOME_MESSAGE
        welcome_message_obj = await channel.send(welcome_text)
        contributors_message = await channel.send(config.DEFAULT_CONTRIBUTORS_MESSAGE)
        topics_message = await channel.send(config.TOPICS_INITIALIZING_MESSAGE)
        new_entry = topic_service.create_entry(
            channel_id=channel.id,
            welcome_message_id=welcome_message_obj.id,
            userlist_message_id=contributors_message.id,
            topics_message_id=topics_message.id,
        )

        async with topic_service.locked_state(guild.id) as state:
            state.entry = new_entry
            state.registry_dirty = True
            state.topics = []
            state.topics_dirty = True

        await render_topics_message(self.bot, guild.id)
        view = WelcomeMessageEditView(
            self.bot,
            guild.id,
            channel.id,
            welcome_message_obj.id,
        )
        await interaction.followup.send(
            config.INIT_FOLLOWUP_PROMPT,
            view=view,
            ephemeral=True,
        )

    @init.error
    async def init_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(
                    config.MANAGE_SERVER_REQUIRED_INIT, ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    config.MANAGE_SERVER_REQUIRED_INIT, ephemeral=True
                )
            return
        raise error

    @app_commands.command(
        name="editwelcomemessage",
        description=config.EDIT_WELCOME_COMMAND_DESCRIPTION
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def edit_welcome_message(self, interaction: discord.Interaction) -> None:
        entry = await self._require_registered(interaction)
        if entry is None:
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return

        welcome_message_id = entry.welcome_message_id
        if not welcome_message_id:
            await interaction.response.send_message(
                config.NO_WELCOME_MESSAGE_CONFIGURED,
                ephemeral=True,
            )
            return

        channel_id = int(entry.channel_id or 0)
        channel = await _resolve_text_channel(self.bot, guild, channel_id)
        if channel is None:
            await interaction.response.send_message(
                config.CONFIGURED_CHANNEL_INACCESSIBLE, ephemeral=True
            )
            return

        message = await _fetch_message(channel, int(welcome_message_id))
        if message is None:
            await interaction.response.send_message(
                config.WELCOME_MESSAGE_INACCESSIBLE, ephemeral=True
            )
            return

        modal = WelcomeMessageModal(
            self.bot,
            guild.id,
            channel.id,
            int(welcome_message_id),
            message.content or "",
        )
        await interaction.response.send_modal(modal)

    @edit_welcome_message.error
    async def edit_welcome_message_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(
                    config.MANAGE_SERVER_REQUIRED_EDIT_WELCOME, ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    config.MANAGE_SERVER_REQUIRED_EDIT_WELCOME, ephemeral=True
                )
            return
        raise error

    @app_commands.command(name="addtopic", description=config.ADD_TOPIC_COMMAND_DESCRIPTION)
    @app_commands.describe(
        emoji="set a topic emoji",
        topic="add a topic name",
    )
    async def addtopic(self, interaction: discord.Interaction, emoji: str, topic: str) -> None:
        entry = await self._require_registered(interaction)
        if entry is None:
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return

        if (
            emoji_lib.emoji_count(emoji) != 1
            or emoji.strip() != emoji
            or not emoji_lib.is_emoji(emoji)
        ):
            await interaction.response.send_message(
                config.SINGLE_EMOJI_REQUIRED, ephemeral=True
            )
            return

        notification_content = config.NOTIFICATION_TEMPLATE.format(
            user=f"<@{interaction.user.id}>",
            emoji=emoji,
            text=topic,
        )

        await interaction.response.defer(ephemeral=True)

        target_message_id: Optional[str] = None
        channel: Optional[discord.TextChannel] = None

        async with topic_service.locked_state(guild.id) as state:
            entry = state.entry
            if entry is None:
                await interaction.followup.send(
                    config.SERVER_NOT_INITIALIZED, ephemeral=True
                )
                return

            if topic_service.has_emoji(state, emoji):
                await interaction.followup.send(
                    config.EMOJI_ALREADY_USED,
                    ephemeral=True,
                )
                return

            channel_id = int(entry.channel_id or 0)
            channel = await _resolve_text_channel(self.bot, guild, channel_id)
            if channel is None:
                await interaction.followup.send(
                    config.CONFIGURED_CHANNEL_INACCESSIBLE, ephemeral=True
                )
                return

            await _delete_notification_message(channel, entry.notification_message_id)
            if entry.notification_message_id:
                entry.notification_message_id = ""
                state.registry_dirty = True

            target_message = topic_service.find_first_available_message(entry)
            if target_message is None:
                new_message = await channel.send(config.TOPICS_INITIALIZING_MESSAGE)
                target_message = topic_service.register_message(entry, str(new_message.id))

            new_topic = topic_service.add_topic_to_state(
                state=state,
                emoji=emoji,
                text=topic,
                author_id=str(interaction.user.id),
                author_name=interaction.user.display_name,
                message_id=target_message.message_id,
            )
            target_message_id = new_topic.message_id

        await render_topics_message(self.bot, guild.id, target_message_id)

        notification_message = await _send_notification_message(channel, notification_content)
        if notification_message:
            notification_id = str(notification_message.id)
            async with topic_service.locked_state(guild.id) as state:
                entry = state.entry
                if entry is None:
                    pass
                else:
                    existing_id = entry.notification_message_id
                    if existing_id and existing_id != notification_id:
                        await _delete_notification_message(channel, notification_id)
                    else:
                        entry.notification_message_id = notification_id
                        state.registry_dirty = True
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

    @app_commands.command(name="removeboards", description=config.REMOVE_BOARDS_COMMAND_DESCRIPTION)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def removeboards(self, interaction: discord.Interaction) -> None:
        entry = await self._require_registered(interaction)
        if entry is None:
            return

        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                config.REMOVE_BOARDS_CHANNEL_ONLY, ephemeral=True
            )
            return

        if str(channel.id) != entry.channel_id:
            await interaction.response.send_message(
                config.REMOVE_BOARDS_CHANNEL_ONLY, ephemeral=True
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        async with topic_service.locked_state(guild.id) as state:
            entry = state.entry
            if entry is None:
                await interaction.followup.send(
                    config.SERVER_NOT_INITIALIZED, ephemeral=True
                )
                return

            if str(channel.id) != entry.channel_id:
                await interaction.followup.send(
                    config.REMOVE_BOARDS_CHANNEL_ONLY, ephemeral=True
                )
                return

            channel_id = int(entry.channel_id or 0)
            channel = await _resolve_text_channel(self.bot, guild, channel_id)
            if channel is None:
                await interaction.followup.send(
                    config.CONFIGURED_CHANNEL_INACCESSIBLE, ephemeral=True
                )
                return

            welcome_id = entry.welcome_message_id
            userlist_id = entry.userlist_message_id
            notification_id = entry.notification_message_id
            topic_message_ids = [message.message_id for message in entry.messages]

            await _delete_message_safely(channel, welcome_id)
            await _delete_message_safely(channel, userlist_id)
            for message_id in topic_message_ids:
                await _delete_message_safely(channel, message_id)
            await _delete_notification_message(channel, notification_id)

            storage.delete_topics_file(guild.id)
            state.entry = None
            state.registry_dirty = True
            state.topics = []
            state.topics_dirty = False

        await interaction.followup.send(config.REMOVE_BOARDS_SUCCESS, ephemeral=True)

    @removeboards.error
    async def removeboards_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send(
                    config.MANAGE_SERVER_REQUIRED_REMOVE_BOARDS, ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    config.MANAGE_SERVER_REQUIRED_REMOVE_BOARDS, ephemeral=True
                )
            return
        raise error

    @app_commands.command(
        name="topicshelp",
        description=config.TOPICS_HELP_COMMAND_DESCRIPTION,
    )
    async def topicshelp(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            config.TOPICS_HELP_MESSAGE,
            ephemeral=True,
        )

    async def topic_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        guild = interaction.guild
        if guild is None:
            return []

        state = topic_service.load_state(guild.id)
        if state.entry is None:
            return []

        topics: List[Topic] = state.topics
        if state.registry_dirty or state.topics_dirty:
            topic_service.save_state(state)

        caller_can_manage = interaction.user.guild_permissions.manage_guild if guild else False
        if not caller_can_manage:
            topics = [t for t in topics if t.author_id == str(interaction.user.id)]

        current_lower = current.lower()
        filtered = []
        for topic in topics:
            display = f"{topic.emoji} {topic.text}".strip()
            if current_lower in display.lower():
                filtered.append((topic, display))

        choices: List[app_commands.Choice[str]] = []
        for topic, display in filtered[:25]:
            choices.append(app_commands.Choice(name=display[:100], value=topic.id))
        return choices

    @app_commands.command(name="removetopic", description=config.REMOVE_TOPIC_COMMAND_DESCRIPTION)
    @app_commands.autocomplete(topic=topic_autocomplete)
    async def removetopic(self, interaction: discord.Interaction, topic: str) -> None:
        entry = await self._require_registered(interaction)
        if entry is None:
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                config.SERVER_ONLY_COMMAND, ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        target_message_id: Optional[str] = None
        target_emoji: Optional[str] = None

        async with topic_service.locked_state(guild.id) as state:
            entry = state.entry
            if entry is None:
                await interaction.followup.send(
                    config.SERVER_NOT_INITIALIZED, ephemeral=True
                )
                return

            selected = next((t for t in state.topics if t.id == topic), None)
            if not selected:
                await interaction.followup.send(config.TOPIC_NOT_FOUND, ephemeral=True)
                return

            caller_can_manage = interaction.user.guild_permissions.manage_guild if guild else False
            if not caller_can_manage and selected.author_id != str(interaction.user.id):
                await interaction.followup.send(
                    config.TOPIC_REMOVAL_NOT_ALLOWED, ephemeral=True
                )
                return

            removed = topic_service.remove_topic_from_state(state, topic)
            if removed:
                target_message_id = removed.message_id
                target_emoji = removed.emoji

        if target_message_id and target_emoji:
            channel_id = int(entry.channel_id or 0)
            channel = await _resolve_text_channel(self.bot, guild, channel_id)
            if channel is not None:
                message = await _fetch_message(channel, int(target_message_id))
                if message is not None:
                    await _remove_reaction_fully(message, target_emoji)

        await render_topics_message(self.bot, guild.id, target_message_id)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    """Attach the Topics cog to the bot."""
    await bot.add_cog(Topics(bot))
