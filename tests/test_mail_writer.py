from hypothesis import given
from hypothesis import strategies as st

from mushy_peas.mail_model import PennMailAlias, PennMailDatabase, PennMailMessage
from mushy_peas.mail_reader import read_mail_database_text
from mushy_peas.mail_writer import write_mail_database_text
from tests.strategies import dbrefs, quoted_text


def aliases() -> st.SearchStrategy[PennMailAlias]:
    return st.builds(
        PennMailAlias,
        owner=dbrefs(),
        name=quoted_text(),
        description=quoted_text(),
        name_flags=st.integers(min_value=0, max_value=2**16),
        member_flags=st.integers(min_value=0, max_value=2**16),
        members=st.lists(dbrefs(), max_size=5).map(tuple),
    )


def messages() -> st.SearchStrategy[PennMailMessage]:
    return st.builds(
        PennMailMessage,
        to=dbrefs(),
        from_=dbrefs(),
        from_ctime=st.integers(min_value=0, max_value=2**31 - 1),
        time_text=quoted_text(),
        subject=quoted_text(),
        body=quoted_text(),
        read_flags=st.integers(min_value=0, max_value=2**16),
    )


def test_writer_output_for_empty_mail_database_matches_expected_text() -> None:
    database = PennMailDatabase(raw_mail_flags=0)

    assert write_mail_database_text(database) == "\n".join(
        (
            "+15",
            "0",
            '"*** End of MALIAS ***"',
            "0",
            "***END OF DUMP***",
            "",
        )
    )


def test_writer_output_for_alias_and_message_matches_expected_text() -> None:
    database = PennMailDatabase(
        raw_mail_flags=0,
        aliases=[
            PennMailAlias(
                owner=1,
                name='builders "north"',
                description="Build team",
                name_flags=2,
                member_flags=4,
                members=(1, 2),
            )
        ],
        messages=[
            PennMailMessage(
                to=2,
                from_=1,
                from_ctime=100,
                time_text="Fri Jan 01 00:00:00 2026",
                subject="Project",
                body="Body text",
                read_flags=8,
            )
        ],
    )

    assert write_mail_database_text(database) == "\n".join(
        (
            "+15",
            "1",
            "1",
            '"builders \\"north\\""',
            '"Build team"',
            "2",
            "4",
            "2",
            "1",
            "2",
            '"*** End of MALIAS ***"',
            "1",
            "2",
            "1",
            "100",
            '"Fri Jan 01 00:00:00 2026"',
            '"Project"',
            '"Body text"',
            "8",
            "***END OF DUMP***",
            "",
        )
    )


@given(
    st.lists(aliases(), max_size=4),
    st.lists(messages(), max_size=6),
)
def test_generated_mail_databases_write_and_read_back(
    generated_aliases: list[PennMailAlias],
    generated_messages: list[PennMailMessage],
) -> None:
    source = PennMailDatabase(
        raw_mail_flags=0,
        aliases=generated_aliases,
        messages=generated_messages,
    )

    parsed = read_mail_database_text(write_mail_database_text(source))

    assert parsed.aliases == source.aliases
    assert parsed.messages == source.messages
