from hypothesis import given
from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from mushy_peas.chat_model import PennChannel, PennChannelUser, PennChatDatabase
from mushy_peas.chat_reader import read_chat_database_text
from mushy_peas.chat_writer import CHAT_LOCK_ORDER, write_chat_database_text
from mushy_peas.oldstyle import read_oldstyle_chat_database_text
from tests.strategies import dbrefs, quoted_text


def channel_users() -> SearchStrategy[PennChannelUser]:
    return st.builds(
        PennChannelUser,
        dbref=dbrefs(),
        flags=st.integers(min_value=0, max_value=2**16),
        title=quoted_text(),
    )


def lock_maps() -> SearchStrategy[dict[str, str]]:
    return st.fixed_dictionaries(
        {lock_name: quoted_text() for lock_name in CHAT_LOCK_ORDER}
    )


def channels() -> SearchStrategy[PennChannel]:
    return st.builds(
        PennChannel,
        name=quoted_text(),
        description=quoted_text(),
        flags=st.integers(min_value=0, max_value=2**16),
        creator=dbrefs(),
        cost=st.integers(min_value=0, max_value=2**16),
        buffer_blocks=st.integers(min_value=0, max_value=100),
        mogrifier=dbrefs(),
        locks=lock_maps(),
        users=st.lists(channel_users(), max_size=5),
    )


def test_writer_output_for_empty_chat_database_matches_expected_text() -> None:
    database = PennChatDatabase(raw_chat_flags=0, savedtime="now")

    assert write_chat_database_text(database) == "\n".join(
        ("+V1", 'savedtime "now"', "channels 0", "***END OF DUMP***", "")
    )


def test_writer_output_for_channel_matches_expected_text() -> None:
    database = PennChatDatabase(
        raw_chat_flags=0,
        savedtime="now",
        channels=[
            PennChannel(
                name='Public "Main"',
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
        ],
    )

    assert write_chat_database_text(database) == "\n".join(
        (
            "+V1",
            'savedtime "now"',
            "channels 1",
            ' name "Public \\"Main\\""',
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


def test_oldstyle_chat_database_writes_as_current_chat_database() -> None:
    oldstyle = read_oldstyle_chat_database_text(
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
                "0",
                "***END OF DUMP***",
                "",
            )
        )
    )

    upgraded = read_chat_database_text(write_chat_database_text(oldstyle))

    assert upgraded.format_kind == "chat-current"
    assert len(upgraded.channels) == 1
    assert len(oldstyle.channels) == 1
    upgraded_channel = upgraded.channels[0]
    oldstyle_channel = oldstyle.channels[0]
    assert upgraded_channel.name == oldstyle_channel.name
    assert upgraded_channel.description == oldstyle_channel.description
    assert upgraded_channel.flags == oldstyle_channel.flags
    assert upgraded_channel.creator == oldstyle_channel.creator
    assert upgraded_channel.cost == oldstyle_channel.cost
    assert upgraded_channel.locks == oldstyle_channel.locks
    assert upgraded_channel.users == oldstyle_channel.users
    assert upgraded_channel.buffer_blocks == 0
    assert upgraded_channel.mogrifier == -1


@given(st.lists(channels(), max_size=5))
def test_generated_chat_databases_write_and_read_back(
    generated_channels: list[PennChannel],
) -> None:
    source = PennChatDatabase(
        raw_chat_flags=0,
        savedtime="now",
        channels=generated_channels,
    )

    parsed = read_chat_database_text(write_chat_database_text(source))

    assert parsed.savedtime == source.savedtime
    assert parsed.channels == source.channels
