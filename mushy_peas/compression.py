"""Compressed text streams for PennMUSH database files."""

import bz2
import gzip
import subprocess
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Literal, TextIO, cast

from mushy_peas.errors import StreamError

CompressionMode = Literal["auto", "none", "gzip", "bzip2", "external"]
ResolvedCompression = Literal["none", "gzip", "bzip2", "external"]
OpenMode = Literal["r", "w"]


def resolve_compression(
    path: str | Path,
    *,
    compression: CompressionMode = "auto",
) -> ResolvedCompression:
    """Resolve explicit compression first, then infer from filename extension."""

    if compression != "auto":
        return compression

    suffix = Path(path).suffix.lower()
    if suffix == ".gz":
        return "gzip"
    if suffix in {".bz2", ".bzip2"}:
        return "bzip2"
    return "none"


@contextmanager
def open_database_text(
    path: str | Path,
    mode: OpenMode,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
    newline: str | None = "",
) -> Generator[TextIO, None, None]:
    """Open a database path as text, applying the requested compression mode."""

    resolved = resolve_compression(path, compression=compression)
    db_path = Path(path)

    if resolved == "external":
        with _open_external_text(
            db_path,
            mode,
            external_command=external_command,
            encoding=encoding,
            newline=newline,
        ) as stream:
            yield stream
        return

    if external_command is not None:
        raise StreamError("external_command is only valid with external compression")

    try:
        stream = _open_builtin_text(
            db_path,
            mode,
            compression=resolved,
            encoding=encoding,
            newline=newline,
        )
    except OSError as exc:
        raise StreamError(f"failed to open {db_path}: {exc}") from exc
    try:
        yield stream
    finally:
        stream.close()


def read_database_text(
    path: str | Path,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> str:
    """Read a whole database text file through the compression layer."""

    try:
        with open_database_text(
            path,
            "r",
            compression=compression,
            external_command=external_command,
            encoding=encoding,
        ) as stream:
            return stream.read()
    except (EOFError, OSError, UnicodeError) as exc:
        raise StreamError(f"failed to read {Path(path)}: {exc}") from exc


def write_database_text(
    path: str | Path,
    text: str,
    *,
    compression: CompressionMode = "auto",
    external_command: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> None:
    """Write a whole database text file through the compression layer."""

    try:
        with open_database_text(
            path,
            "w",
            compression=compression,
            external_command=external_command,
            encoding=encoding,
        ) as stream:
            stream.write(text)
    except (EOFError, OSError, UnicodeError) as exc:
        raise StreamError(f"failed to write {Path(path)}: {exc}") from exc


@contextmanager
def _open_external_text(
    path: Path,
    mode: OpenMode,
    *,
    external_command: Sequence[str] | None,
    encoding: str,
    newline: str | None,
) -> Generator[TextIO, None, None]:
    if external_command is None or len(external_command) == 0:
        raise StreamError("external compression requires an explicit command")

    if mode == "r":
        input_data = path.read_bytes()
        output_data = _run_external_filter(
            external_command,
            input_data,
            operation="read",
            path=path,
        )
        yield StringIO(output_data.decode(encoding), newline=newline)
        return

    buffer = StringIO(newline=newline)
    yield buffer
    output_data = _run_external_filter(
        external_command,
        buffer.getvalue().encode(encoding),
        operation="write",
        path=path,
    )
    path.write_bytes(output_data)


def _run_external_filter(
    command: Sequence[str],
    input_data: bytes,
    *,
    operation: Literal["read", "write"],
    path: Path,
) -> bytes:
    try:
        completed = subprocess.run(
            command,
            input=input_data,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise StreamError(
            f"external filter failed to start while trying to {operation} {path}: {exc}"
        ) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {stderr}" if stderr else ""
        raise StreamError(
            "external filter failed while trying to "
            f"{operation} {path} with exit code {completed.returncode}{suffix}"
        )

    return completed.stdout


def _open_builtin_text(
    path: Path,
    mode: OpenMode,
    *,
    compression: Literal["none", "gzip", "bzip2"],
    encoding: str,
    newline: str | None,
) -> TextIO:
    if compression == "none":
        return path.open(mode, encoding=encoding, newline=newline)
    if compression == "gzip":
        return cast(
            TextIO,
            gzip.open(path, f"{mode}t", encoding=encoding, newline=newline),
        )
    return cast(
        TextIO,
        bz2.open(path, f"{mode}t", encoding=encoding, newline=newline),
    )
