from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mushy_peas.errors import ParseError
from mushy_peas.main_model import PennAttribute, PennFlag
from mushy_peas.main_reader import read_main_header_and_global_lists_text
from mushy_peas.main_writer import write_attribute_section, write_flag_section


def test_reads_global_sections_from_fixture() -> None:
    text = Path("tests/fixtures/main/global_lists.db").read_text(encoding="utf-8")

    database = read_main_header_and_global_lists_text(
        text,
        source="tests/fixtures/main/global_lists.db",
    )

    assert database.raw_dbflags == 0
    assert database.dbversion == 6
    assert database.savedtime == "Fri Jan 01 00:00:00 2026"
    assert database.object_count == 0
    assert database.flags["WIZARD"] == PennFlag(
        name="WIZARD",
        letter="W",
        types=("ROOM", "PLAYER"),
        perms=("trusted",),
        negate_perms=("guest",),
        aliases=("ROYALTY",),
    )
    assert database.powers["BOOT"].aliases == ("KICK",)
    assert database.attributes["DESCRIBE"] == PennAttribute(
        name="DESCRIBE",
        flags=("wizard", "visual"),
        creator=1,
        data="",
        aliases=("DESC",),
    )


def test_global_section_labels_must_be_exact() -> None:
    text = """+V1282
dbversion 6
savedtime "now"
+FLAGS LIST
flagcount 1
 wrong "WIZARD"
  letter "W"
  type ""
  perms ""
  negate_perms ""
flagaliascount 0
~0
"""

    with pytest.raises(ParseError, match="unexpected label"):
        read_main_header_and_global_lists_text(text, source="bad.db")


def test_alias_entries_must_attach_to_existing_canonical_item() -> None:
    text = """+V1282
savedtime "now"
+FLAGS LIST
flagcount 0
flagaliascount 1
 name "MISSING"
  alias "ALIAS"
~0
"""

    with pytest.raises(ParseError, match="flag alias target is missing"):
        read_main_header_and_global_lists_text(text, source="bad-alias.db")


def test_unknown_global_list_fails_with_line_context() -> None:
    text = """+V1282
savedtime "now"
+UNKNOWN LIST
~0
"""

    with pytest.raises(ParseError, match=r"bad-list\.db:3"):
        read_main_header_and_global_lists_text(text, source="bad-list.db")


@given(st.data())
def test_generated_flag_sections_parse_and_reemit_stably(data: st.DataObject) -> None:
    flags = data.draw(flag_maps(), label="flags")
    section = write_flag_section("+FLAGS LIST", flags)
    text = "\n".join(
        (
            "+V1282",
            'savedtime "now"',
            section,
            "~0",
            "",
        )
    )

    first = read_main_header_and_global_lists_text(text).flags
    second_text = "\n".join(
        (
            "+V1282",
            'savedtime "now"',
            write_flag_section("+FLAGS LIST", first),
            "~0",
            "",
        )
    )
    second = read_main_header_and_global_lists_text(second_text).flags

    assert second == first


@given(st.data())
def test_generated_attribute_sections_parse_and_reemit_stably(
    data: st.DataObject,
) -> None:
    attributes = data.draw(attribute_maps(), label="attributes")
    section = write_attribute_section(attributes)
    text = "\n".join(
        (
            "+V1282",
            'savedtime "now"',
            section,
            "~0",
            "",
        )
    )

    first = read_main_header_and_global_lists_text(text).attributes
    second_text = "\n".join(
        (
            "+V1282",
            'savedtime "now"',
            write_attribute_section(first),
            "~0",
            "",
        )
    )
    second = read_main_header_and_global_lists_text(second_text).attributes

    assert second == first


def names() -> st.SearchStrategy[str]:
    return st.from_regex(r"[A-Z][A-Z0-9_]{0,10}", fullmatch=True)


def word_tuples() -> st.SearchStrategy[tuple[str, ...]]:
    return st.lists(names(), max_size=4, unique=True).map(tuple)


def flag_maps() -> st.SearchStrategy[dict[str, PennFlag]]:
    def build_flag(name: str, aliases: tuple[str, ...]) -> PennFlag:
        return PennFlag(
            name=name,
            letter=name[:1],
            types=("ROOM",),
            perms=("trusted",),
            negate_perms=(),
            aliases=aliases,
        )

    return st.dictionaries(
        names(),
        st.lists(names(), max_size=2, unique=True).map(tuple),
        max_size=5,
    ).map(
        lambda items: {
            name: build_flag(name, aliases) for name, aliases in items.items()
        }
    )


def attribute_maps() -> st.SearchStrategy[dict[str, PennAttribute]]:
    def build_attribute(
        name: str,
        values: tuple[tuple[str, ...], tuple[str, ...]],
    ) -> PennAttribute:
        flags, aliases = values
        return PennAttribute(
            name=name,
            flags=flags,
            creator=1,
            data="",
            aliases=aliases,
        )

    return st.dictionaries(
        names(),
        st.tuples(word_tuples(), st.lists(names(), max_size=2, unique=True).map(tuple)),
        max_size=5,
    ).map(
        lambda items: {
            name: build_attribute(name, values) for name, values in items.items()
        }
    )
