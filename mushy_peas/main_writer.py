"""Writer for current PennMUSH main object databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.compression import CompressionMode, write_database_text
from mushy_peas.constants import (
    CURRENT_DB_VERSION,
    CURRENT_MAIN_DB_FLAGS,
    END_MARKER_CURRENT,
    OBJECT_TYPE_GARBAGE,
)
from mushy_peas.main_model import (
    PennAttribute,
    PennFlag,
    PennLock,
    PennMainDatabase,
    PennObject,
)
from mushy_peas.primitives import encode_db_header, write_dbref, write_quoted_string


def write_main_database(
    path: str | Path,
    database: PennMainDatabase,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> None:
    write_database_text(
        path,
        write_main_database_text(database),
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )


def write_main_database_text(database: PennMainDatabase) -> str:
    lines = [
        encode_db_header(CURRENT_MAIN_DB_FLAGS),
        f"dbversion {CURRENT_DB_VERSION}",
        f"savedtime {write_quoted_string(database.savedtime)}",
        *write_global_lists(database).splitlines(),
        f"~{database.object_count}",
    ]

    for dbref in sorted(database.objects):
        obj = database.objects[dbref]
        if obj.type == OBJECT_TYPE_GARBAGE:
            continue
        lines.append(f"!{obj.dbref}")
        lines.extend(write_object_record_lines(obj))

    lines.append(END_MARKER_CURRENT)
    return database.line_ending.join(lines) + database.line_ending


def write_global_lists(database: PennMainDatabase) -> str:
    return "\n".join(
        (
            write_flag_section("+FLAGS LIST", database.flags),
            write_flag_section("+POWER LIST", database.powers),
            write_attribute_section(database.attributes),
        )
    )


def write_flag_section(section_header: str, flags: dict[str, PennFlag]) -> str:
    lines: list[str] = [section_header]
    lines.append(f"flagcount {len(flags)}")
    for flag in flags.values():
        lines.extend(
            (
                f" name {write_quoted_string(flag.name)}",
                f"  letter {write_quoted_string(flag.letter)}",
                f"  type {write_quoted_string(_join_words(flag.types))}",
                f"  perms {write_quoted_string(_join_words(flag.perms))}",
                "  negate_perms "
                f"{write_quoted_string(_join_words(flag.negate_perms))}",
            )
        )

    alias_count = sum(len(flag.aliases) for flag in flags.values())
    lines.append(f"flagaliascount {alias_count}")
    for flag in flags.values():
        for alias in flag.aliases:
            lines.extend(
                (
                    f" name {write_quoted_string(flag.name)}",
                    f"  alias {write_quoted_string(alias)}",
                )
            )

    return "\n".join(lines)


def write_attribute_section(attributes: dict[str, PennAttribute]) -> str:
    lines: list[str] = ["+ATTRIBUTES LIST"]
    lines.append(f"attrcount {len(attributes)}")
    for attribute in attributes.values():
        lines.extend(
            (
                f" name {write_quoted_string(attribute.name)}",
                f"  flags {write_quoted_string(_join_words(attribute.flags))}",
                f"  creator {write_dbref(attribute.creator)}",
                f"  data {write_quoted_string(attribute.data)}",
            )
        )

    alias_count = sum(len(attribute.aliases) for attribute in attributes.values())
    lines.append(f"attraliascount {alias_count}")
    for attribute in attributes.values():
        for alias in attribute.aliases:
            lines.extend(
                (
                    f" name {write_quoted_string(attribute.name)}",
                    f"  alias {write_quoted_string(alias)}",
                )
            )

    return "\n".join(lines)


def _join_words(words: tuple[str, ...]) -> str:
    return " ".join(words)


def write_object_record_lines(obj: PennObject) -> list[str]:
    lines = [
        f"name {write_quoted_string(obj.name)}",
        f"location {write_dbref(obj.location)}",
        f"contents {write_dbref(obj.contents)}",
        f"exits {write_dbref(obj.exits)}",
        f"next {write_dbref(obj.next)}",
        f"parent {write_dbref(obj.parent)}",
        *write_lock_lines(obj.locks),
        f"owner {write_dbref(obj.owner)}",
        f"zone {write_dbref(obj.zone)}",
        f"pennies {obj.pennies}",
        f"type {obj.type}",
        f"flags {write_quoted_string(_join_words(obj.flags))}",
        f"powers {write_quoted_string(_join_words(obj.powers))}",
        f"warnings {write_quoted_string(_join_words(obj.warnings))}",
        f"created {obj.created}",
        f"modified {obj.modified}",
        *write_object_attribute_lines(obj.attributes),
    ]
    return lines


def write_lock_lines(locks: dict[str, PennLock]) -> list[str]:
    lines = [f"lockcount {len(locks)}"]
    for lock in locks.values():
        lines.extend(
            (
                f" type {write_quoted_string(lock.type)}",
                f"  creator {write_dbref(lock.creator)}",
                f"  flags {write_quoted_string(_join_words(lock.flags))}",
                f"  derefs {lock.derefs}",
                f"  key {write_quoted_string(lock.key)}",
            )
        )
    return lines


def write_object_attribute_lines(attributes: dict[str, PennAttribute]) -> list[str]:
    lines = [f"attrcount {len(attributes)}"]
    for attribute in attributes.values():
        lines.extend(
            (
                f" name {write_quoted_string(attribute.name)}",
                f"  owner {write_dbref(attribute.creator)}",
                f"  flags {write_quoted_string(_join_words(attribute.flags))}",
                f"  derefs {attribute.derefs}",
                f"  value {write_quoted_string(attribute.data)}",
            )
        )
    return lines
