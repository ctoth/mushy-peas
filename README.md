# mushy-peas

`mushy-peas` is a Python toolkit for reading, writing, inspecting, and
round-tripping PennMUSH database files.

The implementation target is PennMUSH's on-disk database family:

- current labeled main object databases;
- oldstyle readable main databases covered by PennMUSH `dbtools`;
- mail databases, including mail aliases;
- current and oldstyle chat databases;
- uncompressed, gzip, bzip2, and explicitly configured external-filter streams.

This project is not a LambdaMOO parser or converter.

## Development

Use `uv` for all Python commands:

```powershell
uv run ruff check .
uv run mypy .
uv run pyright
uv run pytest
```

The repository is configured for strict typing with mypy and pyright, Ruff, a
post-commit hook, and GitHub Actions CI.

## CLI

The package installs four verification commands:

```powershell
mush-inspect PATH --kind main|mail|chat|auto
mush-roundtrip PATH --kind main|mail|chat|auto --out OUT
mush-dump-json PATH --kind main|mail|chat|auto
mush-upgrade PATH --kind main-oldstyle|chat-oldstyle --out OUT
```

The commands use the same readers and writers as the test suite. Parse failures
include source file and line context.

## Compatibility

The test suite includes source-shaped fixtures for current main, oldstyle main,
mail, current chat, oldstyle chat, compression, and cross-family read/write/read
round trips. `tests/oracle/` also runs the generated main/mail/chat files
through a real PennMUSH server load path when the local WSL PennMUSH checkout is
available.
