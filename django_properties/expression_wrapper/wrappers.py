import operator
import statistics
from typing import AnyStr, Any, Callable, Union

from django.core.exceptions import FieldError
from django.db.models import Value, F, Avg
from django.db.models.expressions import CombinedExpression, Combinable, Col, Ref, DurationExpression, DurationValue, \
    Random, ExpressionWrapper as DjangoExpressionWrapper, When
from django.utils.crypto import random
from django.utils.functional import cached_property

from django_properties.expression_wrapper.base import ExpressionWrapper, FakeQuery
from django_properties.expression_wrapper.registry import register
from django_properties.resolve import Resolver


class OutputFieldMixin:
    def to_value(self, value):
        try:
            field = self.resolved_expression.field
        except FieldError:
            pass  # no output_field defined
        else:
            if field:
                # TODO: decide if it's better to use get_db_converters here
                value = field.to_python(value)
        return value


@register(Value)
@register(DurationValue)
class ValueWrapper(ExpressionWrapper, OutputFieldMixin):
    expression = None  # type: Value

    def as_python(self, obj):
        value = self.resolved_expression.value
        return self.to_value(value)


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

        lhs_wrapped = wrap(self.resolved_expression.lhs)
        rhs_wrapped = wrap(self.resolved_expression.rhs)
        lhs = lhs_wrapped.as_python(obj)
        rhs = rhs_wrapped.as_python(obj)
        op = self._get_operator()
        value = op(lhs, rhs)
        return self.to_value(value)

    def _get_operator(self) -> Callable[[Any, Any], Any]:
        connector = self.resolved_expression.connector  # type: AnyStr
        op = self._connectors[connector]
        return op


@register(Col)
class ColWrapper(ExpressionWrapper):

    expression = None  # type: Col

    def as_python(self, obj: Any):
        resolver = Resolver(obj)
        return resolver.resolve(self.resolved_expression.alias)


@register(F)
def f_resolver(expression: F):
    # F doesn't behave the same as a normal expression.
    # It essentially acts an alias for either Col or Ref.
    # This will probably cause some broken parts down the road,
    # however let's actually get this running first!

    expression = expression.resolve_expression(
        FakeQuery(),
    )
    return ColWrapper(expression)


@register(Random)
class RandomWrapper(ExpressionWrapper, OutputFieldMixin):
    expression = None  # type: Random

    def as_python(self, obj: Any):
        return self.to_value(
            self.consistent_random,
        )

    @cached_property
    def consistent_random(self):
        return random.random()


@register(DjangoExpressionWrapper)
class ExpressionWrapperWrapper(ExpressionWrapper, OutputFieldMixin):
    expression = None  # type: DjangoExpressionWrapper

    def as_python(self, obj: Any):
        from . import wrap
        wrapped = wrap(self.expression.expression)
        value = wrapped.as_python(obj)
        return self.to_value(value)


class FuncMixin:
    def get_source_values(self, obj):
        from . import wrap
        for expression in self.resolved_expression.source_expressions:
            wrapped = wrap(expression)
            yield wrapped.as_python(obj)


@register(Avg)
class AvgWrapper(ExpressionWrapper, OutputFieldMixin, FuncMixin):
    expression = None  # type: Avg

    def as_python(self, obj: Any):
        # we're going to assume there's no filter in this :/
        # we're also going to assume they're only going to reference a relation

        first_value = next(self.get_source_values(obj))
        avg = statistics.mean(first_value)
        return self.to_value(avg)
