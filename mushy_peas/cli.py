"""Command-line entry points for mushy-peas."""

import argparse
import difflib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Literal, TypeAlias, cast

from mushy_peas.chat_model import PennChatDatabase
from mushy_peas.chat_reader import read_chat_database
from mushy_peas.chat_writer import write_chat_database, write_chat_database_text
from mushy_peas.compression import read_database_text
from mushy_peas.errors import MushyPeasError
from mushy_peas.mail_model import PennMailDatabase
from mushy_peas.mail_reader import read_mail_database
from mushy_peas.mail_writer import write_mail_database, write_mail_database_text
from mushy_peas.main_model import PennMainDatabase
from mushy_peas.main_reader import read_main_database
from mushy_peas.main_writer import write_main_database, write_main_database_text
from mushy_peas.oldstyle import (
    read_oldstyle_chat_database,
    read_oldstyle_main_database,
)
from mushy_peas.softcode.coverage_report import build_softcode_coverage_report
from mushy_peas.softcode.units import extract_softcode_units

RequestedKind: TypeAlias = Literal["main", "mail", "chat", "auto"]
DatabaseKind: TypeAlias = Literal["main", "mail", "chat"]
UpgradeKind: TypeAlias = Literal["main-oldstyle", "chat-oldstyle"]
DatabaseModel: TypeAlias = PennMainDatabase | PennMailDatabase | PennChatDatabase
JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)
CommandHandler: TypeAlias = Callable[[argparse.Namespace], int]


