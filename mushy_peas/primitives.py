"""Low-level PennMUSH flatfile primitives."""

from collections.abc import Sequence
from typing import Literal, overload

from mushy_peas.constants import END_MARKER_CURRENT, END_MARKER_OLD
from mushy_peas.errors import ParseError

LabelValueKind = Literal["raw", "int", "dbref", "quoted", "words"]
EndMarkerStyle = Literal["current", "old"]
UINT32_MODULUS = 2**32
INT32_SIGN_BIT = 2**31


class LineReader:
    """Line-oriented reader with stable source and line context."""

    def __init__(self, text: str, *, source: str = "<string>") -> None:
        self.source = source
        self.line_ending = detect_line_ending(text)
        self._lines = text.splitlines()
        self._position = 0

    @property
    def line_number(self) -> int:
        return self._position

    def eof(self) -> bool:
        return self._position >= len(self._lines)

    def peek_line(self) -> str | None:
        if self.eof():
            return None
        return self._lines[self._position]

    def read_line(self) -> str:
        if self.eof():
            raise ParseError(
                "unexpected end of file",
                source=self.source,
                line=self._position + 1,
            )
        line = self._lines[self._position]
        self._position += 1
        return line

    def error(
        self,
        message: str,
        *,
        expected: str | None = None,
        actual: str | None = None,
    ) -> ParseError:
        return ParseError(
            message,
            source=self.source,
            line=max(self._position, 1),
            expected=expected,
            actual=actual,
        )


def detect_line_ending(text: str) -> str:
    """Return the first line ending style in text, defaulting to LF."""

    for index, char in enumerate(text):
        if char == "\n":
            if index > 0 and text[index - 1] == "\r":
                return "\r\n"
            return "\n"
        if char == "\r":
            next_index = index + 1
            if next_index >= len(text) or text[next_index] != "\n":
                return "\r"
    return "\n"


def parse_quoted_string(
    text: str,
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, str]:
    """Parse a PennMUSH quoted string and return value plus trailing text."""

    if not text.startswith('"'):
        raise ParseError(
            "quoted string must start with a quote",
            source=source,
            line=line,
            expected='leading "',
            actual=text,
        )

    value: list[str] = []
    index = 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return ("".join(value), text[index + 1 :])
        if char == "\\":
            index += 1
            if index >= len(text):
                raise ParseError(
                    "unterminated escape in quoted string",
                    source=source,
                    line=line,
                    expected="escaped character",
                    actual=text,
                )
            value.append(text[index])
        else:
            value.append(char)
        index += 1

    raise ParseError(
        "unterminated quoted string",
        source=source,
        line=line,
        expected='closing "',
        actual=text,
    )


def write_quoted_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def parse_dbref(text: str, *, source: str = "<string>", line: int = 0) -> int:
    if not text.startswith("#"):
        raise ParseError(
            "dbref must start with #",
            source=source,
            line=line,
            expected="#<int>",
            actual=text,
        )
    try:
        return int(text[1:])
    except ValueError as exc:
        raise ParseError(
            "invalid dbref integer",
            source=source,
            line=line,
            expected="#<int>",
            actual=text,
        ) from exc


def write_dbref(dbref: int) -> str:
    return f"#{dbref}"


@overload
def parse_labeled_line(
    line_text: str,
    expected: Literal["raw"],
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, str]: ...


@overload
def parse_labeled_line(
    line_text: str,
    expected: Literal["int", "dbref"],
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, int]: ...


@overload
def parse_labeled_line(
    line_text: str,
    expected: Literal["quoted"],
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, str]: ...


@overload
def parse_labeled_line(
    line_text: str,
    expected: Literal["words"],
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, tuple[str, ...]]: ...


def parse_labeled_line(
    line_text: str,
    expected: LabelValueKind,
    *,
    source: str = "<string>",
    line: int = 0,
) -> tuple[str, str | int | tuple[str, ...]]:
    stripped = line_text.lstrip(" ")
    if not stripped:
        raise ParseError(
            "missing label",
            source=source,
            line=line,
            expected="label",
            actual=line_text,
        )

    parts = stripped.split(maxsplit=1)
    label = parts[0]
    value_text = parts[1] if len(parts) == 2 else ""

    if expected == "raw":
        return (label, value_text)
    if expected == "int":
        return (label, _parse_int(value_text, source=source, line=line))
    if expected == "dbref":
        return (label, parse_dbref(value_text, source=source, line=line))
    if expected == "quoted":
        value, trailing = parse_quoted_string(value_text, source=source, line=line)
        if trailing.strip(" "):
            raise ParseError(
                "unexpected trailing text after quoted value",
                source=source,
                line=line,
                expected="end of line",
                actual=trailing,
            )
        return (label, value)
    return (label, tuple(value_text.split()))


def format_labeled_line(label: str, value: str | int | Sequence[str]) -> str:
    if isinstance(value, int):
        return f"{label} {value}"
    if isinstance(value, str):
        return f"{label} {value}"
    return f"{label} {' '.join(value)}"


def decode_db_header(header: str, *, source: str = "<string>", line: int = 0) -> int:
    if not header.startswith("+V"):
        raise ParseError(
            "invalid DB header",
            source=source,
            line=line,
            expected="+V<int>",
            actual=header,
        )
    try:
        encoded = int(header[2:])
    except ValueError as exc:
        raise ParseError(
            "invalid DB header integer",
            source=source,
            line=line,
            expected="+V<int>",
            actual=header,
        ) from exc

    adjusted = _to_unsigned_32(encoded) - 2
    if adjusted % 256 != 0:
        raise ParseError(
            "DB header does not encode whole DB flags",
            source=source,
            line=line,
            expected="+V encoded as ((flags + 5) * 256) + 2",
            actual=header,
        )
    return (adjusted // 256) - 5


def encode_db_header(raw_dbflags: int) -> str:
    encoded = ((raw_dbflags + 5) * 256) + 2
    return f"+V{_to_signed_32(encoded)}"


def is_end_marker(line_text: str) -> bool:
    stripped = line_text.strip()
    return stripped in {END_MARKER_CURRENT, END_MARKER_OLD}


def write_end_marker(style: EndMarkerStyle = "current") -> str:
    if style == "current":
        return END_MARKER_CURRENT
    return END_MARKER_OLD


def require_end_marker(
    line_text: str,
    *,
    source: str = "<string>",
    line: int = 0,
) -> None:
    if not is_end_marker(line_text):
        raise ParseError(
            "missing end marker",
            source=source,
            line=line,
            expected=f"{END_MARKER_CURRENT} or {END_MARKER_OLD}",
            actual=line_text,
        )


def _parse_int(text: str, *, source: str, line: int) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise ParseError(
            "invalid integer",
            source=source,
            line=line,
            expected="<int>",
            actual=text,
        ) from exc


def _to_unsigned_32(value: int) -> int:
    if value < 0:
        return value + UINT32_MODULUS
    return value


def _to_signed_32(value: int) -> int:
    wrapped = value % UINT32_MODULUS
    if wrapped >= INT32_SIGN_BIT:
        return wrapped - UINT32_MODULUS
    return wrapped
