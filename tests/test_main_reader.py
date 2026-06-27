from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mushy_peas.errors import ParseError
from mushy_peas.main_model import PennAttribute, PennFlag, PennLock, PennObject
from mushy_peas.main_reader import (
    read_main_database_text,
    read_main_header_and_global_lists_text,
)
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


def test_reads_current_object_records_from_fixture() -> None:
    text = Path("tests/fixtures/main/current_objects.db").read_text(encoding="utf-8")

    database = read_main_database_text(
        text,
        source="tests/fixtures/main/current_objects.db",
    )

    assert database.object_count == 3
    assert set(database.objects) == {0, 2}
    assert database.objects[0] == PennObject(
        dbref=0,
        name="Room Zero",
        location=-1,
        contents=-1,
        exits=-1,
        next=-1,
        parent=-1,
        owner=1,
        zone=-1,
        pennies=0,
        type=1,
        created=100,
        modified=101,
    )
    assert database.objects[2].locks == {
        "Basic": PennLock(
            type="Basic",
            creator=2,
            flags=("visual",),
            derefs=0,
            key="#2",
        ),
        "Use": PennLock(
            type="Use",
            creator=2,
            flags=(),
            derefs=1,
            key="#0&!#1",
        ),
    }
    assert database.objects[2].attributes == {
        "DESCRIBE": PennAttribute(
            name="DESCRIBE",
            flags=("wizard",),
            creator=2,
            data="A player",
            derefs=1,
        )
    }


def test_invalid_object_label_fails_with_line_context() -> None:
    text = """+V1282
savedtime "now"
~1
!0
wrong "Room"
location #-1
contents #-1
exits #-1
next #-1
parent #-1
lockcount 0
owner #1
zone #-1
pennies 0
type 1
flags ""
powers ""
warnings ""
created 0
modified 0
attrcount 0
***END OF DUMP***
"""

    with pytest.raises(ParseError, match=r"bad-object\.db:5"):
        read_main_database_text(text, source="bad-object.db")


def test_duplicate_object_record_fails() -> None:
    text = _minimal_database(
        "\n".join(
            (
                "!0",
                _minimal_object_body("Room One"),
                "!0",
                _minimal_object_body("Room Two"),
                "***END OF DUMP***",
            )
        ),
        object_count=1,
    )

    with pytest.raises(ParseError, match="duplicate object record"):
        read_main_database_text(text)


def test_object_record_outside_capacity_fails() -> None:
    text = _minimal_database(
        "\n".join(
            (
                "!1",
                _minimal_object_body("Outside"),
                "***END OF DUMP***",
            )
        ),
        object_count=1,
    )

    with pytest.raises(ParseError, match="outside declared capacity"):
        read_main_database_text(text)


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


@given(st.data())
def test_generated_object_records_parse_without_losing_scalars(
    data: st.DataObject,
) -> None:
    obj = data.draw(objects(), label="object")
    text = _minimal_database(
        "\n".join(
            (
                f"!{obj.dbref}",
                format_object_body(obj),
                "***END OF DUMP***",
            )
        ),
        object_count=obj.dbref + 1,
    )

    parsed = read_main_database_text(text).objects[obj.dbref]

    assert parsed == obj


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


def objects() -> st.SearchStrategy[PennObject]:
    return st.builds(
        PennObject,
        dbref=st.integers(min_value=0, max_value=4),
        name=names(),
        location=st.integers(min_value=-1, max_value=4),
        contents=st.integers(min_value=-1, max_value=4),
        exits=st.integers(min_value=-1, max_value=4),
        next=st.integers(min_value=-1, max_value=4),
        parent=st.integers(min_value=-1, max_value=4),
        locks=st.dictionaries(
            names(),
            locks(),
            max_size=3,
        ),
        owner=st.integers(min_value=0, max_value=4),
        zone=st.integers(min_value=-1, max_value=4),
        pennies=st.integers(min_value=0, max_value=100),
        type=st.sampled_from([1, 2, 4, 8, 16]),
        flags=word_tuples(),
        powers=word_tuples(),
        warnings=word_tuples(),
        created=st.integers(min_value=0, max_value=2_000_000_000),
        modified=st.integers(min_value=0, max_value=2_000_000_000),
        attributes=object_attribute_maps(),
    ).map(_sync_lock_keys)


