import operator
from typing import AnyStr, Any, Callable

from django.core.exceptions import FieldError
from django.db.models import Value, F
from django.db.models.expressions import CombinedExpression, Combinable

from django_properties.expression_wrapper.base import ExpressionWrapper
from django_properties.expression_wrapper.registry import register
from django_properties.resolve import Resolver


class OutputFieldMixin:
    def to_value(self, value):
        try:
            field = self.expression.field
        except FieldError:
            pass  # no output_field defined
        else:
            if field:
                # TODO: decide if it's better to use get_db_converters here
                value = field.to_python(value)
        return value


@register(Value)
class ValueWrapper(ExpressionWrapper, OutputFieldMixin):
    expression = None  # type: Value

    def as_python(self, obj):
        value = self.expression.value
        return self.to_value(value)


@register(F)
class FieldWrapper(ExpressionWrapper):
    expression = None  # type: F

    def as_python(self, obj):
        resolver = Resolver(obj)
        return resolver.resolve(self.expression.name)


@register(CombinedExpression)
class CombinedExpressionWrapper(ExpressionWrapper, OutputFieldMixin):
    expression = None  # type: CombinedExpression

    _connectors = {
        Combinable.ADD: operator.add,
        Combinable.SUB: operator.sub,
        Combinable.MUL: operator.mul,
        Combinable.DIV: operator.truediv,
        Combinable.MOD: operator.mod,
        Combinable.BITAND: operator.and_,
        Combinable.BITOR: operator.or_,
        Combinable.BITLEFTSHIFT: operator.lshift,
        Combinable.BITRIGHTSHIFT: operator.rshift,
    }

    def as_python(self, obj):
        from . import wrap
        lhs_wrapped = wrap(self.expression.lhs)
        rhs_wrapped = wrap(self.expression.rhs)
        lhs = lhs_wrapped.as_python(obj)
        rhs = rhs_wrapped.as_python(obj)
        op = self._get_operator()
        value = op(lhs, rhs)
        return self.to_value(value)

    def _get_operator(self) -> Callable[[Any, Any], Any]:
        connector = self.expression.connector  # type: AnyStr
        op = self._connectors[connector]
        return op
