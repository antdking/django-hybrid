import operator
import statistics
from typing import AnyStr, Any, Callable, Union, Iterable

from django.core.exceptions import FieldError
from django.db.models import Value, F, Avg, Aggregate, Count, Max, Min, StdDev, Sum, Variance, Func
from django.db.models.expressions import CombinedExpression, Combinable, Col, Ref, DurationExpression, DurationValue, \
    Random, ExpressionWrapper as DjangoExpressionWrapper, When
from django.db.models.functions import Cast, Coalesce, ConcatPair, Concat, Greatest, Least, Length, Lower, Now, \
    StrIndex, Substr, Upper
from django.utils import timezone
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


class AggregateWrapper(ExpressionWrapper, OutputFieldMixin, FuncMixin):
    op = None  # type: Callable[Iterable[Any], Any]
    expression = None  # type: Aggregate

    def as_python(self, obj: Any):
        # we're going to assume there's no filter in this :/
        # we're also going to assume they're only going to reference a relation

        first_value = next(self.get_source_values(obj))
        aggregated = self.op(first_value)
        return self.to_value(aggregated)


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


class FuncWrapper(ExpressionWrapper, OutputFieldMixin, FuncMixin):
    expression = None  # type: Func


@register(Cast)
class CastWrapper(FuncWrapper):

    def as_python(self, obj: Any):
        first_value = next(self.get_source_values(obj))
        return self.to_value(first_value)


@register(Coalesce)
class CoalesceWrapper(FuncWrapper):

    def as_python(self, obj: Any):
        for value in self.get_source_values(obj):
            if value is not None:
                return self.to_value(value)


@register(ConcatPair)
class ConcatPairWrapper(FuncWrapper):

    def as_python(self, obj: Any):
        return self.to_value(
            ''.join(
                str(v)
                for v in self.get_source_values(obj)
            )
        )


@register(Concat)
class ConcatWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        # Concat uses ConcatPair internally.
        first_value = next(self.get_source_values(obj))
        return self.to_value(first_value)


@register(Greatest)
class GreatestWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        return self.to_value(
            max(self.get_source_values(obj))
        )


@register(Least)
class LeastWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        return self.to_value(
            min(self.get_source_values(obj))
        )


@register(Length)
class LengthWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        return self.to_value(
            len(next(self.get_source_values(obj)))
        )


@register(Lower)
class LowerWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        value = self.to_value(
            next(self.get_source_values(obj))
        )
        if value:
            return value.lower()
        return value


@register(Now)
class NowWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        return self.to_value(self.consistent_now)

    @cached_property
    def consistent_now(self):
        return timezone.now()


@register(StrIndex)
class StrIndexWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        string, lookup = self.get_source_values(obj)
        try:
            value = string.index(lookup)
        except ValueError:
            value = 0
        return self.to_value(value)


@register(Upper)
class UpperWrapper(FuncWrapper):
    def as_python(self, obj: Any):
        value = self.to_value(
            next(self.get_source_values(obj))
        )
        if value:
            return value.upper()
        return value
