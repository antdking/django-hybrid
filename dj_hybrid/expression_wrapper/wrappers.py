import operator
import re
import statistics
from datetime import date, datetime
from typing import (
    Any,
    AnyStr,
    Callable,
    Container,
    Dict,
    Generator,
    Generic,
    Iterable,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
    Mapping, MutableMapping)
from weakref import WeakKeyDictionary

import django
from django.core.exceptions import FieldError
from django.db.models import (
    Aggregate,
    Avg,
    Count,
    F,
    Field,
    Func,
    Lookup,
    Max,
    Min,
    Model,
    Q,
    StdDev,
    Sum,
    Value,
    Variance,
    When,
)
from django.db.models.expressions import (
    Case,
    Col,
    Combinable,
    CombinedExpression,
    DurationValue,
    ExpressionWrapper as DjangoExpressionWrapper,
    Random,
)
from django.db.models.functions import Cast, Coalesce, Concat, ConcatPair, Greatest, Least, Length, Lower, Now, Upper
from django.db.models.lookups import (
    Contains,
    EndsWith,
    Exact,
    GreaterThan,
    GreaterThanOrEqual,
    IContains,
    IEndsWith,
    IExact,
    In,
    IntegerGreaterThanOrEqual,
    IntegerLessThan,
    IRegex,
    IsNull,
    IStartsWith,
    LessThan,
    LessThanOrEqual,
    Range,
    Regex,
    StartsWith,
    Transform,
)
from django.utils import timezone
from django.utils.crypto import random

from dj_hybrid.expander import expand_query
from dj_hybrid.resolve import get_resolver
from dj_hybrid.types import SupportsPython, SupportsPythonComparison
from dj_hybrid.utils import cached_property

from .base import ExpressionWrapper, FakeQuery
from .registry import register
from .wrap import wrap


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
    def to_value(self, value: Any) -> Any:
        resolved_expression = self.resolved_expression  # type: ignore
        try:
            field = resolved_expression.field  # type: Field
        except FieldError:
            pass  # no output_field defined
        else:
            if field:
                # TODO: decide if it's better to use get_db_converters here
                value = field.to_python(value)
        return value


@register(Value)
@register(DurationValue)
class ValueWrapper(ExpressionWrapper[Union[Value, DurationValue]], OutputFieldMixin):

    def as_python(self, obj: Any) -> Any:
        value = self.resolved_expression.value
        return self.to_value(value)


@register(CombinedExpression)
class CombinedExpressionWrapper(ExpressionWrapper[CombinedExpression], OutputFieldMixin):

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
    }  # type: Dict[str, Callable[[Any, Any], Any]]

    def as_python(self, obj: Any) -> Any:

        lhs_wrapped = wrap(self.resolved_expression.lhs)
        rhs_wrapped = wrap(self.resolved_expression.rhs)
        lhs = lhs_wrapped.as_python(obj)
        rhs = rhs_wrapped.as_python(obj)
        op = self._get_operator()
        value = op(lhs, rhs)
        return self.to_value(value)

    def _get_operator(self) -> Callable[[Any, Any], Any]:
        connector = self.resolved_expression.connector  # type: str
        op = self._connectors[connector]
        return op


@register(Col)
class ColWrapper(ExpressionWrapper[Col]):

    def as_python(self, obj: Any) -> Any:
        resolver = get_resolver(obj)
        resolved = resolver.resolve(self.resolved_expression.alias)

        # This behaviour might not be right, but everything I've seen suggests it..
        # We need to turn a model instance into its PK value.
        if isinstance(resolved, Model):
            return resolved.pk
        return resolved


@register(F)
def f_resolver(expression: F) -> ColWrapper:
    # F doesn't behave the same as a normal expression.
    # It essentially acts an alias for either Col or Ref.
    # This will probably cause some broken parts down the road,
    # however let's actually get this running first!

    expression = expression.resolve_expression(
        FakeQuery(),
    )
    return ColWrapper(expression)


@register(Random)
class RandomWrapper(ExpressionWrapper[Random], OutputFieldMixin):
    def __init__(self, expression) -> None:
        super().__init__(expression)
        self.instance_cache = WeakKeyDictionary()  # type: MutableMapping[Any, float]

    def as_python(self, obj: Any) -> float:
        return cast(float, self.to_value(
            self.random_for_instance(obj),
        ))

    def random_for_instance(self, obj: Any) -> float:
        try:
            return self.instance_cache[obj]
        except KeyError:
            self.instance_cache[obj] = cast(float, random.random())
            return self.instance_cache[obj]


@register(DjangoExpressionWrapper)
class ExpressionWrapperWrapper(ExpressionWrapper[DjangoExpressionWrapper], OutputFieldMixin):

    def as_python(self, obj: Any) -> Any:
        wrapped = wrap(self.expression.expression)
        value = wrapped.as_python(obj)
        return self.to_value(value)


