import operator
import statistics
from typing import AnyStr, Any, Callable, Iterable

from django.core.exceptions import FieldError
from django.db.models import Value, F, Avg, Aggregate, Count, Max, Min, StdDev, Sum, Variance, Func
from django.db.models.expressions import CombinedExpression, Combinable, Col, DurationValue, \
    Random, ExpressionWrapper as DjangoExpressionWrapper
from django.db.models.functions import Cast, Coalesce, ConcatPair, Concat, Greatest, Least, Length, Lower, Now, \
    Upper
from django.utils import timezone
from django.utils.crypto import random
from django.utils.functional import cached_property

from django_properties.expression_wrapper.base import ExpressionWrapper, FakeQuery
from django_properties.expression_wrapper.registry import register
from django_properties.resolve import get_resolver


"""
There are some main types of expressions in Django:
  - Expressions
    This is the base. It acts as a template for Values and Refs
  - Func
    This can be any function call. It defines how many arguments there are, and
    what function is to be called.
    - Aggregate
      This is a subclass of Func. It takes an arbitrary amount of arguments, however
      there is nothing really special about it.
    - Transform
      This is a subclass of Func. They take only one argument, and are commonly used
      in queries.
  - Lookup
    These are not technically expressions.
    They take 2 expressions, and should return True or False.
    The first expression should point at a field, the latter can be anything.
  - References
    These point at fields. They're not technically Expressions, but they behave
    the same.
  - Queries
    A query (or a `Q` object) is actually just syntactical sugar. It wraps a field
    reference, transforms, and a lookup.
    It is used in filters, as well as control flows.
  - Control Flows
    Django uses `Case` and `When` to supply control flows. this is essentially chained
    If statements.
"""


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
        resolver = get_resolver(obj)
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


class FuncWrapper(ExpressionWrapper, OutputFieldMixin, FuncMixin):
    op = None  # type: Callable
    expression = None  # type: Func

    def as_python(self, obj: Any):
        input_values = self.get_source_values(obj)
        output_value = self.__class__.op(*input_values)
        return self.to_value(output_value)


class AggregateWrapper(FuncWrapper):
    op = None  # type: Callable[Iterable[Any], Any]
    expression = None  # type: Aggregate


@register(Avg)
class AvgWrapper(AggregateWrapper):
    op = statistics.mean


@register(Count)
class CountWrapper(AggregateWrapper):
    op = len


@register(Max)
class MaxWrapper(AggregateWrapper):
    op = max


@register(Min)
class MinWrapper(AggregateWrapper):
    op = min


@register(StdDev)
class StdDevWrapper(AggregateWrapper):
    op = statistics.stdev


@register(Sum)
class SumWrapper(AggregateWrapper):
    op = sum


@register(Variance)
class VarianceWrapper(AggregateWrapper):
    op = statistics.variance


@register(Cast)
class CastWrapper(FuncWrapper):
    @staticmethod
    def op(value):
        return value


@register(Coalesce)
class CoalesceWrapper(FuncWrapper):
    @staticmethod
    def op(*values):
        return next(
            (value for value in values if value is not None),
            None
        )


@register(ConcatPair)
@register(Concat)
class ConcatPairWrapper(FuncWrapper):
    @staticmethod
    def op(*values):
        return ''.join(str(v) for v in values)


@register(Greatest)
class GreatestWrapper(FuncWrapper):
    op = max


@register(Least)
class LeastWrapper(FuncWrapper):
    op = min


@register(Length)
class LengthWrapper(FuncWrapper):
    op = len


class TransformWrapper(FuncWrapper):
    op = None  # type: Callable[Any, Any]


@register(Now)
class NowWrapper(ExpressionWrapper, OutputFieldMixin):
    def as_python(self, obj: Any):
        return self.to_value(self.consistent_now)

    @cached_property
    def consistent_now(self):
        return timezone.now()


@register(Lower)
class LowerWrapper(TransformWrapper):
    @staticmethod
    def op(value):
        if value:
            return value.lower()
        return value


@register(Upper)
class UpperWrapper(TransformWrapper):
    @staticmethod
    def op(value):
        if value:
            return value.upper()
        return value


try:
    from django.db.models.functions import StrIndex
except ImportError:
    pass
else:
    @register(StrIndex)
    class StrIndexWrapper(FuncWrapper):
        @staticmethod
        def op(string, lookup):
            try:
                value = string.index(lookup)
            except ValueError:
                value = 0
            return value



