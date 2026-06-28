from pathlib import Path

from mushy_peas.softcode import FunctionCall, FunctionExpr, UnknownExpr
from mushy_peas.softcode.ast_views import build_ast_view
from mushy_peas.softcode.function_metadata import load_function_registry
from mushy_peas.softcode.model import Document, Span, Text, Unknown
from mushy_peas.softcode.parser import parse_expression

FIXTURE = Path("tests/fixtures/softcode/pennmush-functions.json")


def test_function_call_projects_to_function_expr() -> None:
    source = "add(add(1,2),3)"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)
    call = document.children[0]

    ast = build_ast_view(document)
    expr = ast.expressions[0]

    assert isinstance(call, FunctionCall)
    assert isinstance(expr, FunctionExpr)
    assert ast.span == document.span
    assert ast.cst is document
    assert expr.span == call.span
    assert expr.cst is call
    assert expr.name == "ADD"
    assert len(expr.arguments) == 2
    assert isinstance(expr.arguments[0][0], FunctionExpr)
    assert expr.arguments[0][0].cst is call.arguments[0].children[0]


def test_unknown_cst_projects_to_unknown_expr() -> None:
    unknown = Unknown(span=Span(2, 5), reason="oracle-only edge")
    document = Document(span=Span(0, 5), children=(unknown,))

    ast = build_ast_view(document)
    expr = ast.expressions[0]

    assert isinstance(expr, UnknownExpr)
    assert expr.span == unknown.span
    assert expr.cst is unknown
    assert expr.reason == "oracle-only edge"


def test_ast_projection_is_total_over_unsupported_cst_nodes() -> None:
    text = Text(span=Span(0, 4))
    document = Document(span=Span(0, 4), children=(text,))

    ast = build_ast_view(document)
    expr = ast.expressions[0]

    assert isinstance(expr, UnknownExpr)
    assert expr.span == text.span
    assert expr.cst is text
    assert expr.reason == "unsupported CST node: text"
