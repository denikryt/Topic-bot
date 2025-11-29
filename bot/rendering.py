"""Helpers for rendering topics content."""
from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

from . import config
from .models import RenderedTopics, Topic

logger = logging.getLogger(__name__)


def format_topic_entry(topic: Topic) -> str:
    """Return a single human-friendly line describing a topic entry."""
    emoji = topic.emoji
    text = topic.text
    return config.TOPIC_ENTRY_TEMPLATE.format(emoji=emoji, text=text)


def build_topics_payload(
    topics: Sequence[Topic], target_message_id: Optional[str] = None
) -> RenderedTopics:
    """Return (content, emojis) for rendering a topics message.

    If *target_message_id* is provided, only topics belonging to that message are
    included.
    """
    relevant_topics: Sequence[Topic] = topics
    if target_message_id is not None:
        relevant_topics = [
            topic for topic in topics if str(topic.message_id) == str(target_message_id)
        ]

    lines: List[str] = []
    emojis: List[str] = []
    for topic in relevant_topics:
        emojis.append(str(topic.emoji))
        lines.append(format_topic_entry(topic))

    content = "\n".join(lines) if lines else config.TOPICS_EMPTY_MESSAGE
    return RenderedTopics(content=content, emojis=emojis)
