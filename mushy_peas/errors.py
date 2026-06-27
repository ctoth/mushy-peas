"""Error types for PennMUSH database parsing and I/O."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    """A concrete position in an input stream."""

    source: str
    line: int

    def format(self) -> str:
        return f"{self.source}:{self.line}"


class MushyPeasError(Exception):
    """Base exception for this package."""


class ParseError(MushyPeasError):
    """A parse failure with source and line context."""

    def __init__(
        self,
        message: str,
        *,
        source: str = "<string>",
        line: int = 0,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self.message = message
        self.source = source
        self.line = line
        self.expected = expected
        self.actual = actual
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        location = SourceLocation(self.source, self.line).format()
        details: list[str] = [f"{location}: {self.message}"]
        if self.expected is not None:
            details.append(f"expected {self.expected}")
        if self.actual is not None:
            details.append(f"actual {self.actual!r}")
        return "; ".join(details)


class StreamError(MushyPeasError):
    """A stream open, compression, or external filter failure."""
