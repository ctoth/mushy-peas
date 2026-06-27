"""Writer for PennMUSH mail databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.compression import CompressionMode, write_database_text
from mushy_peas.constants import END_MARKER_CURRENT, MAIL_FLAGS_CURRENT
from mushy_peas.mail_model import PennMailAlias, PennMailDatabase, PennMailMessage
from mushy_peas.mail_reader import MALIAS_END_MARKER
from mushy_peas.primitives import write_quoted_string


def write_mail_database(
    path: str | Path,
    database: PennMailDatabase,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> None:
    """Write a PennMUSH mail database file."""

    write_database_text(
        path,
        write_mail_database_text(database),
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )


def write_mail_database_text(database: PennMailDatabase) -> str:
    """Serialize a PennMUSH mail database using the current dump format."""

    line_ending = database.line_ending
    lines: list[str] = [f"+{MAIL_FLAGS_CURRENT}"]
    lines.extend(_write_aliases(database.aliases))
    lines.append(str(len(database.messages)))
    for message in database.messages:
        lines.extend(_write_message(message))
    lines.append(END_MARKER_CURRENT)
    return line_ending.join(lines) + line_ending


def _write_aliases(aliases: Sequence[PennMailAlias]) -> list[str]:
    lines = [str(len(aliases))]
    for alias in aliases:
        lines.extend(
            (
                str(alias.owner),
                write_quoted_string(alias.name),
                write_quoted_string(alias.description),
                str(alias.name_flags),
                str(alias.member_flags),
                str(len(alias.members)),
            )
        )
        lines.extend(str(member) for member in alias.members)
    lines.append(write_quoted_string(MALIAS_END_MARKER))
    return lines


def _write_message(message: PennMailMessage) -> list[str]:
    return [
        str(message.to),
        str(message.from_),
        str(message.from_ctime),
        write_quoted_string(message.time_text),
        write_quoted_string(message.subject),
        write_quoted_string(message.body),
        str(message.read_flags),
    ]
