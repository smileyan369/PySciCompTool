"""Symbolic calculation functions for PySciCompTool."""

from __future__ import annotations

import concurrent.futures
import math
import re
from dataclasses import dataclass

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    factorial_notation,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


class SymbolicCalculationError(ValueError):
    """Raised when symbolic calculation input is invalid."""


@dataclass(frozen=True)
class ParsedExpression:
    expression: sp.Expr
    variable: sp.Symbol


TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
    factorial_notation,
)
# Three right-associative powers such as 2^7^7^7 already create an
# astronomically large integer before SymPy can simplify it.
MAX_POWER_OPERATORS = 3
MAX_FACTORIAL_INPUT = 170
MAX_LITERAL_DIGITS = 2000
MAX_EXPONENT_VALUE = 100000
MAX_RESULT_DIGITS = 5000


def _fast_pow(base: object, exp: object) -> object:
    """Fast exponentiation using Python's built-in pow for integer bases.

    For integer^integer, uses O(log n) exponentiation.
    For large exponents that would produce enormous results, returns infinity.
    """
    try:
        base_int = int(base)
        exp_int = int(exp)
    except (TypeError, ValueError):
        return base ** exp

    if exp_int < 0:
        return base_int ** exp_int

    # Estimate result digit count: exp * log10(base)
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
        raise SymbolicCalculationError(f"{field_name}不能为空。")
    return text


def _parse_variable(variable: str = "x") -> sp.Symbol:
    variable_text = _normalize_text(variable, "变量")
    if not variable_text.isidentifier():
        raise SymbolicCalculationError("变量名只能包含字母、数字和下划线，且不能以数字开头。")
    return sp.symbols(variable_text)


def _local_dict() -> dict[str, object]:
    return {
        "π": sp.pi,
        "pi": sp.pi,
        "e": sp.E,
        "E": sp.E,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "Abs": sp.Abs,
        "ln": sp.log,
        "log": sp.log,
        "lg": lambda value: sp.log(value, 10),
        "sqrt": sp.sqrt,
        "root": lambda degree, value: sp.root(value, degree),
        "fact": sp.factorial,
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

    # Check for dangerously large exponents like 10^100000.  The exponent is
    # the number after ^ or **, not the base before it.
    for match in re.finditer(r"(?:\^|\*\*)\s*(\d+(?:\.\d+)?)", text):
        exp_str = match.group(1)
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


def _parse_math_expression(expression: str) -> sp.Expr:
    if _has_dangerous_growth(expression):
        raise SymbolicCalculationError("表达式过大，已停止计算。")
    return parse_expr(
        _prepare_expression_text(expression),
        local_dict=_local_dict(),
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )


def _parse_expression(expression: str, variable: str = "x") -> ParsedExpression:
    expression_text = _normalize_text(expression, "表达式")
    symbol = _parse_variable(variable)
    try:
        expr = _parse_math_expression(expression_text)
    except Exception as exc:
        raise SymbolicCalculationError(f"表达式格式错误：{expression_text}") from exc
    return ParsedExpression(expr, symbol)


def _format_result(value: object) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_format_result(item) for item in value)

    if isinstance(value, sp.Basic) and value.has(sp.I):
        return _format_complex(value)

    return _format_plain(value)


def _format_plain(value: object) -> str:
    text = str(value)
    text = text.replace("pi", "π")
    text = text.replace("I", "i")
    text = text.replace("E", "e")
    text = text.replace("exp(", "e^(")
    text = text.replace("sqrt(", "√(")
    return text


def _format_complex(value: sp.Basic) -> str:
    real_part, imag_part = sp.simplify(value).as_real_imag()
    real_part = sp.simplify(real_part)
    imag_part = sp.simplify(imag_part)

    if imag_part == 0:
        return _format_plain(real_part)

    imag_abs = sp.simplify(abs(imag_part))
    imag_text = "i" if imag_abs == 1 else f"{_format_plain(imag_abs)}i"

    if real_part == 0:
        return imag_text if imag_part > 0 else f"-{imag_text}"

    real_text = _format_plain(real_part)
    sign = "+" if imag_part > 0 else "-"
    return f"{real_text} {sign} {imag_text}"


def _format_numeric(value: object, digits: int = 12) -> str:
    text = f"{float(value):.{digits}g}"
    return text.replace("e", "E")


def _format_general_expr(value: sp.Expr) -> str:
    parameter = sp.symbols("k", integer=True)
    value = sp.simplify(value)
    coefficient = sp.simplify(value.coeff(parameter))
    rest = sp.simplify(value - coefficient * parameter)
    if coefficient != 0 and rest == 0:
        text = f"k{_format_plain(coefficient)}"
    else:
        text = _format_plain(value)
    return text.replace("*", "")


