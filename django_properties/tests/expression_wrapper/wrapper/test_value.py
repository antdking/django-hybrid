import datetime

import pytest

from django.db.models import Value, DateField, IntegerField, CharField, ExpressionWrapper, NullBooleanField

from .base import WrapperTestBase
from .factory import WrapperStubFactory
from .models import WrapperStubModel


class ValueTestBase(WrapperTestBase):
    model_class = WrapperStubModel
    factory = WrapperStubFactory


class TestInt(ValueTestBase):
    expression = Value(28, output_field=IntegerField())
    python_value = 28


class TestStr(ValueTestBase):
    expression = Value("some string", output_field=CharField())
    python_value = "some string"


class TestCombine(ValueTestBase):
    expression = Value(28, output_field=IntegerField()) + 2
    python_value = 30


class TestDurationExplicit(ValueTestBase):
    expression = ExpressionWrapper(
        Value(datetime.date(2018, 1, 1), output_field=DateField()) + datetime.timedelta(days=1),
        output_field=DateField(),
    )
    python_value = datetime.date(2018, 1, 2)


class TestNull(ValueTestBase):
    expression = Value(None, output_field=NullBooleanField())
    python_value = None


class TestMultipleCombines(ValueTestBase):
    expression = (Value(20, output_field=IntegerField()) + 10) + 20
    python_value = 50


class TestCasting(ValueTestBase):
    expression = Value("24", output_field=IntegerField())
    python_value = 24
