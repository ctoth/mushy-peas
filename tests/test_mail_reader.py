import pytest

from mushy_peas.errors import ParseError
from mushy_peas.mail_model import PennMailAlias, PennMailMessage
from mushy_peas.mail_reader import read_mail_database_text


def test_reads_current_empty_mail_database() -> None:
    database = read_mail_database_text(
        "\n".join(
            (
                "+15",
                "0",
                '"*** End of MALIAS ***"',
                "0",
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.raw_mail_flags == 15
    assert database.aliases == []
    assert database.messages == []
    assert database.eod == "***END OF DUMP***"


def test_reads_current_aliases_and_messages() -> None:
    database = read_mail_database_text(
        "\n".join(
            (
                "+15",
                "1",
                "1",
                '"builders"',
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
                '"Subject \\"A\\""',
                '"Body text"',
                "8",
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.aliases == [
        PennMailAlias(
            owner=1,
            name="builders",
            description="Build team",
            name_flags=2,
            member_flags=4,
            members=(1, 2),
        )
    ]
    assert database.messages == [
        PennMailMessage(
            to=2,
            from_=1,
            from_ctime=100,
            time_text="Fri Jan 01 00:00:00 2026",
            subject='Subject "A"',
            body="Body text",
            read_flags=8,
        )
    ]


def test_reads_legacy_mail_database_without_subject_or_sender_ctime() -> None:
    database = read_mail_database_text(
        "\n".join(
            (
                "1",
                "2",
                "1",
                '"Fri Jan 01 00:00:00 2026"',
                '"Legacy body"',
                "0",
                "*** END OF DUMP ***",
                "",
            )
        )
    )

    assert database.raw_mail_flags == 0
    assert database.messages == [
        PennMailMessage(
            to=2,
            from_=1,
            from_ctime=0,
            time_text="Fri Jan 01 00:00:00 2026",
            subject="",
            body="Legacy body",
            read_flags=0,
        )
    ]


def test_reads_subjectless_flagged_mail_database() -> None:
    database = read_mail_database_text(
        "\n".join(
            (
                "+14",
                "0",
                '"*** End of MALIAS ***"',
                "1",
                "2",
                "1",
                "100",
                '"Fri Jan 01 00:00:00 2026"',
                '"Body only"',
                "0",
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.messages[0].subject == ""
    assert database.messages[0].body == "Body only"


def test_alias_marker_must_match_source_marker() -> None:
    with pytest.raises(ParseError, match="bad mail alias end marker"):
        read_mail_database_text(
            "\n".join(("+15", "0", '"wrong"', "0", "***END OF DUMP***", ""))
        )


def test_eod_style_follows_mail_flags() -> None:
    with pytest.raises(ParseError, match="bad mail end marker"):
        read_mail_database_text(
            "\n".join(
                (
                    "+15",
                    "0",
                    '"*** End of MALIAS ***"',
                    "0",
                    "*** END OF DUMP ***",
                    "",
                )
            )
        )
