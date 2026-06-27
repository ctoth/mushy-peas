import pytest

from mushy_peas.chat_model import PennChannel, PennChannelUser
from mushy_peas.chat_reader import read_chat_database_text
from mushy_peas.errors import ParseError


def test_reads_empty_current_chat_database() -> None:
    database = read_chat_database_text(
        "\n".join(("+V1", 'savedtime "now"', "channels 0", "***END OF DUMP***", ""))
    )

    assert database.raw_chat_flags == 1
    assert database.savedtime == "now"
    assert database.channels == []


def test_reads_current_channel_with_locks_and_users() -> None:
    database = read_chat_database_text(
        "\n".join(
            (
                "+V1",
                'savedtime "Fri Jan 01 00:00:00 2026"',
                "channels 1",
                ' name "Public"',
                '  description "Public channel"',
                "  flags 2",
                "  creator #1",
                "  cost 10",
                "  buffer 3",
                "  mogrifier #-1",
                '  lock "join"',
                '  key "*UNLOCKED*"',
                '  lock "speak"',
                '  key "#1"',
                '  lock "modify"',
                '  key "#2"',
                '  lock "see"',
                '  key "#3"',
                '  lock "hide"',
                '  key "#4"',
                "  users 1",
                "   dbref #1",
                "    flags 8",
                '    title "Builder"',
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.channels == [
        PennChannel(
            name="Public",
            description="Public channel",
            flags=2,
            creator=1,
            cost=10,
            buffer_blocks=3,
            mogrifier=-1,
            locks={
                "join": "*UNLOCKED*",
                "speak": "#1",
                "modify": "#2",
                "see": "#3",
                "hide": "#4",
            },
            users=[PennChannelUser(dbref=1, flags=8, title="Builder")],
        )
    ]


def test_reads_non_spiffy_current_chat_database() -> None:
    database = read_chat_database_text(
        "\n".join(
            (
                "+V0",
                'savedtime "now"',
                "channels 1",
                ' name "Plain"',
                '  description ""',
                "  flags 0",
                "  creator #-1",
                "  cost 0",
                "  users 0",
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.channels[0].buffer_blocks is None
    assert database.channels[0].mogrifier is None
    assert database.channels[0].locks == {}


def test_reads_oldstyle_chat_database_through_chat_reader_fallback() -> None:
    database = read_chat_database_text(
        "\n".join(
            (
                "1",
                '"Public"',
                '"Old public channel"',
                "2",
                "1",
                "10",
                'key "*UNLOCKED*"',
                'key "#1"',
                'key "#2"',
                'key "#3"',
                'key "#4"',
                "1",
                "1",
                "8",
                '"Builder"',
                "***END OF DUMP***",
                "",
            )
        )
    )

    assert database.format_kind == "chat-oldstyle"
    assert database.savedtime is None
    assert database.channels == [
        PennChannel(
            name="Public",
            description="Old public channel",
            flags=2,
            creator=1,
            cost=10,
            locks={
                "join": "*UNLOCKED*",
                "speak": "#1",
                "modify": "#2",
                "see": "#3",
                "hide": "#4",
            },
            users=[PennChannelUser(dbref=1, flags=8, title="Builder")],
        )
    ]


def test_current_chat_database_must_start_with_chat_header() -> None:
    with pytest.raises(ParseError, match="unsupported chat database format"):
        read_chat_database_text("+X\n")


def test_channel_labels_must_match_source_format() -> None:
    with pytest.raises(ParseError, match="unexpected label"):
        read_chat_database_text(
            "\n".join(
                (
                    "+V1",
                    'savedtime "now"',
                    "channel_count 0",
                    "***END OF DUMP***",
                    "",
                )
            )
        )
