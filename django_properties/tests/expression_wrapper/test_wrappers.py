import datetime
from typing import Mapping, ClassVar, Any, Union, List, Sequence, Type

import pytest
from django_properties.expression_wrapper.wrap import wrap

from django.db.models import Model, Expression, F, Q, Lookup, Value


# The aim here is to cover a LOT of usecases for Django expressions here.
# We're looking at end-to-end testing.
# In the future, this will begin to do parity checks of python vs db operations.


pytestmark = pytest.mark.django_db


_UNSET = object()
ExpressionType = Union[Expression, F, Q, Lookup]


class WrappersStubModel(Model):
    pass


@pytest.mark.django_db
class WrapperTestBase:
    expression = None  # type: ClassVar[ExpressionType]
    fixtures = [{}]  # type: ClassVar[List[Mapping[str, Any]]]
    model_class = WrappersStubModel  # type: ClassVar[Type[Model]]
    python_value = _UNSET  # type: ClassVar[Any]

    def python_equivalent(self, obj: Model) -> Any:
        if self.python_value is _UNSET:
            raise NotImplementedError
        return self.python_value

    def get_expression(self) -> ExpressionType:
        return self.expression

    def get_populated_models(self) -> Sequence[Model]:
        return [
            self.model_class(**fixture)
            for fixture in self.fixtures
        ]

    def test_expression_evaluates_to_expected(self):
        expression = self.get_expression()
        wrapped_expression = wrap(expression)

        for model_instance in self.get_populated_models():
            expression_outcome = wrapped_expression.as_python(model_instance)
            python_outcome = self.python_equivalent(model_instance)

            assert expression_outcome == python_outcome


class TestValueInt(WrapperTestBase):
    expression = Value(28)
    python_value = 28


class TestValueStr(WrapperTestBase):
    expression = Value("some string")
    python_value = "some string"


class TestValueCombine(WrapperTestBase):
    expression = Value(28) + 2
    python_value = 30


class TestValueDuration(WrapperTestBase):
    expression = Value(datetime.date(2018, 1, 1)) + Value(datetime.timedelta(days=1))
    python_value = datetime.date(2018, 1, 2)