class CliError(MushyPeasError):
    """A command-line usage or dispatch failure."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mushy-peas")
    subcommands = parser.add_subparsers(dest="command", required=True)
    _configure_inspect_parser(subcommands.add_parser("inspect"))
    _configure_roundtrip_parser(subcommands.add_parser("roundtrip"))
    _configure_dump_json_parser(subcommands.add_parser("dump-json"))
    _configure_upgrade_parser(subcommands.add_parser("upgrade"))
    _configure_softcode_coverage_parser(subcommands.add_parser("softcode-coverage"))
    return _run_parser(parser, argv)


def mush_inspect(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mush-inspect")
    _configure_inspect_parser(parser)
    return _run_parser(parser, argv)


def mush_roundtrip(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mush-roundtrip")
    _configure_roundtrip_parser(parser)
    return _run_parser(parser, argv)


def mush_dump_json(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mush-dump-json")
    _configure_dump_json_parser(parser)
    return _run_parser(parser, argv)


def mush_upgrade(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mush-upgrade")
    _configure_upgrade_parser(parser)
    return _run_parser(parser, argv)


def mush_softcode_coverage(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mush-softcode-coverage")
    _configure_softcode_coverage_parser(parser)
    return _run_parser(parser, argv)


def _configure_inspect_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")
    parser.add_argument(
        "--kind",
        choices=("main", "mail", "chat", "auto"),
        default="auto",
    )
    parser.set_defaults(handler=_inspect_command)


def _configure_roundtrip_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")
    parser.add_argument(
        "--kind",
        choices=("main", "mail", "chat", "auto"),
        default="auto",
    )
    parser.add_argument("--out", required=True)
    parser.set_defaults(handler=_roundtrip_command)


def _configure_dump_json_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")
    parser.add_argument(
        "--kind",
        choices=("main", "mail", "chat", "auto"),
        default="auto",
    )
    parser.set_defaults(handler=_dump_json_command)


def _configure_upgrade_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")
    parser.add_argument(
        "--kind",
        choices=("main-oldstyle", "chat-oldstyle"),
        required=True,
    )
    parser.add_argument("--out", required=True)
    parser.set_defaults(handler=_upgrade_command)


def _configure_softcode_coverage_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+")
    parser.set_defaults(handler=_softcode_coverage_command)


def _run_parser(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None,
) -> int:
    args = parser.parse_args(argv)
    handler = cast(CommandHandler, args.handler)
    try:
        return handler(args)
    except MushyPeasError as exc:
        parser.exit(1, f"{parser.prog}: error: {exc}\n")


def _inspect_command(args: argparse.Namespace) -> int:
    kind, database = _read_requested_database(
        Path(str(args.path)),
        _requested_kind(str(args.kind)),
    )
    for line in _inspection_lines(kind, database):
        print(line)
    return 0


def _roundtrip_command(args: argparse.Namespace) -> int:
    path = Path(str(args.path))
    out_path = Path(str(args.out))
    kind, database = _read_requested_database(path, _requested_kind(str(args.kind)))
    before = read_database_text(path)
    after = _write_database_text(kind, database)
    _write_database(kind, out_path, database)
    difference_count = _line_difference_count(before, after, path, out_path)
    print(f"kind: {kind}")
    print(f"output: {out_path}")
    print(f"line_differences: {difference_count}")
    return 0


def _dump_json_command(args: argparse.Namespace) -> int:
    kind, database = _read_requested_database(
        Path(str(args.path)),
        _requested_kind(str(args.kind)),
    )
    print(
        json.dumps(
            {"kind": kind, "database": _to_json_value(database)},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _upgrade_command(args: argparse.Namespace) -> int:
    path = Path(str(args.path))
    out_path = Path(str(args.out))
    kind = _upgrade_kind(str(args.kind))
    if kind == "main-oldstyle":
        write_main_database(out_path, read_oldstyle_main_database(path))
        output_kind = "main"
    else:
        write_chat_database(out_path, read_oldstyle_chat_database(path))
        output_kind = "chat"
    print(f"kind: {kind}")
    print(f"output_kind: {output_kind}")
    print(f"output: {out_path}")
    return 0


def _softcode_coverage_command(args: argparse.Namespace) -> int:
    paths = tuple(Path(str(path)) for path in args.paths)
    units = extract_softcode_units(paths).units
    report = build_softcode_coverage_report(units)
    print(json.dumps(_to_json_value(report), indent=2, sort_keys=True))
    return 0


def _read_requested_database(
    path: Path,
    requested_kind: RequestedKind,
) -> tuple[DatabaseKind, DatabaseModel]:
    if requested_kind == "auto":
        return _read_auto_database(path)
    if requested_kind == "main":
        return ("main", _read_main_database(path))
    if requested_kind == "mail":
        return ("mail", read_mail_database(path))
    return ("chat", read_chat_database(path))


def _read_auto_database(path: Path) -> tuple[DatabaseKind, DatabaseModel]:
    errors: list[str] = []
    readers: tuple[tuple[DatabaseKind, Callable[[Path], DatabaseModel]], ...] = (
        ("main", _read_main_database),
        ("mail", read_mail_database),
        ("chat", read_chat_database),
    )
    for kind, reader in readers:
        try:
            return (kind, reader(path))
        except MushyPeasError as exc:
            errors.append(f"{kind}: {exc}")
    raise CliError("could not auto-detect database kind:\n" + "\n".join(errors))


def _read_main_database(path: Path) -> PennMainDatabase:
    try:
        return read_main_database(path)
    except MushyPeasError as current_error:
        try:
            return read_oldstyle_main_database(path)
        except MushyPeasError as oldstyle_error:
            raise CliError(
                "could not read main database:\n"
                f"current: {current_error}\n"
                f"oldstyle: {oldstyle_error}"
            ) from oldstyle_error


def _write_database(kind: DatabaseKind, path: Path, database: DatabaseModel) -> None:
    if kind == "main":
        write_main_database(path, _expect_main(database))
    elif kind == "mail":
        write_mail_database(path, _expect_mail(database))
    else:
        write_chat_database(path, _expect_chat(database))


def _write_database_text(kind: DatabaseKind, database: DatabaseModel) -> str:
    if kind == "main":
        return write_main_database_text(_expect_main(database))
    if kind == "mail":
        return write_mail_database_text(_expect_mail(database))
    return write_chat_database_text(_expect_chat(database))


def _inspection_lines(kind: DatabaseKind, database: DatabaseModel) -> list[str]:
    if kind == "main":
        main_database = _expect_main(database)
        return [
            "kind: main",
            f"format_kind: {main_database.format_kind}",
            f"dbversion: {main_database.dbversion}",
            f"object_count: {main_database.object_count}",
            f"non_garbage_count: {len(main_database.objects)}",
            f"flag_count: {len(main_database.flags)}",
            f"power_count: {len(main_database.powers)}",
            f"global_attribute_count: {len(main_database.attributes)}",
        ]
    if kind == "mail":
        mail_database = _expect_mail(database)
        return [
            "kind: mail",
            f"mail_flags: {mail_database.raw_mail_flags}",
            f"alias_count: {len(mail_database.aliases)}",
            f"message_count: {len(mail_database.messages)}",
        ]
    chat_database = _expect_chat(database)
    return [
        "kind: chat",
        f"format_kind: {chat_database.format_kind}",
        f"chat_flags: {chat_database.raw_chat_flags}",
        f"channel_count: {len(chat_database.channels)}",
        f"user_count: {sum(len(channel.users) for channel in chat_database.channels)}",
    ]


def _line_difference_count(before: str, after: str, path: Path, out_path: Path) -> int:
    diff_lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=str(path),
        tofile=str(out_path),
        lineterm="",
    )
    return sum(
        1
        for line in diff_lines
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith(("+++", "---"))
    )


def _to_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _to_json_value(item) for key, item in mapping.items()}
    if isinstance(value, list | tuple):
        sequence = cast(Sequence[object], value)
        return [_to_json_value(item) for item in sequence]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_json_value(cast(object, getattr(value, field.name)))
            for field in fields(value)
        }
    raise CliError(f"cannot serialize {type(value).__name__} to JSON")


def _expect_main(database: DatabaseModel) -> PennMainDatabase:
    if isinstance(database, PennMainDatabase):
        return database
    raise CliError("expected a main database model")


def _expect_mail(database: DatabaseModel) -> PennMailDatabase:
    if isinstance(database, PennMailDatabase):
        return database
    raise CliError("expected a mail database model")


def _expect_chat(database: DatabaseModel) -> PennChatDatabase:
    if isinstance(database, PennChatDatabase):
        return database
    raise CliError("expected a chat database model")


def _requested_kind(value: str) -> RequestedKind:
    if value in {"main", "mail", "chat", "auto"}:
        return cast(RequestedKind, value)
    raise CliError(f"unsupported kind {value!r}")


def _upgrade_kind(value: str) -> UpgradeKind:
    if value in {"main-oldstyle", "chat-oldstyle"}:
        return cast(UpgradeKind, value)
    raise CliError(f"unsupported upgrade kind {value!r}")
