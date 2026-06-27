from pathlib import Path

import pytest

from mushy_peas.errors import ParseError
from mushy_peas.main_model import PennAttribute, PennLock, PennObject
from mushy_peas.main_reader import read_main_database_text
from mushy_peas.main_writer import write_main_database_text
from mushy_peas.oldstyle import read_oldstyle_main_database_text


def test_reads_new_string_oldstyle_main_database_fixture() -> None:
    text = Path("tests/fixtures/oldstyle/new_strings_no_labels.db").read_text(
        encoding="utf-8"
    )

    database = read_oldstyle_main_database_text(
        text,
        source="tests/fixtures/oldstyle/new_strings_no_labels.db",
    )

    assert database.format_kind == "main-oldstyle"
    assert database.object_count == 1
    assert database.objects[0] == PennObject(
        dbref=0,
        name="Room Zero",
        location=-1,
        contents=-1,
        exits=-1,
        next=-1,
        parent=-1,
        locks={
            "Basic": PennLock(
                type="Basic",
                creator=0,
                flags=(),
                derefs=0,
                key="#0",
            )
        },
        owner=1,
        zone=-1,
        pennies=0,
        type=1,
        flags=("WIZARD",),
        powers=(),
        warnings=(),
        created=100,
        modified=101,
        attributes={
            "DESCRIBE": PennAttribute(
                name="DESCRIBE",
                flags=(),
                creator=1,
                data="A room",
                derefs=1,
            )
        },
    )


def test_oldstyle_input_writes_as_current_labeled_format() -> None:
    text = Path("tests/fixtures/oldstyle/new_strings_no_labels.db").read_text(
        encoding="utf-8"
    )
    oldstyle_database = read_oldstyle_main_database_text(text)

    upgraded_text = write_main_database_text(oldstyle_database)
    upgraded_database = read_main_database_text(upgraded_text)

    assert upgraded_text.startswith("+V")
    assert "dbversion 6\n" in upgraded_text
    assert "+FLAGS LIST\n" in upgraded_text
    assert "name \"Room Zero\"\n" in upgraded_text
    assert upgraded_database.objects == oldstyle_database.objects


def test_oldstyle_reader_rejects_labeled_current_database() -> None:
    source_text = Path("tests/fixtures/main/current_objects.db").read_text(
        encoding="utf-8"
    )
    text = write_main_database_text(read_main_database_text(source_text))

    with pytest.raises(ParseError, match="without DBF_LABELS"):
        read_oldstyle_main_database_text(text)


def test_oldstyle_numeric_flag_conversion_is_explicitly_unsupported() -> None:
    text = """+V1282
~1
!0
Room
-1
-1
-1
-1
-1



1
-1
0
1
0
<
***END OF DUMP***
"""

    with pytest.raises(ParseError, match="old numeric flag conversion"):
        read_oldstyle_main_database_text(text)
