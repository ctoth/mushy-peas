from hypothesis import given

from mushy_peas.primitives import (
    decode_db_header,
    encode_db_header,
    parse_dbref,
    parse_quoted_string,
    write_dbref,
    write_quoted_string,
)
from tests.strategies import dbflags, dbrefs, quoted_text


@given(quoted_text())
def test_primitives_quoted_strings_round_trip(value: str) -> None:
    parsed, trailing = parse_quoted_string(write_quoted_string(value))

    assert parsed == value
    assert trailing == ""


@given(quoted_text())
def test_primitives_writer_escapes_raw_quotes(value: str) -> None:
    written = write_quoted_string(value)
    body = written[1:-1]
    index = 0
    while index < len(body):
        if body[index] == '"':
            assert index > 0
            assert body[index - 1] == "\\"
        index += 1


@given(dbflags())
def test_primitives_db_header_round_trip(flags: int) -> None:
    assert decode_db_header(encode_db_header(flags)) == flags


@given(dbrefs())
def test_primitives_dbrefs_round_trip(dbref: int) -> None:
    assert parse_dbref(write_dbref(dbref)) == dbref
