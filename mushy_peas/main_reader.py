"""Reader for current PennMUSH main object databases."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from mushy_peas.compression import CompressionMode, read_database_text
from mushy_peas.errors import ParseError
from mushy_peas.main_model import (
    PennAttribute,
    PennFlag,
    PennLock,
    PennMainDatabase,
    PennObject,
)
from mushy_peas.primitives import (
    LineReader,
    decode_db_header,
    is_end_marker,
    parse_labeled_line,
)


def read_main_database(
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
    return read_main_database_text(text, source=str(path))


def read_main_database_text(
    text: str,
    *,
    source: str = "<string>",
) -> PennMainDatabase:
    reader = LineReader(text, source=source)
    database = _read_main_header_and_global_lists(reader)
    objects: dict[int, PennObject] = {}

    while not reader.eof():
        line_text = reader.read_line()
        if is_end_marker(line_text):
            return replace(database, objects=objects)
        if not line_text.startswith("!"):
            raise reader.error(
                "expected object record or end marker",
                expected="!<dbref> or end marker",
                actual=line_text,
            )
        dbref = _parse_object_record_header(line_text, reader)
        if dbref in objects:
            raise reader.error("duplicate object record", actual=line_text)
        if dbref < 0 or dbref >= database.object_count:
            raise reader.error(
                "object dbref is outside declared capacity",
                expected=f"0 <= dbref < {database.object_count}",
                actual=line_text,
            )
        objects[dbref] = read_object_record(reader, dbref)

    raise reader.error("missing end marker")


def read_main_header_and_global_lists(
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
    return read_main_header_and_global_lists_text(text, source=str(path))


def read_main_header_and_global_lists_text(
    text: str,
    *,
    source: str = "<string>",
) -> PennMainDatabase:
    reader = LineReader(text, source=source)
    return _read_main_header_and_global_lists(reader)


def _read_main_header_and_global_lists(reader: LineReader) -> PennMainDatabase:
    raw_dbflags = decode_db_header(
        reader.read_line(),
        source=reader.source,
        line=reader.line_number,
    )

    dbversion: int | None = None
    next_line = reader.peek_line()
    if next_line is not None and next_line.lstrip(" ").startswith("dbversion"):
        dbversion = _read_int(reader, "dbversion")

    savedtime = _read_quoted(reader, "savedtime")
    flags: dict[str, PennFlag] = {}
    powers: dict[str, PennFlag] = {}
    attributes: dict[str, PennAttribute] = {}

    while not reader.eof():
        line_text = reader.read_line()
        if line_text.startswith("~"):
            object_count = _parse_capacity(line_text, reader)
            return PennMainDatabase(
                raw_dbflags=raw_dbflags,
                dbversion=dbversion,
                savedtime=savedtime,
                flags=flags,
                powers=powers,
                attributes=attributes,
                object_count=object_count,
                line_ending=reader.line_ending,
            )
        if not line_text.startswith("+"):
            raise reader.error(
                "expected global list or object capacity",
                expected="+LIST or ~<count>",
                actual=line_text,
            )

        section = line_text[1:]
        if section == "FLAGS LIST":
            if flags:
                raise reader.error("duplicate FLAGS LIST", actual=line_text)
            flags = read_flags_list(reader)
        elif section == "POWER LIST":
            if powers:
                raise reader.error("duplicate POWER LIST", actual=line_text)
            powers = read_flags_list(reader)
        elif section == "ATTRIBUTES LIST":
            if attributes:
                raise reader.error("duplicate ATTRIBUTES LIST", actual=line_text)
            attributes = read_attribute_list(reader)
        else:
            raise reader.error(
                "unknown +LIST",
                expected="known global list",
                actual=line_text,
            )

    raise reader.error("missing object capacity", expected="~<count>")


def read_object_record(reader: LineReader, dbref: int) -> PennObject:
    name = _read_quoted(reader, "name")
    location = _read_dbref(reader, "location")
    contents = _read_dbref(reader, "contents")
    exits = _read_dbref(reader, "exits")
    next_dbref = _read_dbref(reader, "next")
    parent = _read_dbref(reader, "parent")
    locks = read_locks(reader)
    owner = _read_dbref(reader, "owner")
    zone = _read_dbref(reader, "zone")
    pennies = _read_int(reader, "pennies")
    object_type = _read_int(reader, "type")
    flags = _read_quoted_words(reader, "flags")
    powers = _read_quoted_words(reader, "powers")
    warnings = _read_quoted_words(reader, "warnings")
    created = _read_int(reader, "created")
    modified = _read_int(reader, "modified")
    attributes = read_object_attributes(reader)

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
        flags=flags,
        powers=powers,
        warnings=warnings,
        created=created,
        modified=modified,
        attributes=attributes,
    )


def read_locks(reader: LineReader) -> dict[str, PennLock]:
    lock_count = _read_int(reader, "lockcount")
    locks: dict[str, PennLock] = {}

    for _ in range(lock_count):
        lock_type = _read_quoted(reader, "type")
        if lock_type in locks:
            raise reader.error("duplicate lock type", actual=lock_type)
        locks[lock_type] = PennLock(
            type=lock_type,
            creator=_read_dbref(reader, "creator"),
            flags=_read_quoted_words(reader, "flags"),
            derefs=_read_int(reader, "derefs"),
            key=_read_quoted(reader, "key"),
        )

    return locks


def read_object_attributes(reader: LineReader) -> dict[str, PennAttribute]:
    attr_count = _read_int(reader, "attrcount")
    attributes: dict[str, PennAttribute] = {}

    for _ in range(attr_count):
        name = _read_quoted(reader, "name")
        if name in attributes:
            raise reader.error("duplicate object attribute", actual=name)
        attributes[name] = PennAttribute(
            name=name,
            creator=_read_dbref(reader, "owner"),
            flags=_read_quoted_words(reader, "flags"),
            derefs=_read_int(reader, "derefs"),
            data=_read_quoted(reader, "value"),
        )

    return attributes


def read_flags_list(reader: LineReader) -> dict[str, PennFlag]:
    flag_count = _read_int(reader, "flagcount")
    flags: dict[str, PennFlag] = {}

    for _ in range(flag_count):
        name = _read_quoted(reader, "name")
        if name in flags:
            raise reader.error("duplicate flag name", actual=name)
        flags[name] = PennFlag(
            name=name,
            letter=_read_quoted(reader, "letter"),
            types=_read_quoted_words(reader, "type"),
            perms=_read_quoted_words(reader, "perms"),
            negate_perms=_read_quoted_words(reader, "negate_perms"),
        )

    alias_count = _read_int(reader, "flagaliascount")
    for _ in range(alias_count):
        canonical_name = _read_quoted(reader, "name")
        alias = _read_quoted(reader, "alias")
        _attach_flag_alias(reader, flags, canonical_name, alias)

    return flags


def read_attribute_list(reader: LineReader) -> dict[str, PennAttribute]:
    attr_count = _read_int(reader, "attrcount")
    attributes: dict[str, PennAttribute] = {}

    for _ in range(attr_count):
        name = _read_quoted(reader, "name")
        if name in attributes:
            raise reader.error("duplicate attribute name", actual=name)
        attributes[name] = PennAttribute(
            name=name,
            flags=_read_quoted_words(reader, "flags"),
            creator=_read_dbref(reader, "creator"),
            data=_read_quoted(reader, "data"),
        )

    alias_count = _read_int(reader, "attraliascount")
    for _ in range(alias_count):
        canonical_name = _read_quoted(reader, "name")
        alias = _read_quoted(reader, "alias")
        _attach_attribute_alias(reader, attributes, canonical_name, alias)

    return attributes


def _attach_flag_alias(
    reader: LineReader,
    flags: dict[str, PennFlag],
    canonical_name: str,
    alias: str,
) -> None:
    canonical = flags.get(canonical_name)
    if canonical is None:
        raise reader.error("flag alias target is missing", actual=canonical_name)
    flags[canonical_name] = PennFlag(
        name=canonical.name,
        letter=canonical.letter,
        types=canonical.types,
        perms=canonical.perms,
        negate_perms=canonical.negate_perms,
        aliases=(*canonical.aliases, alias),
    )


def _attach_attribute_alias(
    reader: LineReader,
    attributes: dict[str, PennAttribute],
    canonical_name: str,
    alias: str,
) -> None:
    canonical = attributes.get(canonical_name)
    if canonical is None:
        raise reader.error("attribute alias target is missing", actual=canonical_name)
    attributes[canonical_name] = PennAttribute(
        name=canonical.name,
        flags=canonical.flags,
        creator=canonical.creator,
        data=canonical.data,
        aliases=(*canonical.aliases, alias),
    )


def _read_int(reader: LineReader, expected_label: str) -> int:
    line_text = reader.read_line()
    actual_label, value = parse_labeled_line(
        line_text,
        "int",
        source=reader.source,
        line=reader.line_number,
    )
    _require_label(reader, actual_label, expected_label, line_text)
    return value


def _read_dbref(reader: LineReader, expected_label: str) -> int:
    line_text = reader.read_line()
    actual_label, value = parse_labeled_line(
        line_text,
        "dbref",
        source=reader.source,
        line=reader.line_number,
    )
    _require_label(reader, actual_label, expected_label, line_text)
    return value


def _read_quoted(reader: LineReader, expected_label: str) -> str:
    line_text = reader.read_line()
    actual_label, value = parse_labeled_line(
        line_text,
        "quoted",
        source=reader.source,
        line=reader.line_number,
    )
    _require_label(reader, actual_label, expected_label, line_text)
    return value


def _read_quoted_words(reader: LineReader, expected_label: str) -> tuple[str, ...]:
    return tuple(_read_quoted(reader, expected_label).split())


def _require_label(
    reader: LineReader,
    actual_label: str,
    expected_label: str,
    actual_line: str,
) -> None:
    if actual_label != expected_label:
        raise ParseError(
            "unexpected label",
            source=reader.source,
            line=reader.line_number,
            expected=expected_label,
            actual=actual_line,
        )


def _parse_capacity(line_text: str, reader: LineReader) -> int:
    try:
        return int(line_text[1:])
    except ValueError as exc:
        raise ParseError(
            "invalid object capacity",
            source=reader.source,
            line=reader.line_number,
            expected="~<count>",
            actual=line_text,
        ) from exc


def _parse_object_record_header(line_text: str, reader: LineReader) -> int:
    try:
        return int(line_text[1:])
    except ValueError as exc:
        raise ParseError(
            "invalid object record header",
            source=reader.source,
            line=reader.line_number,
            expected="!<dbref>",
            actual=line_text,
        ) from exc
