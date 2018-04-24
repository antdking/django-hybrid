import factory
from typing import ClassVar, Union, Mapping, Any, Type

import pytest

from django_properties.expression_wrapper.wrap import wrap

from django.db.models import Lookup, Q, F, Expression, Model


ExpressionType = Union[Expression, F, Q, Lookup]


_UNSET = object()


@pytest.mark.django_db(transaction=True)
class WrapperTestBase:
    factory = None  # type: ClassVar[Type[factory.Factory]]
    model_class = None  # type: ClassVar[Type[Model]]
    fixture = {}  # type: ClassVar[Mapping[str, Any]]

    python_value = _UNSET  # type: ClassVar[Any]
    expression = None  # type: ClassVar[ExpressionType]

    def python_equivalent(self, obj: Model) -> Any:
        if self.python_value is _UNSET:
            raise NotImplementedError
        return self.python_value

    def get_expression(self) -> ExpressionType:
        return self.expression

    def get_populated_model(self) -> Model:
        if not hasattr(self, '__model_instance'):
            self.__model_instance = self.factory(**self.fixture)
        return self.__model_instance

    def test_expression_evaluates_to_expected(self):
        expression = self.get_expression()
        wrapped_expression = wrap(expression)
        model_instance = self.get_populated_model()

        expression_outcome = wrapped_expression.as_python(model_instance)
        python_outcome = self.python_equivalent(model_instance)
        assert expression_outcome == python_outcome