def _imageset_expression(solution_set: object) -> tuple[sp.Expr, sp.Set] | None:
    if not isinstance(solution_set, sp.ImageSet):
        return None
    lamda = solution_set.lamda
    if len(lamda.variables) != 1:
        return None
    if solution_set.base_set != sp.S.Integers:
        return None
    parameter = sp.symbols("k", integer=True)
    expr = lamda.expr.subs(lamda.variables[0], parameter)
    return sp.simplify(expr), solution_set.base_set


def _combine_integer_imageset_expressions(expressions: list[sp.Expr]) -> sp.Expr | None:
    if len(expressions) < 2:
        return None

    parameter = sp.symbols("k", integer=True)
    expressions = [sp.expand(expr) for expr in expressions]
    coeffs = [sp.simplify(expr.coeff(parameter)) for expr in expressions]
    if len(set(coeffs)) != 1 or coeffs[0] == 0:
        return None

    coefficient = coeffs[0]
    constants = [sp.simplify(expr - coefficient * parameter) for expr in expressions]
    constants = sorted(constants, key=lambda value: float(sp.N(value)))
    step = sp.simplify(coefficient / len(constants))
    if step == 0:
        return None

    for index, constant in enumerate(constants):
        if sp.simplify(constant - constants[0] - index * step) != 0:
            return None

    return sp.simplify(constants[0] + step * parameter)


def _format_general_solution(solution_set: object) -> str | None:
    parameter = sp.symbols("k", integer=True)
    if solution_set in (sp.S.EmptySet, sp.S.Reals, sp.S.Complexes):
        return None
    if isinstance(solution_set, sp.FiniteSet):
        return None
    if isinstance(solution_set, sp.ConditionSet):
        return None

    sets = list(solution_set.args) if isinstance(solution_set, sp.Union) else [solution_set]
    expressions: list[sp.Expr] = []
    for item in sets:
        parsed = _imageset_expression(item)
        if parsed is None:
            return None
        expr, _base_set = parsed
        expressions.append(sp.simplify(expr))

    combined = _combine_integer_imageset_expressions(expressions)
    if combined is not None:
        return f"{_format_general_expr(combined)}（k为整数，含0）"

    text = ", ".join(_format_general_expr(expr) for expr in expressions)
    return f"{text}（k为整数，含0）"


def _parse_equation(expression: str, variable: str = "x") -> tuple[sp.Expr, sp.Symbol]:
    expression_text = _normalize_text(expression, "方程")
    symbol = _parse_variable(variable)
    try:
        if "=" in expression_text:
            left_text, right_text = expression_text.split("=", 1)
            if not left_text.strip() or not right_text.strip():
                raise SymbolicCalculationError("等号左右两边都需要输入内容。")
            left = _parse_math_expression(left_text)
            right = _parse_math_expression(right_text)
            return left - right, symbol

        return _parse_math_expression(expression_text), symbol
    except SymbolicCalculationError:
        raise
    except Exception as exc:
        raise SymbolicCalculationError(f"方程格式错误：{expression_text}") from exc


def evaluate_expression(expression: str) -> str:
    """Calculate or simplify a symbolic expression."""
    if _has_dangerous_growth(expression):
        return "错误"
    parsed = _parse_expression(expression)
    simplified = sp.simplify(parsed.expression)
    if simplified in (sp.oo, -sp.oo, sp.zoo, sp.nan):
        raise SymbolicCalculationError("表达式在当前取值下没有定义。")
    if simplified.is_Integer and len(str(abs(int(simplified)))) > 308:
        return "inf"
    if not simplified.free_symbols:
        try:
            numeric_value = sp.N(simplified, 18)
            if numeric_value in (sp.oo, -sp.oo, sp.zoo, sp.nan) or numeric_value.is_finite is False:
                raise SymbolicCalculationError("表达式在当前取值下没有定义。")
            try:
                if abs(float(numeric_value)) > 1e308:
                    return "inf"
            except OverflowError:
                return "inf"
            return _format_numeric(numeric_value)
        except SymbolicCalculationError:
            raise
        except Exception:
            return _format_result(simplified)
    raise SymbolicCalculationError("表达式中包含未知内容，无法作为普通计算求值。")


def derivative(expression: str, variable: str = "x") -> str:
    """Differentiate an expression by variable."""
    parsed = _parse_expression(expression, variable)
    result = sp.diff(parsed.expression, parsed.variable)
    return _format_result(sp.simplify(result))


def indefinite_integral(expression: str, variable: str = "x") -> str:
    """Calculate an indefinite integral."""
    parsed = _parse_expression(expression, variable)
    result = sp.integrate(parsed.expression, parsed.variable)
    return f"{_format_result(result)} + C"


