"""Render softcode CST nodes from their original source spans."""

from mushy_peas.softcode.model import Document, Node


def render(node: Document | Node, source: str) -> str:
    if isinstance(node, Document):
        return "".join(render(child, source) for child in node.children)
    return source[node.span.start : node.span.end]
