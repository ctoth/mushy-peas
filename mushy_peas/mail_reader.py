"""Reader for PennMUSH mail databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.compression import CompressionMode, read_database_text
from mushy_peas.constants import (
    END_MARKER_CURRENT,
    END_MARKER_OLD,
    MAIL_FLAG_ALIASES,
    MAIL_FLAG_NEW_EOD,
    MAIL_FLAG_SENDER_CTIME,
    MAIL_FLAG_SUBJECT,
)
from mushy_peas.errors import ParseError
from mushy_peas.mail_model import PennMailAlias, PennMailDatabase, PennMailMessage
from mushy_peas.primitives import LineReader, parse_quoted_string

MALIAS_END_MARKER = "*** End of MALIAS ***"


def read_mail_database(
    path: str | Path,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> PennMailDatabase:
    """Read a PennMUSH mail database file."""

    text = read_database_text(
        path,
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )
    return read_mail_database_text(text, source=str(path))


def read_mail_database_text(
    text: str,
    *,
    source: str = "<string>",
) -> PennMailDatabase:
    """Parse a PennMUSH mail database from text."""

    reader = LineReader(text, source=source)
    raw_mail_flags = _read_mail_flags(reader)
    aliases: list[PennMailAlias] = []
    if raw_mail_flags & MAIL_FLAG_ALIASES:
        aliases = _read_aliases(reader)

    message_count = _read_int_line(reader, label="message count")
    messages = [
        _read_message(reader, raw_mail_flags=raw_mail_flags)
        for _ in range(message_count)
    ]
    eod = _read_eod(reader, raw_mail_flags=raw_mail_flags)

    return PennMailDatabase(
        raw_mail_flags=raw_mail_flags,
        aliases=aliases,
        messages=messages,
        eod=eod,
        line_ending=reader.line_ending,
    )


def _read_mail_flags(reader: LineReader) -> int:
    first_line = reader.peek_line()
    if first_line is None:
        raise reader.error("empty mail database", expected="mail flags or count")
    if not first_line.startswith("+"):
        return 0

    line = reader.read_line()
    try:
        return int(line[1:])
    except ValueError as exc:
        raise reader.error(
            "invalid mail flags",
            expected="+<int>",
            actual=line,
        ) from exc


def _read_aliases(reader: LineReader) -> list[PennMailAlias]:
    alias_count = _read_int_line(reader, label="alias count")
    aliases = [_read_alias(reader) for _ in range(alias_count)]
    marker = _read_quoted_line(reader, label="malias end marker")
    if marker != MALIAS_END_MARKER:
        raise reader.error(
            "bad mail alias end marker",
            expected=MALIAS_END_MARKER,
            actual=marker,
        )
    return aliases


def _read_alias(reader: LineReader) -> PennMailAlias:
    owner = _read_int_line(reader, label="alias owner")
    name = _read_quoted_line(reader, label="alias name")
    description = _read_quoted_line(reader, label="alias description")
    name_flags = _read_int_line(reader, label="alias name flags")
    member_flags = _read_int_line(reader, label="alias member flags")
    member_count = _read_int_line(reader, label="alias member count")
    members = tuple(
        _read_int_line(reader, label="alias member") for _ in range(member_count)
    )
    return PennMailAlias(
        owner=owner,
        name=name,
        description=description,
        name_flags=name_flags,
        member_flags=member_flags,
        members=members,
    )


def _read_message(
    reader: LineReader,
    *,
    raw_mail_flags: int,
) -> PennMailMessage:
    to = _read_int_line(reader, label="message recipient")
    from_ = _read_int_line(reader, label="message sender")
    if raw_mail_flags & MAIL_FLAG_SENDER_CTIME:
        from_ctime = _read_int_line(reader, label="message sender creation time")
    else:
        from_ctime = 0
    time_text = _read_quoted_line(reader, label="message time")
    if raw_mail_flags & MAIL_FLAG_SUBJECT:
        subject = _read_quoted_line(reader, label="message subject")
    else:
        subject = ""
    body = _read_quoted_line(reader, label="message body")
    read_flags = _read_int_line(reader, label="message read flags")
    return PennMailMessage(
        to=to,
        from_=from_,
        from_ctime=from_ctime,
        time_text=time_text,
        subject=subject,
        body=body,
        read_flags=read_flags,
    )


def _read_eod(reader: LineReader, *, raw_mail_flags: int) -> str:
    if raw_mail_flags & MAIL_FLAG_NEW_EOD:
        expected = END_MARKER_CURRENT
    else:
        expected = END_MARKER_OLD
    marker = reader.read_line()
    if marker != expected:
        raise reader.error(
            "bad mail end marker",
            expected=expected,
            actual=marker,
        )
    return marker


def _read_int_line(reader: LineReader, *, label: str) -> int:
    line = reader.read_line()
    try:
        return int(line)
    except ValueError as exc:
        raise reader.error(
            f"invalid {label}",
            expected="<int>",
            actual=line,
        ) from exc


def _read_quoted_line(reader: LineReader, *, label: str) -> str:
    line_number = reader.line_number + 1
    line = reader.read_line()
    value, trailing = parse_quoted_string(
        line,
        source=reader.source,
        line=line_number,
    )
    if trailing:
        raise ParseError(
            f"unexpected trailing text after {label}",
            source=reader.source,
            line=line_number,
            expected="end of line",
            actual=trailing,
        )
    return value
