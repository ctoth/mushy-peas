import pytest

from mushy_peas.softcode.model import Span


def test_span_rejects_negative_start() -> None:
    with pytest.raises(ValueError, match="start must be non-negative"):
        Span(-1, 0)


def test_span_rejects_end_before_start() -> None:
    with pytest.raises(ValueError, match="end must be greater"):
        Span(2, 1)