def definite_integral(
    expression: str,
    variable: str = "x",
    lower: float | str = 0,
    upper: float | str = 1,
) -> str:
    """Calculate a definite integral."""
    parsed = _parse_expression(expression, variable)
    try:
        lower_value = _parse_math_expression(str(lower))
        upper_value = _parse_math_expression(str(upper))
    except Exception as exc:
        raise SymbolicCalculationError("定积分上下限格式错误。") from exc

    result = sp.integrate(parsed.expression, (parsed.variable, lower_value, upper_value))
    return _format_result(sp.simplify(result))


def _solve_equation_worker(expression_text: str, variable_text: str) -> str:
    """Worker function executed in a subprocess for timeout control."""
    import sympy as sp  # noqa: F811 - re-import in subprocess

    from sympy.parsing.sympy_parser import (  # noqa: F811
        convert_xor,
        factorial_notation,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    _transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
        factorial_notation,
    )
    symbol = sp.symbols(variable_text)

    if "=" in expression_text:
        left_text, right_text = expression_text.split("=", 1)
        left = parse_expr(
            left_text.strip(),
            local_dict=_worker_local_dict(),
            transformations=_transformations,
            evaluate=True,
        )
        right = parse_expr(
            right_text.strip(),
            local_dict=_worker_local_dict(),
            transformations=_transformations,
            evaluate=True,
        )
        equation_expr = left - right
    else:
        equation_expr = parse_expr(
            expression_text.strip(),
            local_dict=_worker_local_dict(),
            transformations=_transformations,
            evaluate=True,
        )

    # Try solveset first for general solutions
    try:
        solution_set = sp.solveset(sp.Eq(equation_expr, 0), symbol, domain=sp.S.Reals)
        general = _format_general_solution_worker(solution_set)
        if general:
            return general
    except Exception:
        pass

    # Try explicit roots and solve
    solutions: list[sp.Expr] = []
    try:
        root_map = sp.roots(equation_expr, symbol)
        for root in root_map:
            solutions.append(root)
    except Exception:
        pass

    if not solutions:
        try:
            solutions = sp.solve(sp.Eq(equation_expr, 0), symbol)
        except Exception:
            pass

    if not solutions:
        return "未找到解析解。"

    return _format_result_worker([sp.simplify(s) for s in solutions])


def _worker_local_dict() -> dict[str, object]:
    import math as _math
    import sympy as sp
    def _worker_pow(base, exp):
        try:
            b, e = int(base), int(exp)
        except (TypeError, ValueError):
            return base ** exp
        if e < 0:
            return b ** e
        if b == 0:
            return 0
        if abs(b) == 1:
            return 1 if e % 2 == 0 or b == 1 else -1
        try:
            est = e * _math.log10(abs(b))
        except (ValueError, OverflowError):
            est = float("inf")
        if est > MAX_RESULT_DIGITS:
            return float("inf") if b > 0 else float("-inf")
        return pow(b, e)
    return {
        "π": sp.pi, "pi": sp.pi,
        "e": sp.E, "E": sp.E,
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "Abs": sp.Abs,
        "ln": sp.log, "log": sp.log,
        "lg": lambda v: sp.log(v, 10),
        "sqrt": sp.sqrt,
        "pow": _worker_pow,
    }


def _format_result_worker(values: object) -> str:
    import sympy as sp
    if isinstance(values, (list, tuple, set)):
        return ", ".join(_format_result_worker(item) for item in values)

    if isinstance(values, sp.Basic) and values.has(sp.I):
        real, imag = sp.simplify(values).as_real_imag()
        real = sp.simplify(real)
        imag = sp.simplify(imag)
        imag_abs = sp.simplify(abs(imag))
        imag_text = "i" if imag_abs == 1 else f"{_format_plain_worker(imag_abs)}i"
        if real == 0:
            return imag_text if imag > 0 else f"-{imag_text}"
        real_text = _format_plain_worker(real)
        sign = "+" if imag > 0 else "-"
        return f"{real_text} {sign} {imag_text}"

    return _format_plain_worker(values)


def _format_plain_worker(value: object) -> str:
    text = str(value)
    text = text.replace("pi", "π")
    text = text.replace("I", "i")
    text = text.replace("E", "e")
    text = text.replace("exp(", "e^(")
    text = text.replace("sqrt(", "√(")
    return text