def locks() -> st.SearchStrategy[PennLock]:
    return st.builds(
        PennLock,
        type=names(),
        creator=st.integers(min_value=0, max_value=4),
        flags=word_tuples(),
        derefs=st.integers(min_value=0, max_value=3),
        key=st.sampled_from(["#0", "#1", "#0&!#1"]),
    )


def object_attribute_maps() -> st.SearchStrategy[dict[str, PennAttribute]]:
    def build_attribute(name: str, flags: tuple[str, ...]) -> PennAttribute:
        return PennAttribute(
            name=name,
            flags=flags,
            creator=1,
            data="",
            derefs=1,
        )

    return st.dictionaries(
        names(),
        word_tuples(),
        max_size=5,
    ).map(
        lambda items: {
            name: build_attribute(name, flags) for name, flags in items.items()
        }
    )


def _sync_lock_keys(obj: PennObject) -> PennObject:
    return PennObject(
        dbref=obj.dbref,
        name=obj.name,
        location=obj.location,
        contents=obj.contents,
        exits=obj.exits,
        next=obj.next,
        parent=obj.parent,
        locks={
            lock_type: PennLock(
                type=lock_type,
                creator=lock.creator,
                flags=lock.flags,
                derefs=lock.derefs,
                key=lock.key,
            )
            for lock_type, lock in obj.locks.items()
        },
        owner=obj.owner,
        zone=obj.zone,
        pennies=obj.pennies,
        type=obj.type,
        flags=obj.flags,
        powers=obj.powers,
        warnings=obj.warnings,
        created=obj.created,
        modified=obj.modified,
        attributes=obj.attributes,
    )


def _minimal_database(object_text: str, *, object_count: int) -> str:
    return "\n".join(
        (
            "+V1282",
            'savedtime "now"',
            f"~{object_count}",
            object_text,
            "",
        )
    )


def _minimal_object_body(name: str) -> str:
    return format_object_body(
        PennObject(
            dbref=0,
            name=name,
            location=-1,
            contents=-1,
            exits=-1,
            next=-1,
            parent=-1,
            owner=1,
            zone=-1,
            pennies=0,
            type=1,
            created=0,
            modified=0,
        )
    )


def format_object_body(obj: PennObject) -> str:
    lines = [
        f'name "{obj.name}"',
        f"location #{obj.location}",
        f"contents #{obj.contents}",
        f"exits #{obj.exits}",
        f"next #{obj.next}",
        f"parent #{obj.parent}",
        f"lockcount {len(obj.locks)}",
    ]
    for lock in obj.locks.values():
        lines.extend(
            (
                f' type "{lock.type}"',
                f"  creator #{lock.creator}",
                f'  flags "{" ".join(lock.flags)}"',
                f"  derefs {lock.derefs}",
                f'  key "{lock.key}"',
            )
        )
    lines.extend(
        (
            f"owner #{obj.owner}",
            f"zone #{obj.zone}",
            f"pennies {obj.pennies}",
            f"type {obj.type}",
            f'flags "{" ".join(obj.flags)}"',
            f'powers "{" ".join(obj.powers)}"',
            f'warnings "{" ".join(obj.warnings)}"',
            f"created {obj.created}",
            f"modified {obj.modified}",
            f"attrcount {len(obj.attributes)}",
        )
    )
    for attribute in obj.attributes.values():
        lines.extend(
            (
                f' name "{attribute.name}"',
                f"  owner #{attribute.creator}",
                f'  flags "{" ".join(attribute.flags)}"',
                f"  derefs {attribute.derefs}",
                f'  value "{attribute.data}"',
            )
        )
    return "\n".join(lines)
