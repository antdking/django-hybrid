from typing import Any

import pytest
from django.db.models import Avg, CharField, ExpressionWrapper, F, Value

from django_properties.expression_wrapper.wrap import wrap


def obj(**kwargs: Any) -> object:
    return type('fakeObject', (object,), kwargs)


@pytest.mark.parametrize('expected,value', [
    ('test', Value('test')),
    (1.0, Value(1.0)),
    (str(1), Value(1, output_field=CharField())),
    (1 + 1, Value(1) + Value(1)),
    (6 % 5, Value(6) % Value(5))
])
def test_value(expected: Any, value: Any) -> None:
    wrapped_value = wrap(value)
    python_value = wrapped_value.as_python(None)
    assert python_value == expected


@pytest.mark.parametrize('field_name,value', [
    ('test1', 1.0),
    ('test2', 'value'),
])
def test_field(field_name: str, value: Any) -> None:
    fake_obj = obj(**{field_name: value})
    field = F(field_name)
    wrapped_field = wrap(field)

    output_value = wrapped_field.as_python(fake_obj)
    assert output_value == value


@pytest.mark.parametrize('expected,obj,expression', [
    (5, obj(f1=3, f2=2), F('f1')+F('f2')),
    (5, obj(f1=2), F('f1') + 3),
    (8, obj(f1=5), 3 + F('f1')),
    (str(8), obj(f1=8), ExpressionWrapper(F('f1'), CharField()))
])
def test_field_combining(expected: Any, obj: Any, expression: Any) -> None:
    wrapped_expression = wrap(expression)
    output_value = wrapped_expression.as_python(obj)

    assert output_value == expected


@pytest.mark.parametrize('expected,inner_obj,expression', [
    (2, [1, 2, 3], Avg('nested')),
    (10.5, [0, 1, 3, 6], Avg('nested') + 8),
])
def test_aggregates(expected: Any, inner_obj: Any, expression: Any) -> None:
    nested_obj = obj(nested=inner_obj)
    wrapped_expression = wrap(expression)
    output_value = wrapped_expression.as_python(nested_obj)

    assert output_value == expected


@pytest.mark.parametrize('expected,obj,expression', [
    (5, dict(f1=3, f2=2), F('f1')+F('f2')),
])
def test_dictionary_resolving(expected: Any, obj: Any, expression: Any) -> None:
    wrapped_expression = wrap(expression)
    output_value = wrapped_expression.as_python(obj)

    assert output_value == expected
