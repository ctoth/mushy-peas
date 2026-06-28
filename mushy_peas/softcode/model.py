"""CST model for lossless PennMUSH softcode parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True, order=True)
class Span:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("span start must be non-negative")
        if self.end < self.start:
            raise ValueError("span end must be greater than or equal to start")


@dataclass(frozen=True)
class Text:
    span: Span
    kind: Literal["text"] = "text"


Node: TypeAlias = Text


@dataclass(frozen=True)
class Document:
    span: Span
    children: tuple[Node, ...]
    kind: Literal["document"] = "document"
