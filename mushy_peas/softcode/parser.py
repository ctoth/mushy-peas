"""Handwritten PennMUSH softcode parser."""

from mushy_peas.softcode.model import Document, Span, Text


def parse_expression(source: str) -> Document:
    span = Span(0, len(source))
    if not source:
        return Document(span=span, children=())
    return Document(span=span, children=(Text(span=span),))
