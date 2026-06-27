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
uv run pytest
```

The current first slice implements the package skeleton plus shared primitives:
line ending detection, quoted strings, labeled lines, dbrefs, `+V` header
encoding/decoding, and PennMUSH end markers.
