"""Reader for current PennMUSH main object databases."""

from collections.abc import Sequence
from pathlib import Path

from mushy_peas.compression import CompressionMode, read_database_text
from mushy_peas.errors import ParseError
from mushy_peas.main_model import PennAttribute, PennFlag, PennMainDatabase
from mushy_peas.primitives import (
    LineReader,
    decode_db_header,
    parse_labeled_line,
)


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
