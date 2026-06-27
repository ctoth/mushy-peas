"""Oldstyle PennMUSH database readers and upgrade helpers."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from mushy_peas.compression import CompressionMode, read_database_text
from mushy_peas.constants import (
    DBF_CREATION_TIMES,
    DBF_LABELS,
    DBF_NEW_FLAGS,
    DBF_NEW_LOCKS,
    DBF_NEW_POWERS,
    DBF_NEW_STRINGS,
    DBF_NO_CHAT_SYSTEM,
    DBF_NO_POWERS,
    DBF_SPIFFY_LOCKS,
    DBF_TYPE_GARBAGE,
    DBF_WARNINGS,
    OBJECT_TYPE_GARBAGE,
    OBJECT_TYPE_THING,
)
from mushy_peas.errors import ParseError
from mushy_peas.main_model import PennAttribute, PennLock, PennMainDatabase, PennObject
from mushy_peas.main_reader import read_flags_list, read_locks
from mushy_peas.primitives import (
    LineReader,
    decode_db_header,
    is_end_marker,
    parse_quoted_string,
)


def read_oldstyle_main_database(
    path: str | Path,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> PennMainDatabase:
    text = read_database_text(
        path,
        compression=compression,
        external_command=external_command,
        encoding=encoding,
    )
    return read_oldstyle_main_database_text(text, source=str(path))


def read_oldstyle_main_database_text(
    text: str,
    *,
    source: str = "<string>",
) -> PennMainDatabase:
    reader = LineReader(text, source=source)
    raw_dbflags = decode_db_header(
        reader.read_line(),
        source=reader.source,
        line=reader.line_number,
    )
    if raw_dbflags & DBF_LABELS:
        raise reader.error("oldstyle reader requires a database without DBF_LABELS")

    database = PennMainDatabase(
        raw_dbflags=raw_dbflags,
        dbversion=None,
        savedtime="",
        line_ending=reader.line_ending,
        format_kind="main-oldstyle",
    )
    objects: dict[int, PennObject] = {}

    while not reader.eof():
        line_text = reader.read_line()
        if is_end_marker(line_text):
            return replace(database, objects=objects)
        if line_text.startswith("~"):
            database = replace(
                database,
                object_count=_parse_capacity(line_text, reader),
            )
        elif line_text == "+FLAGS LIST":
            database = replace(database, flags=read_flags_list(reader))
        elif line_text == "+POWER LIST":
            database = replace(database, powers=read_flags_list(reader))
        elif line_text.startswith("!"):
            dbref = _parse_object_header(line_text, reader)
            if dbref in objects:
                raise reader.error("duplicate object record", actual=line_text)
            objects[dbref] = _read_old_object(reader, dbref, raw_dbflags)
        else:
            raise reader.error(
                "unexpected oldstyle top-level record",
                expected="~<count>, +LIST, !<dbref>, or end marker",
                actual=line_text,
            )

    raise reader.error("missing end marker")


def _read_old_object(reader: LineReader, dbref: int, flags: int) -> PennObject:
    name = _read_old_string(reader, flags)
    location = _read_int_line(reader)
    contents = _read_int_line(reader)
    exits = _read_int_line(reader)
    next_dbref = _read_int_line(reader)
    parent = _read_int_line(reader)
    locks = _read_old_locks(reader, dbref, flags)
    owner = _read_int_line(reader)
    zone = _read_int_line(reader)
    pennies = _read_int_line(reader)
    object_type, object_flags = _read_old_type_and_flags(reader, flags)
    powers = _read_old_powers(reader, flags)

    if not flags & DBF_NO_CHAT_SYSTEM:
        _read_int_line(reader)

    warnings = _read_old_warnings(reader, flags)
    if flags & DBF_CREATION_TIMES:
        created = _read_int_line(reader)
        modified = _read_int_line(reader)
    else:
        created = 0
        modified = 0

    attributes = _read_old_attributes(reader, flags)
    if (
        not flags & DBF_TYPE_GARBAGE
        and object_type == OBJECT_TYPE_THING
        and "GOING" in object_flags
    ):
        object_type = OBJECT_TYPE_GARBAGE

    return PennObject(
        dbref=dbref,
        name=name,
        location=location,
        contents=contents,
        exits=exits,
        next=next_dbref,
        parent=parent,
        locks=locks,
        owner=owner,
        zone=zone,
        pennies=pennies,
        type=object_type,
        flags=object_flags,
        powers=powers,
        warnings=warnings,
        created=created,
        modified=modified,
        attributes=attributes,
    )


def _read_old_locks(
    reader: LineReader,
    dbref: int,
    flags: int,
) -> dict[str, PennLock]:
    if flags & DBF_SPIFFY_LOCKS:
        return read_locks(reader)
    if flags & DBF_NEW_LOCKS:
        return _read_new_lock_lines(reader, dbref)
    return _read_really_old_lock_lines(reader, dbref)


def _read_new_lock_lines(reader: LineReader, dbref: int) -> dict[str, PennLock]:
    locks: dict[str, PennLock] = {}
    while True:
        next_line = reader.peek_line()
        if next_line is None or not next_line.startswith("_"):
            return locks
        line_text = reader.read_line()
        lock_name, separator, key = line_text[1:].partition("|")
        if separator != "|":
            raise reader.error("invalid oldstyle lock", actual=line_text)
        locks[lock_name] = PennLock(
            type=lock_name,
            creator=dbref,
            flags=(),
            derefs=0,
            key=key,
        )


def _read_really_old_lock_lines(reader: LineReader, dbref: int) -> dict[str, PennLock]:
    locks: dict[str, PennLock] = {}
    for lock_name in ("Basic", "Use", "Enter"):
        line_text = reader.read_line()
        if line_text == "":
            continue
        locks[lock_name] = PennLock(
            type=lock_name,
            creator=dbref,
            flags=(),
            derefs=0,
            key=line_text,
        )
    return locks


def _read_old_type_and_flags(
    reader: LineReader,
    flags: int,
) -> tuple[int, tuple[str, ...]]:
    if flags & DBF_NEW_FLAGS:
        return (_read_int_line(reader), tuple(_read_quoted_line(reader).split()))
    raise reader.error(
        "old numeric flag conversion is not implemented in this slice",
        expected="DBF_NEW_FLAGS",
    )


def _read_old_powers(reader: LineReader, flags: int) -> tuple[str, ...]:
    if flags & DBF_NO_POWERS:
        return ()
    if flags & DBF_NEW_POWERS:
        return tuple(_read_quoted_line(reader).split())
    raise reader.error(
        "old numeric power conversion is not implemented in this slice",
        expected="DBF_NEW_POWERS or DBF_NO_POWERS",
    )


def _read_old_warnings(reader: LineReader, flags: int) -> tuple[str, ...]:
    if not flags & DBF_WARNINGS:
        return ()
    warning_bits = _read_int_line(reader)
    if warning_bits == 0:
        return ()
    raise reader.error(
        "non-zero old warning bit conversion is not implemented in this slice",
        actual=str(warning_bits),
    )


def _read_old_attributes(
    reader: LineReader,
    flags: int,
) -> dict[str, PennAttribute]:
    attributes: dict[str, PennAttribute] = {}
    while True:
        line_text = reader.read_line()
        if line_text == "<":
            return attributes
        if not line_text.startswith("]"):
            raise reader.error(
                "unexpected oldstyle attribute marker",
                expected="]name^owner^flags[^derefs] or <",
                actual=line_text,
            )
        parts = line_text[1:].split("^")
        if len(parts) not in {3, 4}:
            raise reader.error("invalid oldstyle attribute header", actual=line_text)
        attr_name = parts[0]
        creator = _parse_int(parts[1], reader, line_text)
        flag_bits = _parse_int(parts[2], reader, line_text)
        if flag_bits != 0:
            raise reader.error(
                "non-zero old attribute flag conversion is not implemented "
                "in this slice",
                actual=line_text,
            )
        derefs = _parse_int(parts[3], reader, line_text) if len(parts) == 4 else 0
        attributes[attr_name] = PennAttribute(
            name=attr_name,
            creator=creator,
            flags=(),
            derefs=derefs,
            data=_read_old_string(reader, flags),
        )


def _read_old_string(reader: LineReader, flags: int) -> str:
    if flags & DBF_NEW_STRINGS:
        return _read_quoted_line(reader)
    return reader.read_line().replace("\r", "\n")


def _read_quoted_line(reader: LineReader) -> str:
    line_text = reader.read_line()
    value, trailing = parse_quoted_string(
        line_text,
        source=reader.source,
        line=reader.line_number,
    )
    if trailing.strip(" "):
        raise reader.error(
            "unexpected trailing text after quoted value",
            expected="end of line",
            actual=line_text,
        )
    return value


def _read_int_line(reader: LineReader) -> int:
    line_text = reader.read_line()
    return _parse_int(line_text, reader, line_text)


def _parse_capacity(line_text: str, reader: LineReader) -> int:
    return _parse_int(line_text[1:], reader, line_text)


def _parse_object_header(line_text: str, reader: LineReader) -> int:
    return _parse_int(line_text[1:], reader, line_text)


def _parse_int(text: str, reader: LineReader, actual: str) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise ParseError(
            "invalid oldstyle integer",
            source=reader.source,
            line=reader.line_number,
            expected="<int>",
            actual=actual,
        ) from exc
