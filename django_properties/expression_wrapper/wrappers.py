import operator
import re
import statistics
from typing import AnyStr, Any, Callable, Iterable

import django
from django.core.exceptions import FieldError
from django.db.models import Value, F, Avg, Aggregate, Count, Max, Min, StdDev, Sum, Variance, Func, Lookup
from django.db.models.expressions import CombinedExpression, Combinable, Col, DurationValue, \
    Random, ExpressionWrapper as DjangoExpressionWrapper
from django.db.models.functions import Cast, Coalesce, ConcatPair, Concat, Greatest, Least, Length, Lower, Now, \
    Upper
from django.db.models.lookups import Exact, IExact, GreaterThan, GreaterThanOrEqual, LessThan, LessThanOrEqual, \
    IntegerGreaterThanOrEqual, IntegerLessThan, In, Contains, IContains, StartsWith, IStartsWith, EndsWith, IEndsWith, Range, IsNull, Regex, \
    IRegex
from django.utils import timezone
from django.utils.crypto import random
from django.utils.functional import cached_property

from django_properties.expression_wrapper.base import ExpressionWrapper, FakeQuery
from django_properties.expression_wrapper.registry import register
from django_properties.resolve import get_resolver


if django.VERSION >= (2,):
    # Django 2.0 removes special Decimal lookups
    DecimalGreaterThan = object()
    DecimalGreaterThanOrEqual = object()
    DecimalLessThan = object()
    DecimalLessThanOrEqual = object()
else:
    from django.db.models.lookups import DecimalGreaterThan, DecimalGreaterThanOrEqual, DecimalLessThan, DecimalLessThanOrEqual


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


class LookupWrapper(ExpressionWrapper):
    expression = None  # type: Lookup
    op = None  # type: Callable[[Any, Any] bool]

    def as_python(self, obj: Any) -> bool:
        from . import wrap
        lhs_wrapped = wrap(self.resolved_expression.lhs)
        rhs_wrapped = self.get_wrapped_rhs()
        lhs_value = lhs_wrapped.as_python(obj)
        rhs_value = rhs_wrapped.as_python(obj)
        return self.__class__.op(lhs_value, rhs_value)

    def get_wrapped_rhs(self):
        from . import wrap
        rhs = self.resolved_expression.rhs
        for transform in self.resolved_expression.bilateral_transforms:
            rhs = transform(rhs)
        return wrap(rhs)


@register(Exact)
class ExactWrapper(LookupWrapper):
    op = operator.eq


@register(IExact)
class IExactWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        if lhs and rhs:
            return lhs.lower() == rhs.lower()
        return lhs == rhs


# TODO: python doesn't like comparing different types. investigate.

@register(GreaterThan)
@register(DecimalGreaterThan)
class GreaterThanWrapper(LookupWrapper):
    op = operator.gt


@register(GreaterThanOrEqual)
@register(IntegerGreaterThanOrEqual)
@register(DecimalGreaterThanOrEqual)
class GreaterThanOrEqualWrapper(LookupWrapper):
    op = operator.ge


@register(LessThan)
@register(IntegerLessThan)
@register(DecimalLessThan)
class LessThanWrapper(LookupWrapper):
    op = operator.lt


@register(LessThanOrEqual)
@register(DecimalLessThanOrEqual)
class LessThanOrEqualWrapper(LookupWrapper):
    op = operator.le


@register(In)
class InWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        # TODO: support querysets?
        return lhs in rhs


@register(Contains)
class ContainsWrapper(LookupWrapper):
    op = operator.contains


@register(IContains)
class IContainsWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        if lhs and rhs:
            return rhs.lower() in lhs.lower()
        return rhs in lhs


@register(StartsWith)
class StartsWithWrapper(LookupWrapper):
    op = str.startswith


@register(IStartsWith)
class IStartsWithWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        if lhs and rhs:
            return lhs.lower().startswith(rhs.lower())
        # unsure on this..
        return lhs.startswith(rhs)


@register(EndsWith)
class EndsWithWrapper(LookupWrapper):
    op = str.endswith


@register(IEndsWith)
class IEndsWithWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        return lhs.lower().endswith(rhs.lower())


@register(Range)
class RangeWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, rhs):
        return rhs[0] >= lhs <= rhs[1]


@register(IsNull)
class IsNullWrapper(LookupWrapper):
    @staticmethod
    def op(lhs, wants_null):
        if wants_null:
            return lhs is None
        return lhs is not None


@register(Regex)
class RegexWrapper(LookupWrapper):
    re_flags = 0

    @classmethod
    def op(cls, lhs, rhs):
        re_rhs = re.compile(rhs, flags=cls.re_flags)
        return bool(re_rhs.search(lhs))


@register(IRegex)
class IRegexWrapper(RegexWrapper):
    re_flags = re.IGNORECASE
