from django.db.models import F

from .base import WrapperTestBase
from .factory import FTestingFactory
from .models import FTestingModel


class Base(WrapperTestBase):
    model_class = FTestingModel
    factory = FTestingFactory


class TestAccessInt(Base):
    expression = F('int_field')
    python_value = 24
    fixture = dict(
        int_field=python_value,
    )


class TestAccessStr(Base):
    expression = F('str_field')
    python_value = 'hello'
    fixture = dict(
        str_field=python_value,
    )


class TestAccessRelation(Base):
    expression = F('related')
    python_value = 1
    fixture = dict(
        related__pk=python_value,
    )


class TestAccessRelatedInt(Base):
    expression = F('related__int_field')
    python_value = 26
    fixture = dict(
        related__int_field=python_value,
    )


class TestCombining(Base):
    expression = F('int_field') + 24
    python_value = 50
    fixture = dict(
        int_field=26
    )
