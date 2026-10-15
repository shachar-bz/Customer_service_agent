import pytest

from tools.base import execute_tool
from tools.calculator import CalculatorArgs, calculator


def run_calculator(raw_args):
    return execute_tool(CalculatorArgs, calculator, raw_args)


def calculate(expression):
    return run_calculator({"expression": expression})


@pytest.mark.parametrize(
    "expression, expected_result",
    [
        ("2000 - 1700", 300.0),
        ("12 * 3", 36.0),
        ("7 / 2", 3.5),
        ("7 // 2", 3.0),
        ("7 % 4", 3.0),
        ("2 ** 10", 1024.0),
        ("-5 + +3", -2.0),
    ],
)
def test_basic_arithmetic(expression, expected_result):
    assert calculate(expression) == {"result": expected_result}


def test_precedence_and_parentheses():
    assert calculate("2 + 3 * 4") == {"result": 14.0}
    assert calculate("(2 + 3) * 4") == {"result": 20.0}
    assert calculate("(54.99 - 42.50) * 2") == {"result": 24.98}


def test_allowed_functions():
    assert calculate("round(2.567, 1)") == {"result": 2.6}
    assert calculate("round(2.5)") == {"result": 2.0}
    assert calculate("min(3, 1.5, 2)") == {"result": 1.5}
    assert calculate("max(3, 1.5, 2)") == {"result": 3.0}
    assert calculate("abs(-4.25)") == {"result": 4.25}


def test_result_is_rounded_to_two_decimals():
    assert calculate("0.1 + 0.2") == {"result": 0.3}
    assert calculate("104.99 * 0.95") == {"result": 99.74}
    assert calculate("10 / 3") == {"result": 3.33}
    assert calculate("-0.001") == {"result": 0.0}


def test_premier_threshold_example():
    assert calculate("2000 - (1700 + 129.99)") == {"result": 170.01}


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "x + 1",
        "(1).real",
        '"a" * 3',
        "True + 1",
        "9 ** 9 ** 9",
        "10 ** 200",
        "1 / 0",
        "5 % 0",
        "2 +",
        "1 < 2",
        "[1, 2][0]",
        "lambda: 1",
        "1j * 2",
        "round(1.5, digits=1)",
        "min(*[1, 2])",
        "abs(1, 2)",
        "max(1)",
        "round(1.234, 1.5)",
        "(-8) ** 0.5",
    ],
)
def test_rejected_expressions_return_error(expression):
    result = calculate(expression)

    assert set(result) == {"error"}
    assert result["error"]


def test_rejection_names_disallowed_element():
    assert "'x'" in calculate("x + 1")["error"]
    assert "__import__" in calculate("__import__('os')")["error"]
    assert "Attribute" in calculate("(1).real")["error"]


def test_invalid_arguments_return_error():
    assert "error" in run_calculator({"expression": "   "})
    assert "error" in run_calculator({})
    assert "error" in run_calculator({"expression": "1 + 1", "extra": True})
