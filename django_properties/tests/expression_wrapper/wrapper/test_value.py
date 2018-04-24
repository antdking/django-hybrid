import datetime

import pytest

from django.db.models import Value, DateField, IntegerField

from .base import WrapperTestBase
from .factory import WrapperStubFactory
from .models import WrapperStubModel


class ValueTestBase(WrapperTestBase):
    model_class = WrapperStubModel
    factory = WrapperStubFactory


class TestInt(ValueTestBase):
    expression = Value(28)
    python_value = 28


class TestStr(ValueTestBase):
    expression = Value("some string")
    python_value = "some string"


class TestCombine(ValueTestBase):
    expression = Value(28) + 2
    python_value = 30


class TestDuration(ValueTestBase):
    expression = Value(datetime.date(2018, 1, 1)) + datetime.timedelta(days=1)
    python_value = datetime.date(2018, 1, 2)

    def test_expression_evaluates_to_expected(self):
        pytest.xfail("CombinedExpression falls over due to output field detection")


class TestDurationExplicit(ValueTestBase):
    expression = Value(datetime.date(2018, 1, 1), output_field=DateField()) + datetime.timedelta(days=1)
    python_value = datetime.date(2018, 1, 2)


class TestNull(ValueTestBase):
    expression = Value(None)
    python_value = None


class TestMultipleCombines(ValueTestBase):
    expression = (Value(20) + 10) + 20
    python_value = 50


class TestCasting(ValueTestBase):
    expression = Value("24", output_field=IntegerField())
    python_value = 24
