from hypothesis import given
from hypothesis import strategies as st

from mushy_peas.constants import CURRENT_MAIN_DB_FLAGS
from mushy_peas.main_model import PennAttribute, PennLock, PennMainDatabase, PennObject
from mushy_peas.main_reader import read_main_database_text
from mushy_peas.main_writer import write_main_database_text
from mushy_peas.primitives import encode_db_header
from tests.test_main_reader import objects


def test_writer_output_for_controlled_fixture_matches_expected_text() -> None:
    database = PennMainDatabase(
        raw_dbflags=0,
        dbversion=6,
        savedtime="Fri Jan 01 00:00:00 2026",
        object_count=1,
        objects={
            0: PennObject(
                dbref=0,
                name='Room "Zero"',
                location=-1,
                contents=-1,
                exits=-1,
                next=-1,
                parent=-1,
                owner=1,
                zone=-1,
                pennies=0,
                type=1,
                flags=("WIZARD",),
                powers=(),
                warnings=(),
                created=100,
                modified=101,
            )
        },
    )

    expected = "\n".join(
        (
            encode_db_header(CURRENT_MAIN_DB_FLAGS),
            "dbversion 6",
            'savedtime "Fri Jan 01 00:00:00 2026"',
            "+FLAGS LIST",
            "flagcount 0",
            "flagaliascount 0",
            "+POWER LIST",
            "flagcount 0",
            "flagaliascount 0",
            "+ATTRIBUTES LIST",
            "attrcount 0",
            "attraliascount 0",
            "~1",
            "!0",
            'name "Room \\"Zero\\""',
            "location #-1",
            "contents #-1",
            "exits #-1",
            "next #-1",
            "parent #-1",
            "lockcount 0",
            "owner #1",
            "zone #-1",
            "pennies 0",
            "type 1",
            'flags "WIZARD"',
            'powers ""',
            'warnings ""',
            "created 100",
            "modified 101",
            "attrcount 0",
            "***END OF DUMP***",
            "",
        )
    )

    assert write_main_database_text(database) == expected


def test_writer_output_can_be_parsed_by_reader() -> None:
    source = PennMainDatabase(
        raw_dbflags=0,
        dbversion=6,
        savedtime="now",
        object_count=3,
        objects={
            0: PennObject(
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
                        creator=1,
                        flags=("visual",),
                        derefs=0,
                        key="#1",
                    )
                },
                owner=1,
                zone=-1,
                pennies=0,
                type=1,
                flags=(),
                powers=(),
                warnings=(),
                created=10,
                modified=11,
                attributes={
                    "DESCRIBE": PennAttribute(
                        name="DESCRIBE",
                        flags=("wizard",),
                        creator=1,
                        data="A room",
                        derefs=1,
                    )
                },
            ),
            2: PennObject(
                dbref=2,
                name="Player Two",
                location=0,
                contents=-1,
                exits=-1,
                next=-1,
                parent=-1,
                owner=2,
                zone=-1,
                pennies=10,
                type=8,
                flags=("CONNECTED",),
                powers=("BOOT",),
                warnings=("NO_LOG",),
                created=20,
                modified=21,
            ),
        },
    )

    parsed = read_main_database_text(write_main_database_text(source))

    assert parsed.savedtime == source.savedtime
    assert parsed.object_count == source.object_count
    assert parsed.objects == source.objects
    assert 1 not in parsed.objects


def test_writer_skips_explicit_garbage_objects() -> None:
    database = PennMainDatabase(
        raw_dbflags=0,
        dbversion=6,
        savedtime="now",
        object_count=1,
        objects={
            0: PennObject(
                dbref=0,
                name="Garbage",
                location=-1,
                contents=-1,
                exits=-1,
                next=-1,
                parent=-1,
                type=16,
            )
        },
    )

    parsed = read_main_database_text(write_main_database_text(database))

    assert parsed.object_count == 1
    assert parsed.objects == {}


@given(st.lists(objects(), max_size=5, unique_by=lambda obj: obj.dbref))
def test_generated_small_databases_write_and_read_back(
    generated_objects: list[PennObject],
) -> None:
    if generated_objects:
        object_count = max(obj.dbref for obj in generated_objects) + 1
    else:
        object_count = 0
    source = PennMainDatabase(
        raw_dbflags=0,
        dbversion=6,
        savedtime="now",
        object_count=object_count,
        objects={obj.dbref: obj for obj in generated_objects},
    )

    parsed = read_main_database_text(write_main_database_text(source))

    assert parsed.objects == {
        dbref: obj for dbref, obj in source.objects.items() if obj.type != 16
    }
