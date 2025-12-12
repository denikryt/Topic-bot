"""One-time migration from filesystem JSON storage to MongoDB.

Reads legacy `guilds.json` and `topics/<guild_id>.json` files and inserts
documents into MongoDB collections `guild_boards` and `topics` using the
new schema.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent
GUILDS_FILE = BASE_DIR / "bot" / "guilds.json"
TOPICS_DIR = BASE_DIR / "bot" / "topics"

DEFAULT_MONGO_URI = "mongodb://localhost:27017"


def load_json(path: Path, default: Any) -> Any:
    """Return JSON content from *path* or *default* on error."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logging.warning("Missing file: %s", path)
    except json.JSONDecodeError as exc:
        logging.warning("Invalid JSON in %s: %s", path, exc)
    return default


def migrate(mongo_uri: str = DEFAULT_MONGO_URI) -> None:
    """Run migration from JSON files into MongoDB."""
    logging.info("Connecting to MongoDB at %s", mongo_uri)
    client = MongoClient(mongo_uri)
    db = client.topicboard
    guild_boards = db.guild_boards
    topics_collection = db.topics

    # Clear existing data to avoid duplicates.
    logging.info("Clearing existing Mongo collections (guild_boards, topics)")
    guild_boards.delete_many({})
    topics_collection.delete_many({})

    guilds_raw: Dict[str, Dict[str, Any]] = load_json(GUILDS_FILE, default={})
    if not guilds_raw:
        logging.warning("No guild data found in %s; nothing to migrate.", GUILDS_FILE)

    guild_count = 0
    topic_count = 0

    # Insert guild boards.
    for guild_id, data in guilds_raw.items():
        channel_id = str(data.get("channel_id") or "")
        if not channel_id:
            logging.warning("Skipping guild %s: missing channel_id", guild_id)
            continue

        board_doc = {
            "guild_id": str(guild_id),
            "channel_id": channel_id,
            "welcome_message_id": str(data.get("welcome_message_id") or ""),
            "board_header_message_id": str(data.get("board_header_message_id") or ""),
            "contributors_message_id": str(data.get("contributors_message_id") or ""),
            "notification_message_id": str(data.get("notification_message_id") or ""),
            "messages": data.get("messages") or [],
        }
        guild_boards.insert_one(board_doc)
        guild_count += 1
        logging.info("Inserted guild board for guild %s channel %s", guild_id, channel_id)

    # Insert topics per guild file.
    if TOPICS_DIR.exists():
        for path in TOPICS_DIR.glob("*.json"):
            guild_id = path.stem
            topics_raw: List[Dict[str, Any]] = load_json(path, default=[])
            if not topics_raw:
                logging.info("Skipping topics file %s (empty or missing)", path.name)
                continue

            channel_id = str((guilds_raw.get(guild_id) or {}).get("channel_id") or "")
            if not channel_id:
                logging.warning(
                    "Skipping topics for guild %s: missing channel_id in guilds.json", guild_id
                )
                continue

            docs = []
            for topic in topics_raw:
                doc = {
                    "topic_id": str(topic.get("id") or ""),
                    "guild_id": str(guild_id),
                    "channel_id": channel_id,
                    "emoji": str(topic.get("emoji") or ""),
                    "text": str(topic.get("text") or ""),
                    "author_id": str(topic.get("authorId") or topic.get("author_id") or ""),
                    "author_name": str(topic.get("authorName") or topic.get("author_name") or ""),
                    "message_id": str(topic.get("message_id") or ""),
                }
                if not doc["topic_id"]:
                    logging.warning("Skipping topic in %s: missing id", path.name)
                    continue
                docs.append(doc)

            if not docs:
                logging.info("No valid topics to insert for guild %s", guild_id)
                continue

            result = topics_collection.insert_many(docs)
            inserted = len(result.inserted_ids)
            topic_count += inserted
            logging.info(
                "Inserted %d topics for guild %s (channel %s) from %s",
                inserted,
                guild_id,
                channel_id,
                path.name,
            )
    else:
        logging.warning("Topics directory not found: %s", TOPICS_DIR)

    logging.info("Migration complete: %d guild boards, %d topics inserted.", guild_count, topic_count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    migrate()
