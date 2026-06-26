"""Tests for symbolic calculation backend."""

from __future__ import annotations

from 后端 import symbolic_calc


def test_evaluate_expression_simplifies_expression() -> None:
    assert symbolic_calc.evaluate_expression("sin(x)**2 + cos(x)**2") == "1"


def test_derivative() -> None:
    assert symbolic_calc.derivative("x**2") == "2*x"


def test_indefinite_integral() -> None:
    assert symbolic_calc.indefinite_integral("x") == "x**2/2 + C"


def test_definite_integral() -> None:
    assert symbolic_calc.definite_integral("x", "x", 0, 1) == "1/2"


def test_solve_equation() -> None:
    result = symbolic_calc.solve_equation("x**2 - 4")
    assert "-2" in result
    assert "2" in result


def test_solve_equation_with_equal_sign() -> None:
    result = symbolic_calc.solve_equation("x**2 = 4")
    assert "-2" in result
    assert "2" in result


def test_solve_equation_without_equal_sign_means_equal_zero() -> None:
    result = symbolic_calc.solve_equation("sin(x)")
    assert "0" in result


def test_pi_constant_displays_decimal_in_normal_calculation() -> None:
    assert symbolic_calc.evaluate_expression("pi").startswith("3.14159")
    assert symbolic_calc.evaluate_expression("π").startswith("3.14159")


def test_e_constant_displays_decimal_in_normal_calculation() -> None:
    assert symbolic_calc.evaluate_expression("e").startswith("2.71828")


def test_e_display_uses_lowercase_symbol() -> None:
    assert symbolic_calc.derivative("e**x") == "e^(x)"


def test_factorial() -> None:
    assert symbolic_calc.evaluate_expression("5!") == "120"


def test_nth_root() -> None:
    assert symbolic_calc.evaluate_expression("root(3, 8)") == "2"


def test_square_root_result_uses_symbol() -> None:
    assert symbolic_calc.solve_equation("x**2 = 2") == "-√(2), √(2)"


def test_complex_roots_use_i() -> None:
    result = symbolic_calc.solve_equation("x**2 = -1")
    assert "-i" in result
    assert "i" in result
    assert "I" not in result


def test_complex_roots_put_i_after_coefficient() -> None:
    result = symbolic_calc.solve_equation("x**2 + 2*x + 4 = 0")
    assert "-1 - √(3)i" in result
    assert "-1 + √(3)i" in result
    assert "i/" not in result


def test_repeated_roots_are_shown_once() -> None:
    assert symbolic_calc.solve_equation("(x - 1)**2 = 0") == "1"


def test_lg_is_base_10_log() -> None:
    assert symbolic_calc.evaluate_expression("lg(100)") == "2"


def test_log_is_natural_log() -> None:
    assert symbolic_calc.evaluate_expression("log(100)").startswith("4.605170")


def test_ln_is_natural_log() -> None:
    assert symbolic_calc.evaluate_expression("ln(e)") == "1"


def test_invalid_expression_raises_clear_error() -> None:
    try:
        symbolic_calc.derivative("sin(")
    except symbolic_calc.SymbolicCalculationError as exc:
        assert "表达式格式错误" in str(exc)
    else:
        raise AssertionError("invalid expression should raise SymbolicCalculationError")


def test_unknown_text_is_not_returned_as_normal_result() -> None:
    try:
        symbolic_calc.evaluate_expression("printdsadas")
    except symbolic_calc.SymbolicCalculationError as exc:
        assert "未知内容" in str(exc)
    else:
        raise AssertionError("unknown text should not be returned as a result")