def _format_general_solution_worker(solution_set: object) -> str | None:
    import sympy as sp
    parameter = sp.symbols("k", integer=True)

    if solution_set in (sp.S.EmptySet, sp.S.Reals, sp.S.Complexes):
        return None
    if isinstance(solution_set, sp.FiniteSet):
        return None
    if isinstance(solution_set, sp.ConditionSet):
        return None

    sets = list(solution_set.args) if isinstance(solution_set, sp.Union) else [solution_set]
    expressions: list[sp.Expr] = []
    for item in sets:
        if not isinstance(item, sp.ImageSet):
            return None
        lamda = item.lamda
        if len(lamda.variables) != 1:
            return None
        if item.base_set != sp.S.Integers:
            return None
        expr = lamda.expr.subs(lamda.variables[0], parameter)
        expressions.append(sp.simplify(expr))

    if not expressions:
        return None

    if len(expressions) >= 2:
        coeffs = [sp.simplify(expr.coeff(parameter)) for expr in expressions]
        if len(set(coeffs)) == 1 and coeffs[0] != 0:
            coefficient = coeffs[0]
            constants = sorted(
                [sp.simplify(expr - coefficient * parameter) for expr in expressions],
                key=lambda v: float(sp.N(v)),
            )
            step = sp.simplify(coefficient / len(constants))
            if step != 0:
                all_match = True
                for idx, c in enumerate(constants):
                    if sp.simplify(c - constants[0] - idx * step) != 0:
                        all_match = False
                        break
                if all_match:
                    combined = sp.simplify(constants[0] + step * parameter)
                    return f"{_format_general_expr_worker(combined)}（k为整数，含0）"

    text = ", ".join(_format_general_expr_worker(expr) for expr in expressions)
    return f"{text}（k为整数，含0）"


def _format_general_expr_worker(value: sp.Expr) -> str:
    text = str(value)
    text = text.replace("pi", "π")
    text = text.replace("*", "")
    return text




def solve_equation(expression: str, variable: str = "x") -> str:
    """Solve an equation for variable, keeping exact roots when possible.

    If infinitely many solutions exist, a general formula is returned.
    General solutions are preferred when SymPy can derive them.
    """
    expression_text = _normalize_text(expression, "方程")
    variable_text = _normalize_text(variable, "变量")
    if not variable_text.isidentifier():
        raise SymbolicCalculationError("变量名只能包含字母、数字和下划线，且不能以数字开头。")

    # Resolve common forms in the already-loaded SymPy process.  These are
    # deterministic and avoid treating Windows process startup time as solve time.
    equation_expr, symbol = _parse_equation(expression, variable)
    trig_general = _simple_trig_zero_solution(equation_expr, symbol)
    if trig_general is not None:
        return trig_general

    # Low-degree polynomials have finite exact roots and are fast to enumerate.
    try:
        if equation_expr.is_polynomial(symbol) and sp.degree(equation_expr, symbol) <= 4:
            roots = list(sp.roots(equation_expr, symbol))
            if roots:
                return _format_result([sp.simplify(root) for root in roots])
    except Exception:
        pass

    # Let SymPy finish complex cases without imposing an arbitrary deadline.
    prepared_expr = _prepare_expression_text(expression_text)
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_solve_equation_worker, prepared_expr, variable_text)
            result = future.result()
    except Exception:
        result = None

    if result and result != "未找到解析解。":
        return result
    return "错误"


def _simple_trig_zero_solution(equation_expr: sp.Expr, symbol: sp.Symbol) -> str | None:
    """Return real general solutions for one-term sine, cosine and tangent."""
    reduced = sp.factor(sp.trigsimp(equation_expr))
    parameter = "k为整数，含0）"
    for trig_expr, kind in ((sp.sin(symbol), "sin"), (sp.cos(symbol), "cos"), (sp.tan(symbol), "tan")):
        try:
            coefficient = sp.simplify(reduced.coeff(trig_expr))
            constant = sp.simplify(reduced - coefficient * trig_expr)
        except Exception:
            continue
        if coefficient == 0 or constant.has(symbol):
            continue
        value = sp.simplify(-constant / coefficient)
        if value.has(symbol):
            continue
        if kind == "sin":
            if value == 0:
                return f"kπ（{parameter}"
            if value == 1:
                return f"π/2 + 2kπ（{parameter}"
            if value == -1:
                return f"-π/2 + 2kπ（{parameter}"
        elif kind == "cos":
            if value == 0:
                return f"π/2 + kπ（{parameter}"
            if value == 1:
                return f"2kπ（{parameter}"
            if value == -1:
                return f"π + 2kπ（{parameter}"
        elif kind == "tan" and value == 0:
            return f"kπ（{parameter}"
    return None


def _is_infinite_solution(solution: sp.Expr) -> bool:
    """Check if a solution contains free symbols (like integer parameters)."""
    return bool(solution.free_symbols)


def fourier_transform(
    expression: str,
    variable: str = "x",
    frequency: str = "k",
) -> str:
    """Calculate the symbolic Fourier transform."""
    parsed = _parse_expression(expression, variable)
    frequency_symbol = _parse_variable(frequency)
    try:
        result = sp.fourier_transform(parsed.expression, parsed.variable, frequency_symbol)
    except Exception as exc:
        raise SymbolicCalculationError("傅里叶变换失败，请尝试更简单的表达式。") from exc
    return _format_result(result)
