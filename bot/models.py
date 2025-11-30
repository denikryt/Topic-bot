"""Data models used across the topics bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MessageEntry:
    """Metadata about a topics message in a guild channel."""

    message_id: str
    count: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["MessageEntry"]:
        message_id = str(data.get("message_id") or "")
        if not message_id:
            return None
        return cls(message_id=message_id, count=int(data.get("count", 0)))

    def to_dict(self) -> Dict[str, Any]:
        return {"message_id": self.message_id, "count": self.count}


@dataclass
class Topic:
    """A single topic entry contributed by a guild member."""

    id: str
    emoji: str
    text: str
    author_id: str
    author_name: str
    message_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Topic":
        return cls(
            id=str(data.get("id") or ""),
            emoji=str(data.get("emoji") or ""),
            text=str(data.get("text") or ""),
            author_id=str(data.get("authorId") or ""),
            author_name=str(data.get("authorName") or ""),
            message_id=str(data.get("message_id") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "emoji": self.emoji,
            "text": self.text,
            "authorId": self.author_id,
            "authorName": self.author_name,
            "message_id": self.message_id,
        }


@dataclass
class GuildEntry:
    """Registry entry for a guild with associated messages."""

    channel_id: str
    welcome_message_id: str = ""
    board_header_message_id: str = ""
    contributors_message_id: str = ""
    notification_message_id: str = ""
    messages: List[MessageEntry] = field(default_factory=list)
    registry_dirty: bool = False

    @classmethod
    def from_raw(cls, raw: Optional[Dict[str, Any]]) -> Optional["GuildEntry"]:
        if raw is None:
            return None

        channel_id = str(raw.get("channel_id") or "")
        welcome_id = str(raw.get("welcome_message_id") or "")
        header_id = str(raw.get("board_header_message_id") or "")
        contributors_id = str(
            raw.get("contributors_message_id")
            or raw.get("userlist_message_id")
            or ""
        )
        notification_message_id = str(raw.get("notification_message_id") or "")

        messages_raw = raw.get("messages")
        messages: List[MessageEntry] = []
        registry_dirty = False

        if not isinstance(messages_raw, list) or not messages_raw:
            legacy_id = raw.get("message_id")
            if legacy_id:
                messages.append(MessageEntry(message_id=str(legacy_id), count=0))
                registry_dirty = True
        else:
            for message_raw in messages_raw:
                entry = MessageEntry.from_dict(message_raw)
                if entry:
                    messages.append(entry)

        entry = cls(
            channel_id=channel_id,
            welcome_message_id=welcome_id,
            board_header_message_id=header_id,
            contributors_message_id=contributors_id,
            notification_message_id=notification_message_id,
            messages=messages,
            registry_dirty=registry_dirty,
        )

        if raw.get("userlist_message_id") and not raw.get("contributors_message_id"):
            entry.registry_dirty = True
        return entry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "welcome_message_id": self.welcome_message_id,
            "board_header_message_id": self.board_header_message_id,
            "contributors_message_id": self.contributors_message_id,
            "notification_message_id": self.notification_message_id,
            "messages": [message.to_dict() for message in self.messages],
        }


@dataclass
class RenderedTopics:
    """Content produced for a topics message."""

    content: str
    emojis: List[str]


@dataclass
class GuildTopicState:
    """In-memory state for a guild registry entry and its topics."""

    guild_id: int
    entry: Optional[GuildEntry]
    topics: List[Topic]
    registry_dirty: bool = False
    topics_dirty: bool = False

    def mark_registry_dirty(self) -> None:
        self.registry_dirty = True

    def mark_topics_dirty(self) -> None:
        self.topics_dirty = True
