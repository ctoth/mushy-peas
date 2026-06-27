import pytest

from mushy_peas.constants import END_MARKER_CURRENT, END_MARKER_OLD
from mushy_peas.errors import ParseError
from mushy_peas.primitives import (
    LineReader,
    decode_db_header,
    detect_line_ending,
    encode_db_header,
    is_end_marker,
    parse_dbref,
    parse_labeled_line,
    parse_quoted_string,
    require_end_marker,
    write_dbref,
    write_end_marker,
    write_quoted_string,
)


def test_detects_line_endings() -> None:
    assert detect_line_ending("one\ntwo\n") == "\n"
    assert detect_line_ending("one\r\ntwo\r\n") == "\r\n"
    assert detect_line_ending("one\rtwo\r") == "\r"
    assert detect_line_ending("one") == "\n"


def test_line_reader_tracks_lines_and_source() -> None:
    reader = LineReader("one\ntwo\n", source="fixture.db")

    assert reader.line_ending == "\n"
    assert reader.line_number == 0
    assert reader.peek_line() == "one"
    assert reader.read_line() == "one"
    assert reader.line_number == 1
    assert reader.read_line() == "two"
    assert reader.eof()

    with pytest.raises(ParseError, match=r"fixture\.db:3"):
        reader.read_line()


def test_quoted_string_read_write() -> None:
    value, trailing = parse_quoted_string(r'"a \"quote\" and \\ slash" rest')

    assert value == 'a "quote" and \\ slash'
    assert trailing == " rest"
    assert write_quoted_string(value) == r'"a \"quote\" and \\ slash"'


def test_quoted_string_preserves_non_special_escapes_as_character() -> None:
    value, trailing = parse_quoted_string(r'"a\q\b"')

    assert value == "aqb"
    assert trailing == ""


def test_quoted_string_requires_leading_quote() -> None:
    with pytest.raises(ParseError, match="quoted string must start"):
        parse_quoted_string("not quoted")


def test_labeled_lines_with_leading_spaces() -> None:
    assert parse_labeled_line("  owner #-1", "dbref") == ("owner", -1)
    assert parse_labeled_line("  pennies 123", "int") == ("pennies", 123)
    assert parse_labeled_line("  name \"The Room\"", "quoted") == (
        "name",
        "The Room",
    )
    assert parse_labeled_line("  flags WIZARD ROYALTY", "words") == (
        "flags",
        ("WIZARD", "ROYALTY"),
    )
    assert parse_labeled_line("  key #0&!#1", "raw") == ("key", "#0&!#1")


def test_dbref_parse_and_write() -> None:
    for dbref in (0, 1, -1, -2, 123456):
        assert parse_dbref(write_dbref(dbref)) == dbref


def test_dbref_requires_hash() -> None:
    with pytest.raises(ParseError, match="dbref must start"):
        parse_dbref("-1")


def test_db_header_decode_encode_known_roundtrip() -> None:
    for flags in (0, 1, 2, 256, -1, 0xFFFF):
        assert decode_db_header(encode_db_header(flags)) == flags


def test_db_header_rejects_bad_prefix() -> None:
    with pytest.raises(ParseError, match="invalid DB header"):
        decode_db_header("+X1282")


def test_end_markers_parse_and_write() -> None:
    assert is_end_marker(END_MARKER_CURRENT)
    assert is_end_marker(END_MARKER_OLD)
    assert write_end_marker("current") == END_MARKER_CURRENT
    assert write_end_marker("old") == END_MARKER_OLD
    require_end_marker(END_MARKER_CURRENT)
    require_end_marker(END_MARKER_OLD)


def test_require_end_marker_rejects_other_text() -> None:
    with pytest.raises(ParseError, match="missing end marker"):
        require_end_marker("***DONE***")


def test_errors_include_line_context() -> None:
    def parse_bad_dbref() -> int:
        return parse_dbref("x", source="db", line=9)

    with pytest.raises(ParseError, match="db:9"):
        parse_bad_dbref()