T_Func = TypeVar('T_Func', bound=Func)


class FuncWrapper(ExpressionWrapper[Func], OutputFieldMixin, Generic[T_Func]):
    op = None  # type: Callable

    def as_python(self, obj: Any) -> Any:
        input_values = self.get_source_values(obj)
        output_value = type(self).op(*input_values)
        return self.to_value(output_value)

    def get_source_values(self, obj: Any) -> Generator[Any, None, None]:
        for expression in self.resolved_expression.source_expressions:
            wrapped = wrap(expression)
            yield wrapped.as_python(obj)


T_Aggregate = TypeVar('T_Aggregate', bound=Aggregate)


class AggregateWrapper(FuncWrapper[Aggregate], Generic[T_Aggregate]):
    op = None  # type: Callable[[Iterable[Any]], Any]


@register(Avg)
class AvgWrapper(AggregateWrapper[Avg]):
    op = statistics.mean


@register(Count)
class CountWrapper(AggregateWrapper[Count]):
    op = len


@register(Max)
class MaxWrapper(AggregateWrapper[Count]):
    op = max


@register(Min)
class MinWrapper(AggregateWrapper[Min]):
    op = min


@register(StdDev)
class StdDevWrapper(AggregateWrapper[StdDev]):
    op = statistics.stdev


@register(Sum)
class SumWrapper(AggregateWrapper[Sum]):
    op = sum


@register(Variance)
class VarianceWrapper(AggregateWrapper[Variance]):
    op = statistics.variance


Cast_T = TypeVar('Cast_T')


@register(Cast)
class CastWrapper(FuncWrapper[Cast]):
    @staticmethod
    def op(value: Cast_T) -> Cast_T:
        return value


Coalesce_T = TypeVar('Coalesce_T')


@register(Coalesce)
class CoalesceWrapper(FuncWrapper[Coalesce]):
    @staticmethod
    def op(*values: Coalesce_T) -> Optional[Coalesce_T]:
        return next(
            (value for value in values if value is not None),
            None
        )


@register(ConcatPair)
@register(Concat)
class ConcatPairWrapper(FuncWrapper[Union[Concat, ConcatPair]]):
    @staticmethod
    def op(*values: str) -> str:
        return ''.join(str(v) for v in values)


@register(Greatest)
class GreatestWrapper(FuncWrapper[Greatest]):
    op = max


@register(Least)
class LeastWrapper(FuncWrapper[Least]):
    op = min


@register(Length)
class LengthWrapper(FuncWrapper[Length]):
    op = len


T_Transform = TypeVar('T_Transform', bound=Transform)


class TransformWrapper(FuncWrapper[Transform], Generic[T_Transform]):
    op = None  # type: Callable[[Any], Any]


@register(Now)
class NowWrapper(ExpressionWrapper[Now], OutputFieldMixin):
    def __init__(self, expression):
        super().__init__(expression)
        self.now_cache = WeakKeyDictionary()  # type: MutableMapping[Any, datetime]

    def as_python(self, obj: Any) -> datetime:
        return cast(datetime, self.to_value(self.now_for_instance(obj)))

    def now_for_instance(self, obj: Any) -> datetime:
        try:
            return self.now_cache[obj]
        except KeyError:
            self.now_cache[obj] = cast(datetime, timezone.now())
            return self.now_cache[obj]


@register(Lower)
class LowerWrapper(TransformWrapper[Lower]):
    @staticmethod
    def op(value: AnyStr) -> AnyStr:
        if value:
            return value.lower()
        return value


@register(Upper)
class UpperWrapper(TransformWrapper[Upper]):
    @staticmethod
    def op(value: AnyStr) -> AnyStr:
        if value:
            return value.upper()
        return value


try:
    from django.db.models.functions import StrIndex
except ImportError:
    pass
else:
    @register(StrIndex)
    class StrIndexWrapper(FuncWrapper[StrIndex]):
        @staticmethod
        def op(string: AnyStr, lookup: AnyStr) -> int:
            try:
                value = string.index(lookup)
            except ValueError:
                value = 0
            return value


T_Lookup = TypeVar('T_Lookup', bound=Lookup)


class LookupWrapper(ExpressionWrapper[Lookup], Generic[T_Lookup]):
    op = None  # type: Callable[[Any, Any], bool]

    def as_python(self, obj: Any) -> bool:
        lhs_wrapped = wrap(self.resolved_expression.lhs)
        rhs_wrapped = self.get_wrapped_rhs()
        lhs_value = lhs_wrapped.as_python(obj)
        rhs_value = rhs_wrapped.as_python(obj)
        return type(self).op(lhs_value, rhs_value)

    def get_wrapped_rhs(self) -> SupportsPython:
        rhs = self.resolved_expression.rhs
        for transform in self.resolved_expression.bilateral_transforms:
            rhs = transform(rhs)
        return wrap(rhs)


