from hypothesis import given
from hypothesis import strategies as st

from mushy_peas.softcode import parse_expression, render


@given(st.text(max_size=200))
def test_text_only_documents_round_trip(source: str) -> None:
    document = parse_expression(source)

    assert render(document, source) == source


def test_empty_document_has_no_children() -> None:
    document = parse_expression("")

    assert document.children == ()
    assert render(document, "") == ""
