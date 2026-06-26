"""Tests for numeric calculation backend."""

from __future__ import annotations

from 后端 import numeric_calc


def assert_close_text(value: str, expected: float, tolerance: float = 1e-6) -> None:
    assert abs(float(value) - expected) <= tolerance


def test_numeric_integral() -> None:
    assert_close_text(numeric_calc.numeric_integral("x^2", 0, 1), 1 / 3)


def test_numeric_derivative() -> None:
    assert_close_text(numeric_calc.numeric_derivative("sin(x)", 0), 1)


def test_numeric_root() -> None:
    assert_close_text(numeric_calc.numeric_root("x^2 - 2", 0, 2), 2**0.5)


def test_numeric_expression_supports_constants_and_root_symbol() -> None:
    assert_close_text(numeric_calc.numeric_integral("√(x)", 0, 1), 2 / 3)
    assert_close_text(numeric_calc.numeric_derivative("e^x", 0), 1)


def test_numeric_root_rejects_interval_without_sign_change() -> None:
    try:
        numeric_calc.numeric_root("x^2 + 1", -1, 1)
    except numeric_calc.NumericCalculationError as exc:
        assert "无法保证区间内有根" in str(exc)
    else:
        raise AssertionError("root finding should reject intervals without sign change")


def test_numeric_integral_reports_timeout() -> None:
    try:
        numeric_calc.numeric_integral("x", 0, 1, timeout_seconds=0)
    except numeric_calc.NumericCalculationTimeout:
        pass
    else:
        raise AssertionError("integral should report timeout")


def test_numeric_derivative_reports_timeout() -> None:
    try:
        numeric_calc.numeric_derivative("x", 1, timeout_seconds=0)
    except numeric_calc.NumericCalculationTimeout:
        pass
    else:
        raise AssertionError("derivative should report timeout")


def test_numeric_root_reports_timeout() -> None:
    try:
        numeric_calc.numeric_root("x", -10, 10, timeout_seconds=0)
    except numeric_calc.NumericCalculationTimeout:
        pass
    else:
        raise AssertionError("root search should report timeout")
