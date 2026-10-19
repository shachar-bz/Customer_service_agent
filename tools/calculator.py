"""calculator tool: safely evaluates an arithmetic expression (no eval) and returns the result rounded to 2 decimals."""
from __future__ import annotations

import ast
import operator
from decimal import ROUND_HALF_UP, Context, Decimal
from typing import Any, Callable, Union

from pydantic import BaseModel, ConfigDict

from tools.base import NonBlankStr

Number = Union[int, float]

RESULT_DECIMAL_PLACES = 2
MAX_EXPONENT = 100
MAX_RESULT_MAGNITUDE = 1e100

ALLOWED_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
ALLOWED_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
ALLOWED_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "round": round,
    "min": min,
    "max": max,
    "abs": abs,
}

CALCULATOR_SCHEMA = {
    "type": "function",
    "name": "calculator",
    "description": (
        """Evaluate an arithmetic expression and return the result rounded to 2 decimal places.
            ALWAYS use this tool for any arithmetic; never compute numbers in your head,
            not even simple sums or differences.
            Use it for, e.g.: totals of several prices, how much more a customer must
            spend to reach premier status, how much a discount or a cheaper product saves,
            or how many days a product will last.
            Supports numbers, + - * / // % **, parentheses, and round(), min(), max(), abs().
            Variables, text, and any other functions are not allowed: write the numbers in."""
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": (
                    "Arithmetic expression using only numbers, e.g. '2000 - (1700 + 129.99)' "
                    "or '(54.99 - 42.50) * 2'."
                ),
            },
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
    "strict": False,
}


class CalculatorArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: NonBlankStr


class CalculatorError(Exception):
    """An expression problem whose message is returned to the LLM as-is."""


def check_magnitude(value: Any) -> Number:
    if isinstance(value, complex):
        raise CalculatorError("The result is not a real number (e.g. a fractional power of a negative number).")
    if abs(value) > MAX_RESULT_MAGNITUDE:
        raise CalculatorError(f"The result is too large (limit is {MAX_RESULT_MAGNITUDE:g}).")
    return value


def describe_node(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return f"name '{node.id}'"
    if isinstance(node, ast.Constant):
        return f"{type(node.value).__name__} value {node.value!r}"
    return type(node).__name__


def evaluate_function_call(node: ast.Call) -> Number:
    if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
        allowed_names = ", ".join(ALLOWED_FUNCTIONS)
        raise CalculatorError(
            f"Function call to {describe_node(node.func)} is not allowed; only {allowed_names} are supported."
        )
    if node.keywords:
        raise CalculatorError(f"{node.func.id}() accepts positional numbers only.")
    # Wrong arity or argument types raise TypeError/ValueError from the builtin; calculator() reports them.
    argument_values = [evaluate_node(argument) for argument in node.args]
    return check_magnitude(ALLOWED_FUNCTIONS[node.func.id](*argument_values))


def evaluate_node(node: ast.AST) -> Number:
    """Recursively evaluate a whitelisted AST node; anything not whitelisted raises CalculatorError."""
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError(f"Only numbers are allowed, not {describe_node(node)}.")
        return check_magnitude(node.value)

    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINARY_OPERATORS:
        left_value = evaluate_node(node.left)
        right_value = evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right_value) > MAX_EXPONENT:
            raise CalculatorError(f"Exponent {right_value} is too large (limit is {MAX_EXPONENT}).")
        return check_magnitude(ALLOWED_BINARY_OPERATORS[type(node.op)](left_value, right_value))

    if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY_OPERATORS:
        return ALLOWED_UNARY_OPERATORS[type(node.op)](evaluate_node(node.operand))

    if isinstance(node, ast.Call):
        return evaluate_function_call(node)

    if isinstance(node, (ast.BinOp, ast.UnaryOp)):
        raise CalculatorError(f"Operator {type(node.op).__name__} is not allowed.")
    raise CalculatorError(f"{describe_node(node)} is not allowed; use only numbers and arithmetic.")


def calculator(expression: str) -> dict[str, Any]:
    try:
        syntax_tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        return {"error": f"Invalid expression syntax: {error.msg.rstrip('.')}."}
    except (ValueError, RecursionError, MemoryError):
        return {"error": "Invalid expression: too long or too deeply nested."}

    try:
        value = evaluate_node(syntax_tree)
    except CalculatorError as error:
        return {"error": str(error)}
    except ZeroDivisionError:
        return {"error": "Division or modulo by zero."}
    except OverflowError:
        return {"error": "The result is too large."}
    except (TypeError, ValueError) as error:
        return {"error": f"Invalid expression: {error}."}
    except RecursionError:
        return {"error": "Invalid expression: too deeply nested."}

    # + 0.0 turns -0.0 into 0.0.
    # Decimal avoids float artifacts (12.1 * 0.95 is 11.495 in binary, which round() sends to 11.49).
    # The wide context keeps quantize from overflowing on results near MAX_RESULT_MAGNITUDE.
    rounded = Decimal(str(float(value))).quantize(
        Decimal(1).scaleb(-RESULT_DECIMAL_PLACES), rounding=ROUND_HALF_UP, context=Context(prec=200)
    )
    return {"result": float(rounded) + 0.0}
