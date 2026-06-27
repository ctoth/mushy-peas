"""Dataclasses for PennMUSH chat databases."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PennChannelUser:
    dbref: int
    flags: int
    title: str


@dataclass(frozen=True)
class PennChannel:
    name: str
    description: str
    flags: int
    creator: int
    cost: int
    buffer_blocks: int | None = None
    mogrifier: int | None = None
    locks: dict[str, str] = field(default_factory=dict[str, str])
    users: list[PennChannelUser] = field(default_factory=list[PennChannelUser])


@dataclass(frozen=True)
class PennChatDatabase:
    raw_chat_flags: int
    savedtime: str | None
    channels: list[PennChannel] = field(default_factory=list[PennChannel])
    format_kind: Literal["chat-current", "chat-oldstyle"] = "chat-current"
    line_ending: str = "\n"
