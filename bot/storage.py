"""Storage helpers for the topics bot using MongoDB."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import motor.motor_asyncio
from pymongo import errors as pymongo_errors

# Mongo client and database
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
)
db = client.topicboard

guild_boards = db.guild_boards
topics_collection = db.topics

logger = logging.getLogger(__name__)


async def ensure_indexes() -> None:
    """Create required indexes if they do not already exist."""
    try:
        await guild_boards.create_index(
            [("guild_id", 1), ("channel_id", 1)], unique=True, name="guild_channel_unique"
        )
        await topics_collection.create_index(
            [("guild_id", 1), ("channel_id", 1)], name="topics_guild_channel"
        )
        await topics_collection.create_index(
            [("topic_id", 1)], unique=True, name="topic_id_unique"
        )
    except (pymongo_errors.ServerSelectionTimeoutError, pymongo_errors.ConnectionFailure) as exc:
        message = (
            "Unable to connect to MongoDB at "
            f"{MONGO_URI!r}. Ensure MongoDB is running and accessible."
        )
        logger.error(message)
        raise RuntimeError(message) from exc


async def fetch_board(guild_id: int | str, channel_id: int | str) -> Optional[Dict[str, Any]]:
    """Return a board document for the guild/channel if present."""
    return await guild_boards.find_one(
        {"guild_id": str(guild_id), "channel_id": str(channel_id)}
    )


async def upsert_board(entry: Dict[str, Any]) -> None:
    """Insert or replace a board document."""
    await guild_boards.replace_one(
        {"guild_id": str(entry["guild_id"]), "channel_id": str(entry["channel_id"])},
        entry,
        upsert=True,
    )


async def delete_board(guild_id: int | str, channel_id: int | str) -> None:
    """Delete a board document for the guild/channel."""
    await guild_boards.delete_one({"guild_id": str(guild_id), "channel_id": str(channel_id)})


async def load_topics(guild_id: int | str, channel_id: int | str) -> List[Dict[str, Any]]:
    """Return all topics for the guild/channel."""
    cursor = topics_collection.find(
        {"guild_id": str(guild_id), "channel_id": str(channel_id)}
    )
    return [doc async for doc in cursor]


async def save_topics(guild_id: int | str, channel_id: int | str, topics: List[Dict[str, Any]]) -> None:
    """Replace all topics for the guild/channel with the provided list."""
    await topics_collection.delete_many({"guild_id": str(guild_id), "channel_id": str(channel_id)})
    if topics:
        docs = []
        for topic in topics:
            topic_copy = dict(topic)
            topic_copy["guild_id"] = str(guild_id)
            topic_copy["channel_id"] = str(channel_id)
            docs.append(topic_copy)
        await topics_collection.insert_many(docs)


async def delete_topics_for_channel(guild_id: int | str, channel_id: int | str) -> None:
    """Delete all topics for the given guild/channel."""
    await topics_collection.delete_many({"guild_id": str(guild_id), "channel_id": str(channel_id)})
