"""Numeric calculation functions for PySciCompTool."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Callable

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

try:
    from scipy import integrate, optimize
except Exception:  # pragma: no cover - fallback is tested indirectly when scipy is absent.
    integrate = None
    optimize = None


class NumericCalculationError(ValueError):
    """Raised when numeric calculation input is invalid."""


class NumericCalculationTimeout(NumericCalculationError):
    """Raised when numeric root search takes too long."""


@dataclass(frozen=True)
class NumericExpression:
    expression: sp.Expr
    variable: sp.Symbol
    function: Callable[[float], float]


TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
MAX_POWER_OPERATORS = 4
MAX_FACTORIAL_INPUT = 170
MAX_LITERAL_DIGITS = 2000
MAX_EXPONENT_VALUE = 100000
MAX_RESULT_DIGITS = 5000
NUMERIC_TIMEOUT_SECONDS = 2.0


def _fast_pow(base: object, exp: object) -> object:
    """Fast exponentiation with overflow protection."""
    try:
        base_int = int(base)
        exp_int = int(exp)
    except (TypeError, ValueError):
        return base ** exp

    if exp_int < 0:
        return base_int ** exp_int
    if base_int == 0:
        return 0
    if abs(base_int) == 1:
        return 1 if exp_int % 2 == 0 or base_int == 1 else -1

    try:
        estimated_digits = exp_int * math.log10(abs(base_int))
    except (ValueError, OverflowError):
        estimated_digits = float("inf")

    if estimated_digits > MAX_RESULT_DIGITS:
        return float("inf") if base_int > 0 else float("-inf")

    return pow(base_int, exp_int)


def module_ready() -> bool:
    """Return whether the module can be imported successfully."""
    return True


def _normalize_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise NumericCalculationError(f"{field_name}不能为空。")
    return text


def _local_dict() -> dict[str, object]:
    return {
        "π": sp.pi,
        "pi": sp.pi,
        "e": sp.E,
        "E": sp.E,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "ln": sp.log,
        "log": sp.log,
        "lg": lambda value: sp.log(value, 10),
        "sqrt": sp.sqrt,
        "root": lambda degree, value: sp.root(value, degree),
        "Abs": sp.Abs,
        "pow": _fast_pow,
    }


def _prepare_expression_text(expression: str) -> str:
    text = expression.strip()
    text = text.replace("ⁿ√", "root")
    text = text.replace("√", "sqrt")
    return text


def _has_dangerous_growth(expression: str) -> bool:
    text = _prepare_expression_text(expression)
    if text.count("^") + text.count("**") >= MAX_POWER_OPERATORS:
        return True

    # Check for dangerously large exponents like 10^100000
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*[\^]|[\*]{2}\s*(\d+)", text):
        exp_str = match.group(1) or match.group(2)
        if exp_str:
            try:
                if float(exp_str) > MAX_EXPONENT_VALUE:
                    return True
            except (ValueError, OverflowError):
                return True

    for match in re.finditer(r"(\d+)\s*!", text):
        try:
            if int(match.group(1)) > MAX_FACTORIAL_INPUT:
                return True
        except ValueError:
            return True

    return any(len(match.group(0)) >= MAX_LITERAL_DIGITS for match in re.finditer(r"\d+", text))


def _parse_number(value: float | str, field_name: str) -> float:
    try:
        if _has_dangerous_growth(str(value)):
            return math.inf
        parsed = parse_expr(
            _prepare_expression_text(str(value)),
            local_dict=_local_dict(),
            transformations=TRANSFORMATIONS,
            evaluate=True,
        )
        return float(sp.N(parsed))
    except Exception as exc:
        raise NumericCalculationError(f"{field_name}格式错误。") from exc


def _parse_optional_number(value: float | str | None, field_name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _parse_number(value, field_name)


def _parse_optional_count(value: int | str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        count = int(str(value).strip())
    except ValueError as exc:
        raise NumericCalculationError("解的个数必须是正整数。") from exc
    if count <= 0:
        raise NumericCalculationError("解的个数必须是正整数。")
    return count


def _parse_expression(expression: str, variable: str = "x") -> NumericExpression:
    expression_text = _normalize_text(expression, "表达式")
    variable_text = _normalize_text(variable, "变量")
    if _has_dangerous_growth(expression_text):
        raise NumericCalculationError("表达式过大，已停止计算。")
    if not variable_text.isidentifier():
        raise NumericCalculationError("变量名只能包含字母、数字和下划线，且不能以数字开头。")

    symbol = sp.symbols(variable_text)
    try:
        expr = parse_expr(
            _prepare_expression_text(expression_text),
            local_dict=_local_dict(),
            transformations=TRANSFORMATIONS,
            evaluate=True,
        )
        func = sp.lambdify(symbol, expr, modules=["math"])
    except Exception as exc:
        raise NumericCalculationError(f"表达式格式错误：{expression_text}") from exc

    def wrapped(x_value: float) -> float:
        try:
            result = func(x_value)
            result = float(result)
        except Exception as exc:
            raise NumericCalculationError("表达式在当前数值下无法计算。") from exc
        if not math.isfinite(result):
            raise NumericCalculationError("计算结果不是有限数值。")
        return result

    return NumericExpression(expr, symbol, wrapped)


def _format_numeric(value: float, digits: int = 12) -> str:
    if abs(value) < 1e-14:
        value = 0.0
    return f"{value:.{digits}g}"


def _deadline_function(function: Callable[[float], float], deadline: float) -> Callable[[float], float]:
    """Return a callback that lets SciPy and fallback loops stop at the deadline."""
    def timed(value: float) -> float:
        if time.perf_counter() > deadline:
            raise NumericCalculationTimeout("数值计算超时。")
        result = function(value)
        if time.perf_counter() > deadline:
            raise NumericCalculationTimeout("数值计算超时。")
        return result

    return timed


def numeric_integral(
    expression: str,
    lower: float | str,
    upper: float | str,
    variable: str = "x",
    timeout_seconds: float = NUMERIC_TIMEOUT_SECONDS,
) -> str:
    """Calculate a definite integral numerically."""
    parsed = _parse_expression(expression, variable)
    a = _parse_number(lower, "积分下限")
    b = _parse_number(upper, "积分上限")

    if a == b:
        return "0"

    deadline = time.perf_counter() + timeout_seconds
    function = _deadline_function(parsed.function, deadline)

    if integrate is not None:
        try:
            result, _error = integrate.quad(function, a, b, limit=100)
            if time.perf_counter() > deadline:
                raise NumericCalculationTimeout("数值计算超时。")
            return _format_numeric(float(result))
        except NumericCalculationTimeout:
            raise
        except Exception as exc:
            raise NumericCalculationError("数值积分失败，请检查函数和区间。") from exc

    n = 10000
    step = (b - a) / n
    total = 0.5 * (function(a) + function(b))
    for i in range(1, n):
        total += function(a + i * step)
    return _format_numeric(total * step)


def numeric_derivative(
    expression: str,
    point: float | str,
    variable: str = "x",
    step: float = 1e-5,
    timeout_seconds: float = NUMERIC_TIMEOUT_SECONDS,
) -> str:
    """Calculate a numeric derivative at a point."""
    parsed = _parse_expression(expression, variable)
    x0 = _parse_number(point, "求导点")
    function = _deadline_function(parsed.function, time.perf_counter() + timeout_seconds)
    try:
        result = (function(x0 + step) - function(x0 - step)) / (2 * step)
    except NumericCalculationError:
        raise
    except Exception as exc:
        raise NumericCalculationError("数值求导失败，请检查函数和求导点。") from exc
    return _format_numeric(result)


def numeric_root(
    expression: str,
    lower: float | str,
    upper: float | str,
    variable: str = "x",
) -> str:
    """Find one numeric root in the interval."""
    parsed = _parse_expression(expression, variable)
    a = _parse_number(lower, "区间下限")
    b = _parse_number(upper, "区间上限")
    if a >= b:
        raise NumericCalculationError("区间下限必须小于区间上限。")

    fa = parsed.function(a)
    fb = parsed.function(b)
    if abs(fa) < 1e-12:
        return _format_numeric(a)
    if abs(fb) < 1e-12:
        return _format_numeric(b)
    if fa * fb > 0:
        raise NumericCalculationError("区间两端函数值同号，无法保证区间内有根。")

    if optimize is not None:
        try:
            result = optimize.brentq(parsed.function, a, b)
            return _format_numeric(float(result))
        except Exception as exc:
            raise NumericCalculationError("数值求根失败，请检查函数和区间。") from exc

    left, right = a, b
    for _ in range(100):
        mid = (left + right) / 2
        fm = parsed.function(mid)
        if abs(fm) < 1e-12:
            return _format_numeric(mid)
        if parsed.function(left) * fm <= 0:
            right = mid
        else:
            left = mid
    return _format_numeric((left + right) / 2)


def numeric_root(
    expression: str,
    lower: float | str | None = None,
    upper: float | str | None = None,
    variable: str = "x",
    root_count: int | str | None = None,
    timeout_seconds: float = NUMERIC_TIMEOUT_SECONDS,
) -> str:
    """Find numeric roots in the interval or a default search window."""
    parsed = _parse_expression(expression, variable)
    a = _parse_optional_number(lower, "区间下限")
    b = _parse_optional_number(upper, "区间上限")
    count = _parse_optional_count(root_count)
    if a is None and b is None:
        a, b = -100.0, 100.0
    elif a is None:
        a = b - 200.0
    elif b is None:
        b = a + 200.0

    if a >= b:
        raise NumericCalculationError("区间下限必须小于区间上限。")

    deadline = time.perf_counter() + timeout_seconds
    function = _deadline_function(parsed.function, deadline)
    max_roots = count or 20
    samples = 2000
    step = (b - a) / samples
    roots: list[float] = []

    def check_timeout() -> None:
        if time.perf_counter() > deadline:
            raise NumericCalculationTimeout("计算超时，请输入需要解的个数或设置上下界。")

    def add_root(value: float) -> None:
        if math.isfinite(value) and all(abs(value - item) > 1e-7 for item in roots):
            roots.append(value)

    def bisect(left: float, right: float) -> float:
        f_left = function(left)
        for _ in range(80):
            check_timeout()
            mid = (left + right) / 2
            f_mid = function(mid)
            if abs(f_mid) < 1e-12:
                return mid
            if f_left * f_mid <= 0:
                right = mid
            else:
                left = mid
                f_left = f_mid
        return (left + right) / 2

    prev_x: float | None = None
    prev_y: float | None = None
    for index in range(samples + 1):
        check_timeout()
        x_value = a + index * step
        try:
            y_value = function(x_value)
        except NumericCalculationError:
            prev_x = None
            prev_y = None
            continue

        if abs(y_value) < 1e-8:
            add_root(x_value)
        if prev_x is not None and prev_y is not None and prev_y * y_value < 0:
            try:
                if optimize is not None:
                    root = optimize.brentq(function, prev_x, x_value, maxiter=80)
                else:
                    root = bisect(prev_x, x_value)
                add_root(float(root))
            except NumericCalculationTimeout:
                raise
            except Exception:
                pass

        if len(roots) >= max_roots:
            break
        prev_x = x_value
        prev_y = y_value

    if not roots:
        raise NumericCalculationError("无法保证区间内有根，未找到满足条件的根。")
    roots.sort()
    return ", ".join(_format_numeric(root) for root in roots[:max_roots])
