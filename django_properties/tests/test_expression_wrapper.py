import pytest
from django.db.models import Value, F, CharField

from django_properties import expression_wrapper


def obj(**kwargs):
    return type('fakeObject', (object,), kwargs)


@pytest.mark.parametrize('expected,value', [
    ('test', Value('test')),
    (1.0, Value(1.0)),
    (str(1), Value(1, output_field=CharField())),
    (1 + 1, Value(1) + Value(1)),
    (6 % 5, Value(6) % Value(5))
])
def test_value(expected, value):
    wrapped_value = expression_wrapper.wrap(value)
    python_value = wrapped_value.as_python(None)
    assert python_value == expected


@pytest.mark.parametrize('field_name,value', [
    ('test1', 1.0),
    ('test2', 'value'),
])
def test_field(field_name, value):
    fake_obj = obj(**{field_name: value})
    field = F(field_name)
    wrapped_field = expression_wrapper.wrap(field)

    output_value = wrapped_field.as_python(fake_obj)
    assert output_value == value


@pytest.mark.parametrize('expected,obj,expression', [
    (5, obj(f1=3, f2=2), F('f1')+F('f2')),
])
def test_field_combining(expected, obj, expression):
    wrapped_expression = expression_wrapper.wrap(expression)
    output_value = wrapped_expression.as_python(obj)

    assert output_value == expected