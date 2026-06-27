"""PennMUSH server-load oracle test support."""

import bz2
import gzip
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mushy_peas.chat_model import PennChatDatabase
from mushy_peas.chat_reader import read_chat_database_text
from mushy_peas.chat_writer import write_chat_database_text
from mushy_peas.mail_model import PennMailDatabase
from mushy_peas.mail_writer import write_mail_database_text
from mushy_peas.main_reader import read_main_database_text
from mushy_peas.main_writer import write_main_database_text

OracleCompression = Literal["none", "gzip", "bzip2"]

DEFAULT_CHECKOUT = Path("C:/Users/Q/src/pennmush")
DEFAULT_WSL_CHECKOUT = "/mnt/c/Users/Q/src/pennmush"
DEFAULT_GAME_ROOT = "/tmp/mushy-peas-penn-oracle"
SERVER_TIMEOUT_SECONDS = 20
RUN_SECONDS = 6

REQUIRED_MARKERS = (
    "LOADING: data/indb",
    "LOADING: data/indb (done)",
    "LOADING: data/maildb",
    "LOADING: data/maildb (done)",
    "LOADING: data/chatdb",
    "LOADING: data/chatdb (done)",
    "RESTART FINISHED.",
    "MUSH shutdown completed.",
)
FORBIDDEN_MARKERS = (
    "ERROR: Unable to read mail database!",
    "ERROR: Unable to read chat database!",
    "PANIC:",
)


@dataclass(frozen=True)
class OracleRun:
    game_dir: str
    log: str


@dataclass(frozen=True)
class BaselineDatabases:
    main_text: str
    mail: PennMailDatabase
    chat: PennChatDatabase


def oracle_available() -> bool:
    if not DEFAULT_CHECKOUT.exists():
        return False
    completed = _run_wsl(
        f"cd {shlex.quote(DEFAULT_WSL_CHECKOUT)} && ./src/netmud --version",
        check=False,
    )
    return completed.returncode == 0


def require_oracle_available() -> None:
    if not oracle_available():
        raise RuntimeError(
            "PennMUSH oracle is unavailable; expected built checkout at "
            f"{DEFAULT_CHECKOUT}"
        )


def load_baseline_databases() -> BaselineDatabases:
    """Create a real minimal PennMUSH world and return its dumped databases."""

    game_dir = _prepare_game_dir("baseline", compression="none")
    _write_text(
        f"{game_dir}/data/maildb",
        write_mail_database_text(PennMailDatabase(0)),
    )
    _write_text(
        f"{game_dir}/data/chatdb",
        write_chat_database_text(PennChatDatabase(raw_chat_flags=0, savedtime="now")),
    )
    run = _run_server(game_dir)
    _assert_baseline_success(run)
    main_text = _read_glob_text(game_dir, "outdb*")
    chat = read_chat_database_text(_read_text(f"{game_dir}/data/chatdb"))
    return BaselineDatabases(
        main_text=main_text,
        mail=PennMailDatabase(raw_mail_flags=0),
        chat=chat,
    )


def run_load_oracle(
    *,
    main_text: str,
    mail: PennMailDatabase,
    chat: PennChatDatabase,
    compression: OracleCompression,
) -> OracleRun:
    game_dir = _prepare_game_dir(f"load-{compression}", compression=compression)
    _write_database_payload(
        f"{game_dir}/data/indb{_suffix(compression)}",
        write_main_database_text(read_main_database_text(main_text)),
        compression=compression,
    )
    _write_database_payload(
        f"{game_dir}/data/maildb{_suffix(compression)}",
        write_mail_database_text(mail),
        compression=compression,
    )
    _write_database_payload(
        f"{game_dir}/data/chatdb{_suffix(compression)}",
        write_chat_database_text(chat),
        compression=compression,
    )
    return _run_server(game_dir)


def assert_oracle_success(run: OracleRun) -> None:
    missing = [marker for marker in REQUIRED_MARKERS if marker not in run.log]
    forbidden = [marker for marker in FORBIDDEN_MARKERS if marker in run.log]
    if missing or forbidden:
        detail = "\n".join(
            (
                f"game_dir={run.game_dir}",
                f"missing={missing}",
                f"forbidden={forbidden}",
                "log:",
                run.log,
            )
        )
        raise AssertionError(detail)


def _assert_baseline_success(run: OracleRun) -> None:
    missing = [
        marker
        for marker in ("RESTART FINISHED.", "MUSH shutdown completed.")
        if marker not in run.log
    ]
    forbidden = [marker for marker in ("PANIC:",) if marker in run.log]
    if missing or forbidden:
        detail = "\n".join(
            (
                f"game_dir={run.game_dir}",
                f"missing={missing}",
                f"forbidden={forbidden}",
                "log:",
                run.log,
            )
        )
        raise AssertionError(detail)


