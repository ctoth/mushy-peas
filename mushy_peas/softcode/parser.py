"""Handwritten PennMUSH softcode parser."""

from __future__ import annotations

from dataclasses import dataclass

from mushy_peas.softcode.function_metadata import FunctionMetadata, FunctionRegistry
from mushy_peas.softcode.model import (
    Argument,
    BraceGroup,
    Document,
    Escape,
    EvalGroup,
    FunctionCall,
    Node,
    PercentSub,
    Span,
    Text,
)


@dataclass(frozen=True)
class ParseMode:
    function_mandatory: bool = False


def parse_expression(
    source: str,
    metadata: FunctionRegistry | None = None,
    mode: ParseMode | None = None,
) -> Document:
    parser = _Parser(
        source=source,
        metadata=metadata,
        mode=mode or ParseMode(),
    )
    children, end = parser.parse_until(0, terminators=frozenset())
    span = Span(0, len(source))
    if end != len(source):
        raise AssertionError("top-level softcode parse stopped early")
    return Document(span=span, children=children)


@dataclass(frozen=True)
class _Parser:
    source: str
    metadata: FunctionRegistry | None
    mode: ParseMode

    def parse_until(
        self,
        position: int,
        *,
        terminators: frozenset[str],
    ) -> tuple[tuple[Node, ...], int]:
        children: list[Node] = []
        text_start = position
        index = position
        while index < len(self.source):
            if self.source[index] in terminators:
                break
            escape = self._parse_escape_at(index)
            if escape is not None:
                if text_start < index:
                    children.append(Text(span=Span(text_start, index)))
                children.append(escape)
                index = escape.span.end
                text_start = index
                continue
            percent_sub = self._parse_percent_sub_at(index)
            if percent_sub is not None:
                if text_start < index:
                    children.append(Text(span=Span(text_start, index)))
                children.append(percent_sub)
                index = percent_sub.span.end
                text_start = index
                continue
            group = self._parse_group_at(index)
            if group is not None:
                if text_start < index:
                    children.append(Text(span=Span(text_start, index)))
                children.append(group)
                index = group.span.end
                text_start = index
                continue
            function = self._parse_function_at(index)
            if function is not None:
                if text_start < index:
                    children.append(Text(span=Span(text_start, index)))
                children.append(function)
                index = function.span.end
                text_start = index
                continue
            index += 1
        if text_start < index:
            children.append(Text(span=Span(text_start, index)))
        return tuple(children), index

    def _parse_function_at(self, position: int) -> FunctionCall | None:
        metadata = self._match_function_at(position)
        if metadata is None:
            return None
        open_paren = position + len(metadata.name)
        if open_paren >= len(self.source) or self.source[open_paren] != "(":
            return None
        arguments, close_paren = self._parse_arguments(open_paren + 1)
        if close_paren >= len(self.source) or self.source[close_paren] != ")":
            return None
        return FunctionCall(
            span=Span(position, close_paren + 1),
            name_span=Span(position, open_paren),
            name=metadata.name,
            open_paren=open_paren,
            arguments=arguments,
            close_paren=close_paren,
        )

    def _match_function_at(self, position: int) -> FunctionMetadata | None:
        if self.metadata is None:
            return None
        for name in sorted(self.metadata.functions, key=len, reverse=True):
            end = position + len(name)
            if self.source[position:end].upper() == name:
                return self.metadata.functions[name]
        return None

    def _parse_arguments(self, position: int) -> tuple[tuple[Argument, ...], int]:
        arguments: list[Argument] = []
        index = position
        while True:
            children, end = self.parse_until(index, terminators=frozenset({",", ")"}))
            arguments.append(
                Argument(
                    span=Span(index, end),
                    children=children,
                )
            )
            if end >= len(self.source) or self.source[end] == ")":
                return tuple(arguments), end
            index = end + 1

    def _parse_group_at(self, position: int) -> BraceGroup | EvalGroup | None:
        if self.source[position] == "{":
            children, end = self.parse_until(position + 1, terminators=frozenset("}"))
            if end < len(self.source) and self.source[end] == "}":
                return BraceGroup(
                    span=Span(position, end + 1),
                    open_brace=position,
                    children=children,
                    close_brace=end,
                )
            return None
        if self.source[position] == "[":
            children, end = self.parse_until(position + 1, terminators=frozenset("]"))
            if end < len(self.source) and self.source[end] == "]":
                return EvalGroup(
                    span=Span(position, end + 1),
                    open_bracket=position,
                    children=children,
                    close_bracket=end,
                )
        return None

    def _parse_percent_sub_at(self, position: int) -> PercentSub | None:
        if self.source[position] != "%" or position + 1 >= len(self.source):
            return None
        code = self.source[position + 1]
        end = position + 2
        if code in {"Q", "q"} and end < len(self.source):
            if self.source[end] == "<":
                close = self.source.find(">", end + 1)
                if close != -1:
                    end = close + 1
            else:
                end += 1
        elif code in {"I", "i", "$", "V", "v", "W", "w", "X", "x"}:
            if end >= len(self.source):
                return None
            end += 1
        return PercentSub(
            span=Span(position, end),
            raw=self.source[position:end],
        )

    def _parse_escape_at(self, position: int) -> Escape | None:
        if self.source[position] != "\\":
            return None
        end = min(position + 2, len(self.source))
        return Escape(
            span=Span(position, end),
            raw=self.source[position:end],
        )
