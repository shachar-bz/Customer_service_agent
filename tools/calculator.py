"""calculator tool: safely evaluates an arithmetic expression (no eval) and returns the result rounded to 2 decimals."""
from __future__ import annotations

import ast
import math
import operator
from typing import Any, Callable, Union

from pydantic import BaseModel, ConfigDict, field_validator

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
# Function name -> (callable, min positional args, max positional args).
ALLOWED_FUNCTIONS: dict[str, tuple[Callable[..., Any], int, float]] = {
    "round": (round, 1, 2),
    "min": (min, 2, math.inf),
    "max": (max, 2, math.inf),
    "abs": (abs, 1, 1),
}

CALCULATOR_SCHEMA = {
    "type": "function",
    "function": {
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
    },
}


class CalculatorArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str

    @field_validator("expression")
    @classmethod
    def reject_blank_expression(cls, expression: str) -> str:
        stripped_expression = expression.strip()
        if not stripped_expression:
            raise ValueError("must not be blank")
        return stripped_expression


class CalculatorError(Exception):
    """An expression problem whose message is returned to the LLM as-is."""


def check_magnitude(value: Any) -> Number:
    if isinstance(value, complex):
        raise CalculatorError("The result is not a real number (e.g. a fractional power of a negative number).")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculatorError("The result is too large.")
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
    function_name = node.func.id
    if node.keywords or any(isinstance(argument, ast.Starred) for argument in node.args):
        raise CalculatorError(f"{function_name}() accepts positional numbers only.")

    function, min_args, max_args = ALLOWED_FUNCTIONS[function_name]
    if not min_args <= len(node.args) <= max_args:
        expected = f"{min_args}" if min_args == max_args else (
            f"{min_args} or more" if max_args == math.inf else f"{min_args} to {int(max_args)}"
        )
        raise CalculatorError(f"{function_name}() takes {expected} arguments, got {len(node.args)}.")

    argument_values = [evaluate_node(argument) for argument in node.args]
    if function_name == "round" and len(argument_values) == 2 and not isinstance(argument_values[1], int):
        raise CalculatorError("round()'s second argument (number of digits) must be a whole number.")
    return check_magnitude(function(*argument_values))


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
    return {"result": round(float(value), RESULT_DECIMAL_PLACES) + 0.0}
