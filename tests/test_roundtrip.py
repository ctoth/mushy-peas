from pathlib import Path

from mushy_peas.chat_reader import read_chat_database, read_chat_database_text
from mushy_peas.chat_writer import write_chat_database_text
from mushy_peas.mail_reader import read_mail_database, read_mail_database_text
from mushy_peas.mail_writer import write_mail_database_text
from mushy_peas.main_reader import read_main_database, read_main_database_text
from mushy_peas.main_writer import write_main_database, write_main_database_text
from mushy_peas.oldstyle import read_oldstyle_main_database


def test_current_main_fixture_read_write_read() -> None:
    source = read_main_database("tests/fixtures/main/current_objects.db")

    parsed = read_main_database_text(write_main_database_text(source))

    assert parsed.object_count == source.object_count
    assert parsed.objects == source.objects


def test_oldstyle_main_fixture_upgrades_then_read_write_reads() -> None:
    source = read_oldstyle_main_database(
        "tests/fixtures/oldstyle/new_strings_no_labels.db"
    )

    upgraded = read_main_database_text(write_main_database_text(source))
    parsed = read_main_database_text(write_main_database_text(upgraded))

    assert upgraded.format_kind == "main-current"
    assert parsed.objects == source.objects


def test_mail_fixture_read_write_read() -> None:
    source = read_mail_database("tests/fixtures/mail/current_with_alias_message.db")

    parsed = read_mail_database_text(write_mail_database_text(source))

    assert parsed.aliases == source.aliases
    assert parsed.messages == source.messages


def test_current_chat_fixture_read_write_read() -> None:
    source = read_chat_database("tests/fixtures/chat/current_channel.db")

    parsed = read_chat_database_text(write_chat_database_text(source))

    assert parsed.channels == source.channels


def test_oldstyle_chat_fixture_upgrades_then_read_write_reads() -> None:
    source = read_chat_database("tests/fixtures/chat/oldstyle_channel.db")

    upgraded = read_chat_database_text(write_chat_database_text(source))
    parsed = read_chat_database_text(write_chat_database_text(upgraded))

    assert upgraded.format_kind == "chat-current"
    assert len(source.channels) == 1
    assert len(parsed.channels) == 1
    source_channel = source.channels[0]
    parsed_channel = parsed.channels[0]
    assert parsed_channel.name == source_channel.name
    assert parsed_channel.description == source_channel.description
    assert parsed_channel.flags == source_channel.flags
    assert parsed_channel.creator == source_channel.creator
    assert parsed_channel.cost == source_channel.cost
    assert parsed_channel.locks == source_channel.locks
    assert parsed_channel.users == source_channel.users
    assert parsed_channel.buffer_blocks == 0
    assert parsed_channel.mogrifier == -1


def test_main_fixture_round_trips_through_gzip_and_bzip2(tmp_path: Path) -> None:
    source = read_main_database("tests/fixtures/main/current_objects.db")
    gzip_path = tmp_path / "indb.gz"
    bzip2_path = tmp_path / "indb.bz2"

    write_main_database(gzip_path, source)
    write_main_database(bzip2_path, source)

    assert read_main_database(gzip_path).objects == source.objects
    assert read_main_database(bzip2_path).objects == source.objects