@register(Exact)
class ExactWrapper(LookupWrapper[Exact]):
    op = operator.eq


@register(IExact)
class IExactWrapper(LookupWrapper[IExact]):
    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return lhs.lower() == rhs.lower()
        return lhs == rhs


# TODO: python doesn't like comparing different types. investigate.

@register(GreaterThan)
class GreaterThanWrapper(LookupWrapper[GreaterThan], Generic[T_Lookup]):
    op = operator.gt


@register(GreaterThanOrEqual)
@register(IntegerGreaterThanOrEqual)
class GreaterThanOrEqualWrapper(LookupWrapper[Union[GreaterThanOrEqual, IntegerGreaterThanOrEqual]], Generic[T_Lookup]):
    op = operator.ge


@register(LessThan)
@register(IntegerLessThan)
class LessThanWrapper(LookupWrapper[Union[LessThan, IntegerLessThan]], Generic[T_Lookup]):
    op = operator.lt


@register(LessThanOrEqual)
class LessThanOrEqualWrapper(LookupWrapper[LessThanOrEqual], Generic[T_Lookup]):
    op = operator.le


@register(In)
class InWrapper(LookupWrapper[In]):
    @staticmethod
    def op(lhs: Any, rhs: Container) -> bool:
        # TODO: support querysets?
        return lhs in rhs


@register(Contains)
class ContainsWrapper(LookupWrapper[Contains]):
    op = operator.contains


@register(IContains)
class IContainsWrapper(LookupWrapper[IContains]):
    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return rhs.lower() in lhs.lower()
        return rhs in lhs


@register(StartsWith)
class StartsWithWrapper(LookupWrapper[StartsWith]):
    op = str.startswith


@register(IStartsWith)
class IStartsWithWrapper(LookupWrapper[IStartsWith]):
    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return lhs.lower().startswith(rhs.lower())
        # unsure on this..
        return lhs.startswith(rhs)


@register(EndsWith)
class EndsWithWrapper(LookupWrapper[EndsWith]):
    op = str.endswith


@register(IEndsWith)
class IEndsWithWrapper(LookupWrapper[IEndsWith]):
    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        return lhs.lower().endswith(rhs.lower())


Rangeable_T = TypeVar('Rangeable_T', int, date)


@register(Range)
class RangeWrapper(LookupWrapper[Range]):

    @staticmethod
    def op(lhs: Rangeable_T, rhs: Tuple[Rangeable_T, Rangeable_T]) -> bool:
        return rhs[0] >= lhs <= rhs[1]


@register(IsNull)
class IsNullWrapper(LookupWrapper[IsNull]):
    @staticmethod
    def op(lhs: Any, wants_null: bool) -> bool:
        if wants_null:
            return lhs is None
        return lhs is not None


@register(Regex)
class RegexWrapper(LookupWrapper[Regex], Generic[T_Lookup]):
    re_flags = 0

    @classmethod
    def op(cls, lhs: str, rhs: str) -> bool:
        re_rhs = re.compile(rhs, flags=cls.re_flags)
        return bool(re_rhs.search(lhs))


@register(IRegex)
class IRegexWrapper(RegexWrapper[IRegex]):
    re_flags = re.IGNORECASE


@register(Q)
class QWrapper(ExpressionWrapper[Q]):

    def as_python(self, obj: Model) -> bool:
        expanded_query = expand_query(obj._meta.model, self.expression)
        wrapped = wrap(expanded_query)
        return cast(SupportsPythonComparison, wrapped).as_python(obj)


class ConditionNotMet(Exception):
    pass


@register(Case)
class CaseWrapper(ExpressionWrapper[Case], OutputFieldMixin):

    def as_python(self, obj: Any) -> Any:
        statement = self.resolved_expression
        for case in statement.cases:  # type: When
            wrapped_case = wrap(case)
            try:
                value = wrapped_case.as_python(obj)
                break
            except ConditionNotMet:
                pass
        else:
            value = wrap(statement.default).as_python(obj)
        return self.to_value(value)


@register(When)
class WhenWrapper(ExpressionWrapper[When]):

    def as_python(self, obj: Any) -> Any:
        statement = self.resolved_expression
        wrapped_condition = wrap(statement.condition)
        if wrapped_condition.as_python(obj):
            return wrap(statement.result).as_python(obj)
        raise ConditionNotMet


if django.VERSION < (2,):
    from django.db.models.lookups import DecimalGreaterThan, DecimalGreaterThanOrEqual, DecimalLessThan, DecimalLessThanOrEqual

    register(DecimalGreaterThan, GreaterThanWrapper[DecimalGreaterThan])
    register(DecimalGreaterThanOrEqual, GreaterThanOrEqualWrapper[DecimalGreaterThanOrEqual])
    register(DecimalLessThan, LessThanWrapper[DecimalLessThan])
    register(DecimalLessThanOrEqual, LessThanOrEqualWrapper[DecimalGreaterThanOrEqual])
