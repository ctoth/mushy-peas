from pathlib import Path

from mushy_peas.softcode import (
    AssignmentStmt,
    BraceExpr,
    DolistStmt,
    DynamicExpr,
    EvalExpr,
    FunctionCall,
    FunctionExpr,
    ParseMode,
    SubstitutionExpr,
    SwitchStmt,
    TriggerStmt,
    UnknownExpr,
    WaitStmt,
    build_action_ast_view,
)
from mushy_peas.softcode.actions import parse_action_list
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


def test_substitutions_project_to_substitution_expr() -> None:
    source = "%n $1"
    document = parse_expression(source, mode=ParseMode(dollar_substitutions=True))

    ast = build_ast_view(document)
    percent = ast.expressions[0]
    dollar = ast.expressions[2]

    assert isinstance(percent, SubstitutionExpr)
    assert percent.span == document.children[0].span
    assert percent.cst is document.children[0]
    assert percent.substitution_kind == "percent"
    assert percent.raw == "%n"
    assert isinstance(dollar, SubstitutionExpr)
    assert dollar.span == document.children[2].span
    assert dollar.cst is document.children[2]
    assert dollar.substitution_kind == "dollar"
    assert dollar.raw == "$1"


def test_groups_project_recursive_ast_children() -> None:
    source = "{%n}[add(1,2)]"
    registry = load_function_registry(FIXTURE)
    document = parse_expression(source, metadata=registry)

    ast = build_ast_view(document)
    brace = ast.expressions[0]
    eval_group = ast.expressions[1]

    assert isinstance(brace, BraceExpr)
    assert brace.span == document.children[0].span
    assert brace.cst is document.children[0]
    assert isinstance(brace.expressions[0], SubstitutionExpr)
    assert isinstance(eval_group, EvalExpr)
    assert eval_group.span == document.children[1].span
    assert eval_group.cst is document.children[1]
    assert isinstance(eval_group.expressions[0], FunctionExpr)


def test_ast_projection_is_total_over_unsupported_cst_nodes() -> None:
    text = Text(span=Span(0, 4))
    document = Document(span=Span(0, 4), children=(text,))

    ast = build_ast_view(document)
    expr = ast.expressions[0]

    assert isinstance(expr, UnknownExpr)
    assert expr.span == text.span
    assert expr.cst is text
    assert expr.reason == "unsupported CST node: text"


def test_action_ast_projects_assignment_statement() -> None:
    source = "@pemit %#=hello"
    action_list = parse_action_list(source)

    ast = build_action_ast_view(action_list)
    stmt = ast.statements[0]
    assignment = action_list.statements[0].assignment

    assert isinstance(stmt, AssignmentStmt)
    assert assignment is not None
    assert ast.span == action_list.span
    assert ast.cst is action_list
    assert stmt.span == assignment.span
    assert stmt.cst is assignment
    assert stmt.lhs == Span(7, 9)
    assert stmt.rhs == Span(10, len(source))


def test_action_ast_projects_trigger_dolist_and_switch_statements() -> None:
    source = (
        "@trigger #10/A=one;"
        "@dolist one two={@emit ##};"
        "@wait 3={@emit later};"
        "@switch foo=bar,@emit yes"
    )
    action_list = parse_action_list(source)

    ast = build_action_ast_view(action_list)
    trigger = ast.statements[0]
    dolist = ast.statements[1]
    wait = ast.statements[2]
    switch = ast.statements[3]

    assert isinstance(trigger, TriggerStmt)
    assert action_list.statements[0].trigger is not None
    assert trigger.cst is action_list.statements[0].trigger
    assert trigger.target == Span(9, 14)
    assert trigger.arguments == Span(15, 18)
    assert isinstance(dolist, DolistStmt)
    assert action_list.statements[1].dolist is not None
    assert dolist.cst is action_list.statements[1].dolist
    assert dolist.list_expr == Span(27, 34)
    assert dolist.body == Span(35, 45)
    assert isinstance(wait, WaitStmt)
    assert action_list.statements[2].wait is not None
    assert wait.cst is action_list.statements[2].wait
    assert wait.delay == Span(52, 53)
    assert wait.body == Span(54, 67)
    assert isinstance(switch, SwitchStmt)
    assert action_list.statements[3].switch is not None
    assert switch.cst is action_list.statements[3].switch
    assert switch.subject == Span(76, 79)
    assert len(switch.cases) == 1
    assert switch.cases[0].pattern == Span(80, 83)
    assert switch.cases[0].action == Span(84, len(source))


def test_action_ast_projects_empty_statement_to_dynamic_expr() -> None:
    action_list = parse_action_list("")

    ast = build_action_ast_view(action_list)
    stmt = ast.statements[0]

    assert isinstance(stmt, DynamicExpr)
    assert stmt.span == Span(0, 0)
    assert stmt.cst is action_list.statements[0]
    assert stmt.reason == "empty command statement"