def _prepare_game_dir(name: str, *, compression: OracleCompression) -> str:
    game_dir = f"{DEFAULT_GAME_ROOT}/{name}"
    commands = [
        f"rm -rf {shlex.quote(game_dir)}",
        f"cp -a {shlex.quote(DEFAULT_WSL_CHECKOUT)}/game {shlex.quote(game_dir)}",
        f"cd {shlex.quote(game_dir)}",
        "cp mushcnf.dst mush.cnf",
        "cp aliascnf.dst alias.cnf",
        "cp restrictcnf.dst restrict.cnf",
        ": > access.cnf",
        "mkdir -p data log save",
        "perl -0pi -e 's/^port\\s+.*/port 44201/m' mush.cnf",
        "perl -0pi -e 's#^input_database\\s+.*#input_database data/indb#m' mush.cnf",
        "perl -0pi -e 's#^output_database\\s+.*#output_database data/outdb#m' mush.cnf",
        "perl -0pi -e 's#^mail_database\\s+.*#mail_database data/maildb#m' mush.cnf",
        "perl -0pi -e 's#^chat_database\\s+.*#chat_database data/chatdb#m' mush.cnf",
        *_compression_config_commands(compression),
    ]
    _run_wsl(" && ".join(commands))
    return game_dir


def _compression_config_commands(compression: OracleCompression) -> tuple[str, ...]:
    if compression == "none":
        return (
            "printf '\\ncompress_program\\nuncompress_program\\ncompress_suffix\\n' "
            ">> mush.cnf",
        )
    if compression == "gzip":
        return (
            "printf '\\ncompress_program gzip\\nuncompress_program gunzip\\n"
            "compress_suffix .gz\\n' >> mush.cnf",
        )
    return (
        "printf '\\ncompress_program bzip2\\nuncompress_program bunzip2\\n"
        "compress_suffix .bz2\\n' >> mush.cnf",
    )


def _run_server(game_dir: str) -> OracleRun:
    command = (
        f"cd {shlex.quote(game_dir)} && "
        f"timeout -s INT {RUN_SECONDS}s "
        f"{shlex.quote(DEFAULT_WSL_CHECKOUT)}/src/netmud --no-session mush.cnf"
    )
    _run_wsl(command, check=False, timeout=SERVER_TIMEOUT_SECONDS)
    return OracleRun(game_dir=game_dir, log=_read_text(f"{game_dir}/log/netmush.log"))


def _write_database_payload(
    path: str,
    text: str,
    *,
    compression: OracleCompression,
) -> None:
    data = text.encode("utf-8")
    if compression == "gzip":
        data = gzip.compress(data)
    elif compression == "bzip2":
        data = bz2.compress(data)
    _write_bytes(path, data)


def _suffix(compression: OracleCompression) -> str:
    if compression == "gzip":
        return ".gz"
    if compression == "bzip2":
        return ".bz2"
    return ""


def _read_text(path: str) -> str:
    completed = _run_wsl(f"cat {shlex.quote(path)}")
    return completed.stdout.decode("utf-8")


def _read_glob_text(game_dir: str, pattern: str) -> str:
    command = (
        f"cd {shlex.quote(game_dir)} && "
        f"find data -maxdepth 1 -type f -name {shlex.quote(pattern)} "
        "-printf '%s %p\\n'"
    )
    completed = _run_wsl(command)
    candidates = _parse_find_candidates(completed.stdout.decode("utf-8"))
    if not candidates:
        raise RuntimeError(f"no files matched {pattern} under {game_dir}/data")
    _size, relative_path = max(candidates)
    return _read_text(f"{game_dir}/{relative_path}")


def _parse_find_candidates(output: str) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    for line in output.splitlines():
        size_text, separator, path = line.partition(" ")
        if not separator:
            continue
        candidates.append((int(size_text), path))
    return candidates


def _write_text(path: str, text: str) -> None:
    _write_bytes(path, text.encode("utf-8"))


def _write_bytes(path: str, data: bytes) -> None:
    _run_wsl(f"cat > {shlex.quote(path)}", input_data=data)


def _run_wsl(
    command: str,
    *,
    input_data: bytes | None = None,
    check: bool = True,
    timeout: int = SERVER_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["wsl", "-u", "q", "--", "bash", "-lc", command],
        input=input_data,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        stdout = completed.stdout.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"WSL command failed with exit {completed.returncode}: {command}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed
