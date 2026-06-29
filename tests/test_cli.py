import json
from pathlib import Path
from typing import cast

import pytest

from mushy_peas.chat_model import PennChannel, PennChatDatabase
from mushy_peas.chat_reader import read_chat_database
from mushy_peas.chat_writer import write_chat_database_text
from mushy_peas.cli import (
    main,
    mush_dump_json,
    mush_inspect,
    mush_roundtrip,
    mush_softcode_coverage,
    mush_softcode_graph,
    mush_upgrade,
)
from mushy_peas.mail_model import PennMailAlias, PennMailDatabase, PennMailMessage
from mushy_peas.mail_writer import write_mail_database_text
from mushy_peas.main_model import PennMainDatabase, PennObject
from mushy_peas.main_reader import read_main_database
from mushy_peas.main_writer import write_main_database_text


def test_inspect_auto_reports_main_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "indb"
    path.write_text(write_main_database_text(_main_database()), encoding="utf-8")

    assert mush_inspect([str(path), "--kind", "auto"]) == 0

    output = capsys.readouterr().out
    assert "kind: main\n" in output
    assert "dbversion: 6\n" in output
    assert "object_count: 1\n" in output
    assert "non_garbage_count: 1\n" in output


def test_roundtrip_writes_output_and_reports_line_differences(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "indb"
    out_path = tmp_path / "outdb"
    path.write_text(write_main_database_text(_main_database()), encoding="utf-8")

    assert mush_roundtrip([str(path), "--kind", "main", "--out", str(out_path)]) == 0

    output = capsys.readouterr().out
    assert "kind: main\n" in output
    assert f"output: {out_path}\n" in output
    assert "line_differences: 0\n" in output
    assert read_main_database(out_path).objects[0].name == "Room Zero"


def test_dump_json_reports_mail_model(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "maildb"
    path.write_text(write_mail_database_text(_mail_database()), encoding="utf-8")

    assert mush_dump_json([str(path), "--kind", "mail"]) == 0

    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert payload["kind"] == "mail"
    database = cast(dict[str, object], payload["database"])
    assert database["raw_mail_flags"] == 15
    messages = cast(list[object], database["messages"])
    assert len(messages) == 1


def test_upgrade_oldstyle_chat_writes_current_chat_database(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "chatdb.old"
    out_path = tmp_path / "chatdb"
    path.write_text(_oldstyle_chat_text(), encoding="utf-8")

    assert (
        mush_upgrade(
            [str(path), "--kind", "chat-oldstyle", "--out", str(out_path)]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "kind: chat-oldstyle\n" in output
    assert "output_kind: chat\n" in output
    upgraded = read_chat_database(out_path)
    assert upgraded.format_kind == "chat-current"
    assert upgraded.channels[0].name == "Public"


def test_cli_errors_include_source_and_line_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "broken.db"
    path.write_text("not a database\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        mush_inspect([str(path), "--kind", "main"])

    assert exc_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "broken.db:1" in stderr


def test_softcode_coverage_cli_reports_json_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&CMD.TEST #10=$test:@emit hi",
        encoding="utf-8",
    )

    assert mush_softcode_coverage([str(root)]) == 0

    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert payload["unit_count"] == 1
    assert payload["action_parsed_count"] == 1
    assert payload["effect_count"] == 1
    assert payload["unsupported_categories"] == []


def test_main_softcode_coverage_subcommand_reports_json_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.VALUE #10=1",
        encoding="utf-8",
    )

    assert main(["softcode-coverage", str(root)]) == 0

    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert payload["unit_count"] == 1
    assert payload["expression_parsed_count"] == 1


def test_softcode_graph_cli_reports_json_graph(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&CMD.TEST #10=$test:@emit hi",
        encoding="utf-8",
    )

    assert mush_softcode_graph([str(root)]) == 0

    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    definitions = cast(list[object], payload["definitions"])
    effects = cast(list[object], payload["effects"])
    assert len(definitions) == 1
    assert len(effects) == 1


def test_main_softcode_graph_subcommand_reports_json_graph(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "wcnh" / "systems" / "softcode"
    root.mkdir(parents=True)
    (root / "system.mush").write_text(
        "&FN.VALUE #10=1",
        encoding="utf-8",
    )

    assert main(["softcode-graph", str(root)]) == 0

    payload = cast(dict[str, object], json.loads(capsys.readouterr().out))
    definitions = cast(list[object], payload["definitions"])
    assert len(definitions) == 1


def _main_database() -> PennMainDatabase:
    return PennMainDatabase(
        raw_dbflags=0,
        dbversion=6,
        savedtime="now",
        object_count=1,
        objects={
            0: PennObject(
                dbref=0,
                name="Room Zero",
                location=-1,
                contents=-1,
                exits=-1,
                next=-1,
                parent=-1,
                owner=0,
                zone=-1,
                pennies=0,
                type=1,
                created=10,
                modified=11,
            )
        },
    )


def _mail_database() -> PennMailDatabase:
    return PennMailDatabase(
        raw_mail_flags=0,
        aliases=[
            PennMailAlias(
                owner=1,
                name="builders",
                description="Build team",
                name_flags=0,
                member_flags=0,
                members=(1, 2),
            )
        ],
        messages=[
            PennMailMessage(
                to=2,
                from_=1,
                from_ctime=100,
                time_text="now",
                subject="Subject",
                body="Body",
                read_flags=0,
            )
        ],
    )


def _oldstyle_chat_text() -> str:
    return "\n".join(
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


def test_inspect_auto_reports_chat_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "chatdb"
    path.write_text(
        write_chat_database_text(
            PennChatDatabase(
                raw_chat_flags=0,
                savedtime="now",
                channels=[
                    PennChannel(
                        name="Public",
                        description="Public channel",
                        flags=0,
                        creator=1,
                        cost=0,
                    )
                ],
            )
        ),
        encoding="utf-8",
    )

    assert mush_inspect([str(path), "--kind", "auto"]) == 0

    output = capsys.readouterr().out
    assert "kind: chat\n" in output
    assert "channel_count: 1\n" in output
