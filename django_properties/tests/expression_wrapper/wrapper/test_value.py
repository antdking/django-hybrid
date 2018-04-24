import datetime

import pytest

from django.db.models import Value, Model, DateField
from .base import WrapperTestBase


class StubModel(Model):
    pass


class ValueTestBase(WrapperTestBase):
    model_class = StubModel


class TestValueInt(ValueTestBase):
    expression = Value(28)
    python_value = 28


class TestValueStr(ValueTestBase):
    expression = Value("some string")
    python_value = "some string"


class TestValueCombine(ValueTestBase):
    expression = Value(28) + 2
    python_value = 30


class TestValueDuration(ValueTestBase):
    expression = Value(datetime.date(2018, 1, 1)) + datetime.timedelta(days=1)
    python_value = datetime.date(2018, 1, 2)

    def test_expression_evaluates_to_expected(self):
        pytest.xfail("CombinedExpression falls over due to output field detection")


class TestValueDurationExplicit(ValueTestBase):
    expression = Value(datetime.date(2018, 1, 1), output_field=DateField()) + datetime.timedelta(days=1)
    python_value = datetime.date(2018, 1, 2)
