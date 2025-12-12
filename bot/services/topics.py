"""Shared helpers for manipulating guild topics state."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Tuple
from uuid import uuid4

from ..config import MAX_TOPICS_PER_MESSAGE
from .. import storage
from ..models import GuildEntry, GuildTopicState, MessageEntry, Topic

logger = logging.getLogger(__name__)

_guild_locks: Dict[int, asyncio.Lock] = {}


def _get_lock(guild_id: int) -> asyncio.Lock:
    lock = _guild_locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        _guild_locks[guild_id] = lock
    return lock


@asynccontextmanager
async def locked_state(guild_id: int, channel_id: int) -> AsyncIterator[GuildTopicState]:
    """Yield a normalized state for *guild_id*/*channel_id* and persist any changes."""
    lock = _get_lock(guild_id)
    async with lock:
        state = await load_state(guild_id, channel_id)
        try:
            yield state
        finally:
            await save_state(state)


async def load_state(guild_id: int, channel_id: int) -> GuildTopicState:
    """Load registry entry and topics list, normalizing data."""
    raw_entry = await storage.fetch_board(guild_id, channel_id)
    entry = GuildEntry.from_raw(raw_entry, channel_id=str(channel_id))
    topics_raw = await storage.load_topics(guild_id, channel_id) if entry else []
    topics = [Topic.from_dict(raw) for raw in topics_raw]

    entry, topics, entry_changed, topics_changed = normalize_entry_and_topics(entry, topics)
    state = GuildTopicState(
        guild_id=guild_id,
        channel_id=channel_id,
        entry=entry,
        topics=topics,
        registry_dirty=entry_changed,
        topics_dirty=topics_changed,
    )
    return state


async def save_state(state: GuildTopicState) -> None:
    """Persist registry and topics if marked dirty."""
    if state.registry_dirty:
        if state.entry:
            payload = state.entry.to_dict()
            payload["guild_id"] = str(state.guild_id)
            await storage.upsert_board(payload)
        else:
            await storage.delete_board(state.guild_id, state.channel_id)
        state.registry_dirty = False
        if state.entry:
            state.entry.registry_dirty = False

    if state.topics_dirty:
        await storage.save_topics(state.guild_id, state.channel_id, [topic.to_dict() for topic in state.topics])
        state.topics_dirty = False


def normalize_entry_and_topics(
    entry: Optional[GuildEntry], topics: List[Topic]
) -> Tuple[Optional[GuildEntry], List[Topic], bool, bool]:
    """Ensure entry/topic references and counts are consistent."""
    if entry is None:
        return None, topics, False, False

    registry_changed = entry.registry_dirty
    topics_changed = False

    if entry.messages:
        primary_id = entry.messages[0].message_id
        counts: Dict[str, int] = {message.message_id: 0 for message in entry.messages}

        for topic in topics:
            if not topic.message_id or topic.message_id not in counts:
                topic.message_id = primary_id
                topics_changed = True
            counts[topic.message_id] = counts.get(topic.message_id, 0) + 1

        for message in entry.messages:
            new_count = counts.get(message.message_id, 0)
            if message.count != new_count:
                message.count = new_count
                registry_changed = True

    return entry, topics, registry_changed, topics_changed


def find_first_available_message(entry: GuildEntry) -> Optional[MessageEntry]:
    """Return the oldest message entry that still has capacity remaining."""
    for message in entry.messages:
        if message.count < MAX_TOPICS_PER_MESSAGE:
            return message
    return None


def register_message(entry: GuildEntry, message_id: str) -> MessageEntry:
    """Register a brand new topics message on the entry."""
    message = MessageEntry(message_id=message_id, count=0)
    entry.messages.append(message)
    entry.registry_dirty = True
    return message


def add_topic_to_state(
    state: GuildTopicState,
    emoji: str,
    text: str,
    author_id: str,
    author_name: str,
    message_id: str,
) -> Topic:
    """Append a topic to the in-memory state and bump counts."""
    topic = Topic(
        id=uuid4().hex,
        emoji=emoji,
        text=text,
        author_id=author_id,
        author_name=author_name,
        message_id=message_id,
    )
    state.topics.append(topic)
    state.topics_dirty = True

    if state.entry:
        for message in state.entry.messages:
            if message.message_id == message_id:
                message.count += 1
                state.registry_dirty = True
                break
    return topic


def remove_topic_from_state(
    state: GuildTopicState, topic_id: str
) -> Optional[Topic]:
    """Remove a topic by id, adjusting counts; returns removed topic if found."""
    target = next((topic for topic in state.topics if topic.id == topic_id), None)
    if target is None:
        return None

    state.topics = [topic for topic in state.topics if topic.id != topic_id]
    state.topics_dirty = True

    if state.entry:
        for message in state.entry.messages:
            if message.message_id == target.message_id:
                message.count = max(message.count - 1, 0)
                state.registry_dirty = True
                break
    return target


def has_emoji(state: GuildTopicState, emoji: str) -> bool:
    """Return True if the emoji is already used in this guild."""
    return any(topic.emoji == emoji for topic in state.topics)


def create_entry(
    channel_id: int,
    welcome_message_id: int,
    board_header_message_id: int | str,
    contributors_message_id: int | str,
    topics_message_id: int | str,
    notification_message_id: int | str = "",
) -> GuildEntry:
    """Construct a new registry entry for /init."""
    entry = GuildEntry(
        channel_id=str(channel_id),
        welcome_message_id=str(welcome_message_id),
        board_header_message_id=str(board_header_message_id),
        contributors_message_id=str(contributors_message_id),
        notification_message_id=str(notification_message_id or ""),
        messages=[MessageEntry(message_id=str(topics_message_id), count=0)],
    )
    entry.registry_dirty = True
    return entry
