"""Writer for PennMUSH chat databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.chat_model import PennChannel, PennChannelUser, PennChatDatabase
from mushy_peas.compression import CompressionMode, write_database_text
from mushy_peas.constants import CHAT_FLAGS_CURRENT, END_MARKER_CURRENT
from mushy_peas.primitives import write_dbref, write_quoted_string

CHAT_LOCK_ORDER = ("join", "speak", "modify", "see", "hide")
DEFAULT_LOCK_TEXT = "*UNLOCKED*"


def write_chat_database(
    path: str | Path,
    database: PennChatDatabase,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> None:
    """Write a PennMUSH chat database file."""

    write_database_text(
        path,
        write_chat_database_text(database),
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )


def write_chat_database_text(database: PennChatDatabase) -> str:
    """Serialize a PennMUSH chat database using the current labeled format."""

    line_ending = database.line_ending
    savedtime = database.savedtime or ""
    lines = [
        f"+V{CHAT_FLAGS_CURRENT}",
        f"savedtime {write_quoted_string(savedtime)}",
        f"channels {len(database.channels)}",
    ]
    for channel in database.channels:
        lines.extend(_write_channel(channel))
    lines.append(END_MARKER_CURRENT)
    return line_ending.join(lines) + line_ending


def _write_channel(channel: PennChannel) -> list[str]:
    lines = [
        f" name {write_quoted_string(channel.name)}",
        f"  description {write_quoted_string(channel.description)}",
        f"  flags {channel.flags}",
        f"  creator {write_dbref(channel.creator)}",
        f"  cost {channel.cost}",
        f"  buffer {channel.buffer_blocks or 0}",
        f"  mogrifier {write_dbref(_mogrifier_dbref(channel))}",
    ]
    for lock_name in CHAT_LOCK_ORDER:
        key = channel.locks.get(lock_name, DEFAULT_LOCK_TEXT)
        lines.extend(
            (
                f"  lock {write_quoted_string(lock_name)}",
                f"  key {write_quoted_string(key)}",
            )
        )
    lines.append(f"  users {len(channel.users)}")
    for user in channel.users:
        lines.extend(_write_user(user))
    return lines


def _write_user(user: PennChannelUser) -> list[str]:
    return [
        f"   dbref {write_dbref(user.dbref)}",
        f"    flags {user.flags}",
        f"    title {write_quoted_string(user.title)}",
    ]


def _mogrifier_dbref(channel: PennChannel) -> int:
    if channel.mogrifier is None:
        return -1
    return channel.mogrifier
