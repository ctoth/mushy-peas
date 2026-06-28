"""CST model for lossless PennMUSH softcode parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Escape:
    span: Span
    raw: str
    kind: Literal["escape"] = "escape"


@dataclass(frozen=True)
class PercentSub:
    span: Span
    raw: str
    kind: Literal["percent_sub"] = "percent_sub"


@dataclass(frozen=True)
class DollarSub:
    span: Span
    raw: str
    kind: Literal["dollar_sub"] = "dollar_sub"


@dataclass(frozen=True)
class Terminator:
    span: Span
    value: str
    kind: Literal["terminator"] = "terminator"


@dataclass(frozen=True)
class Argument:
    span: Span
    children: tuple[Node, ...]
    kind: Literal["argument"] = "argument"


@dataclass(frozen=True)
class FunctionCall:
    span: Span
    name_span: Span
    name: str
    open_paren: int
    arguments: tuple[Argument, ...]
    close_paren: int
    argument_terminators: tuple[Terminator, ...] = field(default_factory=tuple)
    kind: Literal["function_call"] = "function_call"


@dataclass(frozen=True)
class BraceGroup:
    span: Span
    open_brace: int
    children: tuple[Node, ...]
    close_brace: int
    kind: Literal["brace_group"] = "brace_group"


@dataclass(frozen=True)
class EvalGroup:
    span: Span
    open_bracket: int
    children: tuple[Node, ...]
    close_bracket: int
    kind: Literal["eval_group"] = "eval_group"


@dataclass(frozen=True)
class Unknown:
    span: Span
    reason: str
    kind: Literal["unknown"] = "unknown"


Node: TypeAlias = (
    Text
    | Escape
    | PercentSub
    | DollarSub
    | Terminator
    | FunctionCall
    | Argument
    | BraceGroup
    | EvalGroup
    | Unknown
)


@dataclass(frozen=True)
class Document:
    span: Span
    children: tuple[Node, ...]
    kind: Literal["document"] = "document"
