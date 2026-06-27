"""Reader for PennMUSH chat databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.chat_model import PennChannel, PennChannelUser, PennChatDatabase
from mushy_peas.compression import CompressionMode, read_database_text
from mushy_peas.constants import CHAT_FLAG_SPIFFY, END_MARKER_CURRENT
from mushy_peas.errors import ParseError
from mushy_peas.primitives import LineReader, parse_labeled_line


def read_chat_database(
    path: str | Path,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> PennChatDatabase:
    """Read a PennMUSH chat database file."""

    text = read_database_text(
        path,
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )
    return read_chat_database_text(text, source=str(path))


def read_chat_database_text(
    text: str,
    *,
    source: str = "<string>",
) -> PennChatDatabase:
    """Parse a current labeled PennMUSH chat database."""

    reader = LineReader(text, source=source)
    raw_chat_flags = _read_chat_header(reader)
    savedtime = _read_quoted(reader, "savedtime")
    channel_count = _read_int(reader, "channels")
    channels = [
        _read_channel(reader, raw_chat_flags=raw_chat_flags)
        for _ in range(channel_count)
    ]
    eod = reader.read_line()
    if eod != END_MARKER_CURRENT:
        raise reader.error(
            "bad chat end marker",
            expected=END_MARKER_CURRENT,
            actual=eod,
        )
    return PennChatDatabase(
        raw_chat_flags=raw_chat_flags,
        savedtime=savedtime,
        channels=channels,
        line_ending=reader.line_ending,
    )


def _read_chat_header(reader: LineReader) -> int:
    line = reader.read_line()
    if not line.startswith("+V"):
        raise reader.error(
            "unsupported chat database format",
            expected="+V<int>",
            actual=line,
        )
    try:
        return int(line[2:])
    except ValueError as exc:
        raise reader.error(
            "invalid chat flags",
            expected="+V<int>",
            actual=line,
        ) from exc


def _read_channel(reader: LineReader, *, raw_chat_flags: int) -> PennChannel:
    name = _read_quoted(reader, "name")
    description = _read_quoted(reader, "description")
    flags = _read_int(reader, "flags")
    creator = _read_dbref(reader, "creator")
    cost = _read_int(reader, "cost")
    buffer_blocks: int | None = None
    mogrifier: int | None = None
    if raw_chat_flags & CHAT_FLAG_SPIFFY:
        buffer_blocks = _read_int(reader, "buffer")
        mogrifier = _read_dbref(reader, "mogrifier")

    locks, user_count = _read_locks_and_user_count(reader)
    users = [_read_user(reader) for _ in range(user_count)]
    return PennChannel(
        name=name,
        description=description,
        flags=flags,
        creator=creator,
        cost=cost,
        buffer_blocks=buffer_blocks,
        mogrifier=mogrifier,
        locks=locks,
        users=users,
    )


def _read_locks_and_user_count(reader: LineReader) -> tuple[dict[str, str], int]:
    locks: dict[str, str] = {}
    while True:
        line = reader.read_line()
        label, value_text = parse_labeled_line(
            line,
            "raw",
            source=reader.source,
            line=reader.line_number,
        )
        if label == "users":
            return locks, _parse_int(value_text, reader=reader, label="users")
        if label != "lock":
            raise reader.error(
                "unexpected channel label",
                expected="lock or users",
                actual=line,
            )
        lock_name = _parse_quoted_value(value_text, reader=reader, label="lock")
        if lock_name in locks:
            raise reader.error("duplicate channel lock", actual=lock_name)
        locks[lock_name] = _read_quoted(reader, "key")


def _read_user(reader: LineReader) -> PennChannelUser:
    return PennChannelUser(
        dbref=_read_dbref(reader, "dbref"),
        flags=_read_int(reader, "flags"),
        title=_read_quoted(reader, "title"),
    )


def _read_int(reader: LineReader, expected_label: str) -> int:
    label, value = parse_labeled_line(
        reader.read_line(),
        "int",
        source=reader.source,
        line=reader.line_number,
    )
    if label != expected_label:
        raise reader.error(
            "unexpected label",
            expected=expected_label,
            actual=label,
        )
    return value


def _read_dbref(reader: LineReader, expected_label: str) -> int:
    label, value = parse_labeled_line(
        reader.read_line(),
        "dbref",
        source=reader.source,
        line=reader.line_number,
    )
    if label != expected_label:
        raise reader.error(
            "unexpected label",
            expected=expected_label,
            actual=label,
        )
    return value


def _read_quoted(reader: LineReader, expected_label: str) -> str:
    label, value = parse_labeled_line(
        reader.read_line(),
        "quoted",
        source=reader.source,
        line=reader.line_number,
    )
    if label != expected_label:
        raise reader.error(
            "unexpected label",
            expected=expected_label,
            actual=label,
        )
    return value


def _parse_int(value_text: str, *, reader: LineReader, label: str) -> int:
    try:
        return int(value_text)
    except ValueError as exc:
        raise reader.error(
            f"invalid {label}",
            expected="<int>",
            actual=value_text,
        ) from exc


def _parse_quoted_value(value_text: str, *, reader: LineReader, label: str) -> str:
    try:
        parsed = parse_labeled_line(
            f"{label} {value_text}",
            "quoted",
            source=reader.source,
            line=reader.line_number,
        )
    except ParseError:
        raise
    parsed_label, value = parsed
    if parsed_label != label:
        raise reader.error(
            "unexpected label",
            expected=label,
            actual=parsed_label,
        )
    return value
