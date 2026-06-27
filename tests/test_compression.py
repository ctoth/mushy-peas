from pathlib import Path

import pytest

from mushy_peas.compression import (
    open_database_text,
    read_database_text,
    resolve_compression,
    write_database_text,
)
from mushy_peas.errors import StreamError

TINY_DATABASE = '+V1282\nsavedtime "now"\n***END OF DUMP***\n'


def filter_command(script_name: str) -> list[str]:
    return ["uv", "run", "python", str(Path("tests/fixtures/filters") / script_name)]


def test_resolves_compression_explicit_option_before_extension() -> None:
    assert resolve_compression("db.gz", compression="none") == "none"
    assert resolve_compression("db.txt", compression="gzip") == "gzip"
    assert resolve_compression("db.Z", compression="external") == "external"


def test_resolves_compression_from_extension_when_auto() -> None:
    assert resolve_compression("db.gz") == "gzip"
    assert resolve_compression("db.bz2") == "bzip2"
    assert resolve_compression("db.bzip2") == "bzip2"
    assert resolve_compression("db.Z") == "none"


def test_reads_plain_text_stream(tmp_path: Path) -> None:
    path = tmp_path / "tiny.db"
    path.write_text(TINY_DATABASE, encoding="utf-8", newline="")

    with open_database_text(path, "r") as stream:
        assert stream.read() == TINY_DATABASE


def test_tiny_database_reads_from_plain_gzip_and_bzip2(tmp_path: Path) -> None:
    plain = tmp_path / "tiny.db"
    gzip_path = tmp_path / "tiny.db.gz"
    bzip2_path = tmp_path / "tiny.db.bz2"

    write_database_text(plain, TINY_DATABASE)
    write_database_text(gzip_path, TINY_DATABASE)
    write_database_text(bzip2_path, TINY_DATABASE)

    assert read_database_text(plain) == TINY_DATABASE
    assert read_database_text(gzip_path) == TINY_DATABASE
    assert read_database_text(bzip2_path) == TINY_DATABASE


def test_writer_output_compressed_as_gzip_and_bzip2_decompresses(
    tmp_path: Path,
) -> None:
    gzip_path = tmp_path / "tiny.gz"
    bzip2_path = tmp_path / "tiny.bz2"

    write_database_text(gzip_path, TINY_DATABASE, compression="gzip")
    write_database_text(bzip2_path, TINY_DATABASE, compression="bzip2")

    assert read_database_text(gzip_path, compression="gzip") == TINY_DATABASE
    assert read_database_text(bzip2_path, compression="bzip2") == TINY_DATABASE


def test_reads_through_explicit_external_filter(tmp_path: Path) -> None:
    legacy_path = tmp_path / "tiny.Z"
    legacy_path.write_bytes(TINY_DATABASE.encode("utf-8"))

    assert (
        read_database_text(
            legacy_path,
            compression="external",
            external_command=filter_command("copy_filter.py"),
        )
        == TINY_DATABASE
    )


def test_writer_output_through_external_filter_round_trips(tmp_path: Path) -> None:
    legacy_path = tmp_path / "written.Z"

    write_database_text(
        legacy_path,
        TINY_DATABASE,
        compression="external",
        external_command=filter_command("copy_filter.py"),
    )

    assert legacy_path.read_bytes() == TINY_DATABASE.encode("utf-8")
    assert (
        read_database_text(
            legacy_path,
            compression="external",
            external_command=filter_command("copy_filter.py"),
        )
        == TINY_DATABASE
    )


def test_external_filter_failure_includes_stderr(tmp_path: Path) -> None:
    path = tmp_path / "tiny.Z"
    path.write_bytes(TINY_DATABASE.encode("utf-8"))

    with pytest.raises(StreamError, match="intentional filter failure"):
        read_database_text(
            path,
            compression="external",
            external_command=filter_command("fail_filter.py"),
        )


def test_wrong_compression_mode_fails_with_stream_error(tmp_path: Path) -> None:
    path = tmp_path / "plain.db"
    path.write_text(TINY_DATABASE, encoding="utf-8", newline="")

    with pytest.raises(StreamError, match="failed to read"):
        read_database_text(path, compression="gzip")


def test_external_command_is_rejected_for_non_external_mode(tmp_path: Path) -> None:
    path = tmp_path / "plain.db"
    path.write_text(TINY_DATABASE, encoding="utf-8", newline="")

    with pytest.raises(StreamError, match="external_command is only valid"):
        read_database_text(
            path,
            compression="none",
            external_command=filter_command("copy_filter.py"),
        )
