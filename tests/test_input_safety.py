"""Tests for user-friendly input parsing and large-expression guards."""

from __future__ import annotations

from 后端 import numeric_calc, symbolic_calc


def test_symbolic_implicit_multiplication_before_variable() -> None:
    assert symbolic_calc.derivative("2x") == "2"


def test_symbolic_implicit_multiplication_before_function() -> None:
    result = symbolic_calc.solve_equation("3sin(x)=0")
    assert "0" in result


def test_numeric_implicit_multiplication_before_variable() -> None:
    assert abs(float(numeric_calc.numeric_derivative("2x", 0)) - 2) < 1e-6


def test_huge_power_expression_returns_inf() -> None:
    assert symbolic_calc.evaluate_expression("3^2^2^2^2") == "错误"


def test_huge_factorial_expression_returns_inf() -> None:
    assert symbolic_calc.evaluate_expression("1000!") == "错误"


def test_three_level_power_chain_is_rejected_before_sympy_evaluation() -> None:
    assert symbolic_calc.evaluate_expression("2^7^7^7") == "错误"


def test_trigonometric_equation_uses_general_solution() -> None:
    result = symbolic_calc.solve_equation("sin(x)=0")
    assert "k" in result
    assert "π" in result or "蟺" in result
    assert "k为整数" in result


def test_sine_one_uses_a_general_solution() -> None:
    result = symbolic_calc.solve_equation("sin(x)-1")
    assert result == "π/2 + 2kπ（k为整数，含0）"


def test_finite_equation_still_uses_exact_roots() -> None:
    result = symbolic_calc.solve_equation("x^2=4")
    assert "-2" in result
    assert "2" in result
    assert "k为整数" not in result
