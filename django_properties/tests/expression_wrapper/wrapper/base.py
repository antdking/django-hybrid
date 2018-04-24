import pytest
from typing import ClassVar, Union, Mapping, Any, Type

from django_properties.expression_wrapper.wrap import wrap

from django.db.models import Lookup, Q, F, Expression, Model


ExpressionType = Union[Expression, F, Q, Lookup]


_UNSET = object()


@pytest.mark.django_db
class WrapperTestBase:
    expression = None  # type: ClassVar[ExpressionType]
    fixture = {}  # type: ClassVar[Mapping[str, Any]]
    model_class = None  # type: ClassVar[Type[Model]]
    python_value = _UNSET  # type: ClassVar[Any]

    def python_equivalent(self, obj: Model) -> Any:
        if self.python_value is _UNSET:
            raise NotImplementedError
        return self.python_value

    def get_expression(self) -> ExpressionType:
        return self.expression

    def get_populated_model(self) -> Model:
        return self.model_class(**self.fixture)

    def test_expression_evaluates_to_expected(self):
        expression = self.get_expression()
        wrapped_expression = wrap(expression)
        model_instance = self.get_populated_model()

        expression_outcome = wrapped_expression.as_python(model_instance)
        python_outcome = self.python_equivalent(model_instance)
        assert expression_outcome == python_outcome
