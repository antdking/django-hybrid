import decimal
import operator
import re
import statistics
from contextlib import suppress
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
    MutableMapping, ClassVar)
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
    Expression)
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
from django.utils.dateparse import parse_date, parse_datetime, parse_duration, parse_time
from django.utils.encoding import force_bytes, force_text

from dj_hybrid.expander import expand_query
from dj_hybrid.expression_wrapper.convert import get_connection, get_db
from dj_hybrid.expression_wrapper.types import SupportsResolving
from dj_hybrid.resolve import get_resolver
from dj_hybrid.types import SupportsPython, SupportsPythonComparison, Slots

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

_UNSET = object()


def _get_output_field(expression: Expression) -> Optional[Field]:
    with suppress(FieldError):
        return expression.output_field


@register(Value)
@register(DurationValue)
class ValueWrapper(ExpressionWrapper[Union[Value, DurationValue]]):
    __slots__ = (
        '_resolved_value',
    )  # type: Slots

    def __init__(self, expression: Union[Value, DurationValue]) -> None:
        super().__init__(expression)
        self._resolved_value = _UNSET  # type: Any

    def as_python(self, obj: Any) -> Any:
        return self.get_value()

    def get_value(self) -> Any:
        if self._resolved_value is not _UNSET:
            return self._resolved_value
        return self.expression.value

    def resolve_expression(self, query: FakeQuery) -> 'ValueWrapper':
        c = cast(ValueWrapper, super().resolve_expression(query))
        value = c.expression.value
        output_field = _get_output_field(c.expression)
        if output_field:
            connection = get_connection(get_db(query.model))
            value = output_field.get_db_prep_value(value, connection)
        c._resolved_value = value
        return c


@register(CombinedExpression)
class CombinedExpressionWrapper(ExpressionWrapper[CombinedExpression]):
    __slots__ = ()  # type: Slots

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

        lhs_wrapped = wrap(self.expression.lhs)
        rhs_wrapped = wrap(self.expression.rhs)
        lhs = lhs_wrapped.as_python(obj)
        rhs = rhs_wrapped.as_python(obj)
        op = self._get_operator()
        value = op(lhs, rhs)
        return value

    def _get_operator(self) -> Callable[[Any, Any], Any]:
        connector = self.expression.connector  # type: str
        op = self._connectors[connector]
        return op


@register(Col)
class ColWrapper(ExpressionWrapper[Col]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        resolver = get_resolver(obj)
        resolved = resolver.resolve(self.expression.alias)

        # This behaviour might not be right, but everything I've seen suggests it..
        # We need to turn a model instance into its PK value.
        if isinstance(resolved, Model):
            return resolved.pk
        return resolved


@register(F)
class FWrapper(ExpressionWrapper[F]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        resolver = get_resolver(obj)
        resolved = resolver.resolve(self.expression.name)
        if isinstance(resolved, Model):
            return resolved.pk
        return resolved

    def resolve_expression(self, query: FakeQuery) -> SupportsPython:
        new_expression = self.expression.resolve_expression(query)
        wrapped = wrap(new_expression)
        if isinstance(wrapped, SupportsResolving):
            wrapped = wrapped.resolve_expression(query)
        return wrapped


@register(Random)
class RandomWrapper(ExpressionWrapper[Random]):
    __slots__ = (
        'instance_cache',
    )  # type: Slots

    def __init__(self, expression: Random) -> None:
        super().__init__(expression)
        self.instance_cache = WeakKeyDictionary()  # type: MutableMapping[Any, float]

    def as_python(self, obj: Any) -> float:
        return self.random_for_instance(obj)

    def random_for_instance(self, obj: Any) -> float:
        try:
            return self.instance_cache[obj]
        except KeyError:
            self.instance_cache[obj] = cast(float, random.random())
            return self.instance_cache[obj]


@register(DjangoExpressionWrapper)
class ExpressionWrapperWrapper(ExpressionWrapper[DjangoExpressionWrapper]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        wrapped = wrap(self.expression.expression)
        value = wrapped.as_python(obj)
        return value


T_Func = TypeVar('T_Func', bound=Func)


class FuncWrapper(ExpressionWrapper[Func], Generic[T_Func]):
    __slots__ = ()  # type: Slots
    op = None  # type: ClassVar[Callable]

    def as_python(self, obj: Any) -> Any:
        input_values = self.get_source_values(obj)
        op = self.get_op()
        output_value = op(*input_values)
        return output_value

    def get_source_values(self, obj: Any) -> Generator[Any, None, None]:
        for expression in self.expression.source_expressions:
            wrapped = wrap(expression)
            yield wrapped.as_python(obj)

    def get_op(self) -> Callable:
        return type(self).op


T_Aggregate = TypeVar('T_Aggregate', bound=Aggregate)


class AggregateWrapper(FuncWrapper[Aggregate], Generic[T_Aggregate]):
    __slots__ = ()  # type: Slots
    op = None  # type: ClassVar[Callable[[Iterable[Any]], Any]]


@register(Avg)
class AvgWrapper(AggregateWrapper[Avg]):
    __slots__ = ()  # type: Slots
    op = statistics.mean


@register(Count)
class CountWrapper(AggregateWrapper[Count]):
    __slots__ = ()  # type: Slots
    op = len


@register(Max)
class MaxWrapper(AggregateWrapper[Count]):
    __slots__ = ()  # type: Slots
    op = max


@register(Min)
class MinWrapper(AggregateWrapper[Min]):
    __slots__ = ()  # type: Slots
    op = min


@register(StdDev)
class StdDevWrapper(AggregateWrapper[StdDev]):
    __slots__ = ()  # type: Slots
    op = statistics.stdev


@register(Sum)
class SumWrapper(AggregateWrapper[Sum]):
    __slots__ = ()  # type: Slots
    op = sum


@register(Variance)
class VarianceWrapper(AggregateWrapper[Variance]):
    __slots__ = ()  # type: Slots
    op = statistics.variance


Cast_T = TypeVar('Cast_T')


@register(Cast)
class CastWrapper(FuncWrapper[Cast]):
    __slots__ = ()  # type: Slots

    _ops = {
        'AutoField': int,
        'BigAutoField': int,
        'BinaryField': force_bytes,
        'BooleanField': bool,
        'CharField': force_text,
        'DateField': parse_date,
        'DateTimeField': parse_datetime,
        'DecimalField': decimal.Decimal,
        'DurationField': parse_duration,
        'FileField': force_text,
        'FilePathField': force_text,
        'FloatField': float,
        'IntegerField': int,
        'BigIntegerField': int,
        'IPAddressField': force_text,
        'GenericIPAddressField': force_text,
        'NullBooleanField': bool,  # TODO: make this nullable
        'OneToOneField': int,
        'PositiveIntegerField': int,
        'PositiveSmallIntegerField': int,
        'SlugField': force_text,
        'SmallIntegerField': int,
        'TextField': force_text,
        'TimeField': parse_time,
        'UUIDField': str,
    }  # type: Dict[str, Callable[[Any], Any]]

    def get_op(self) -> Callable[[Any], Any]:
        output_field = _get_output_field(self.expression)
        if output_field:
            internal_type = output_field.get_internal_type()
        else:
            internal_type = None
        return self._ops.get(internal_type, lambda x: x)


Coalesce_T = TypeVar('Coalesce_T')


@register(Coalesce)
class CoalesceWrapper(FuncWrapper[Coalesce]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(*values: Coalesce_T) -> Optional[Coalesce_T]:
        return next(
            (value for value in values if value is not None),
            None
        )


@register(ConcatPair)
@register(Concat)
class ConcatPairWrapper(FuncWrapper[Union[Concat, ConcatPair]]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(*values: str) -> str:
        return ''.join(str(v) for v in values)


@register(Greatest)
class GreatestWrapper(FuncWrapper[Greatest]):
    __slots__ = ()  # type: Slots
    op = max


@register(Least)
class LeastWrapper(FuncWrapper[Least]):
    __slots__ = ()  # type: Slots
    op = min


@register(Length)
class LengthWrapper(FuncWrapper[Length]):
    __slots__ = ()  # type: Slots
    op = len


T_Transform = TypeVar('T_Transform', bound=Transform)


class TransformWrapper(FuncWrapper[Transform], Generic[T_Transform]):
    __slots__ = ()  # type: Slots
    op = None  # type: ClassVar[Callable[[Any], Any]]


@register(Now)
class NowWrapper(ExpressionWrapper[Now]):
    __slots__ = (
        'now_cache',
    )  # type: Slots

    def __init__(self, expression: Now) -> None:
        super().__init__(expression)
        self.now_cache = WeakKeyDictionary()  # type: MutableMapping[Any, datetime]

    def as_python(self, obj: Any) -> datetime:
        return self.now_for_instance(obj)

    def now_for_instance(self, obj: Any) -> datetime:
        try:
            return self.now_cache[obj]
        except KeyError:
            self.now_cache[obj] = cast(datetime, timezone.now())
            return self.now_cache[obj]


@register(Lower)
class LowerWrapper(TransformWrapper[Lower]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(value: AnyStr) -> AnyStr:
        if value:
            return value.lower()
        return value


@register(Upper)
class UpperWrapper(TransformWrapper[Upper]):
    __slots__ = ()  # type: Slots

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
        __slots__ = ()  # type: Slots

        @staticmethod
        def op(string: AnyStr, lookup: AnyStr) -> int:
            try:
                value = string.index(lookup)
            except ValueError:
                value = 0
            return value


T_Lookup = TypeVar('T_Lookup', bound=Lookup)


class LookupWrapper(ExpressionWrapper[Lookup], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    op = None  # type: Callable[[Any, Any], bool]

    def as_python(self, obj: Any) -> bool:
        lhs_wrapped = wrap(self.expression.lhs)
        rhs_wrapped = self.get_wrapped_rhs()
        lhs_value = lhs_wrapped.as_python(obj)
        rhs_value = rhs_wrapped.as_python(obj)
        return type(self).op(lhs_value, rhs_value)

    def get_wrapped_rhs(self) -> SupportsPython:
        rhs = self.expression.rhs
        for transform in self.expression.bilateral_transforms:
            rhs = transform(rhs)
        return wrap(rhs)


@register(Exact)
class ExactWrapper(LookupWrapper[Exact]):
    __slots__ = ()  # type: Slots
    op = operator.eq


@register(IExact)
class IExactWrapper(LookupWrapper[IExact]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return lhs.lower() == rhs.lower()
        return lhs == rhs


# TODO: python doesn't like comparing different types. investigate.

@register(GreaterThan)
class GreaterThanWrapper(LookupWrapper[GreaterThan], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    op = operator.gt


@register(GreaterThanOrEqual)
@register(IntegerGreaterThanOrEqual)
class GreaterThanOrEqualWrapper(LookupWrapper[Union[GreaterThanOrEqual, IntegerGreaterThanOrEqual]], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    op = operator.ge


@register(LessThan)
@register(IntegerLessThan)
class LessThanWrapper(LookupWrapper[Union[LessThan, IntegerLessThan]], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    op = operator.lt


@register(LessThanOrEqual)
class LessThanOrEqualWrapper(LookupWrapper[LessThanOrEqual], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    op = operator.le


@register(In)
class InWrapper(LookupWrapper[In]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: Any, rhs: Container) -> bool:
        # TODO: support querysets?
        return lhs in rhs


@register(Contains)
class ContainsWrapper(LookupWrapper[Contains]):
    __slots__ = ()  # type: Slots
    op = operator.contains


@register(IContains)
class IContainsWrapper(LookupWrapper[IContains]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return rhs.lower() in lhs.lower()
        return rhs in lhs


@register(StartsWith)
class StartsWithWrapper(LookupWrapper[StartsWith]):
    __slots__ = ()  # type: Slots
    op = str.startswith


@register(IStartsWith)
class IStartsWithWrapper(LookupWrapper[IStartsWith]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        if lhs and rhs:
            return lhs.lower().startswith(rhs.lower())
        # unsure on this..
        return lhs.startswith(rhs)


@register(EndsWith)
class EndsWithWrapper(LookupWrapper[EndsWith]):
    __slots__ = ()  # type: Slots
    op = str.endswith


@register(IEndsWith)
class IEndsWithWrapper(LookupWrapper[IEndsWith]):
    __slots__ = ()  # type: Slots
    @staticmethod
    def op(lhs: AnyStr, rhs: AnyStr) -> bool:
        return lhs.lower().endswith(rhs.lower())


Rangeable_T = TypeVar('Rangeable_T', int, date)


@register(Range)
class RangeWrapper(LookupWrapper[Range]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: Rangeable_T, rhs: Tuple[Rangeable_T, Rangeable_T]) -> bool:
        return rhs[0] >= lhs <= rhs[1]


@register(IsNull)
class IsNullWrapper(LookupWrapper[IsNull]):
    __slots__ = ()  # type: Slots

    @staticmethod
    def op(lhs: Any, wants_null: bool) -> bool:
        if wants_null:
            return lhs is None
        return lhs is not None


@register(Regex)
class RegexWrapper(LookupWrapper[Regex], Generic[T_Lookup]):
    __slots__ = ()  # type: Slots
    re_flags = 0

    @classmethod
    def op(cls, lhs: str, rhs: str) -> bool:
        re_rhs = re.compile(rhs, flags=cls.re_flags)
        return bool(re_rhs.search(lhs))


@register(IRegex)
class IRegexWrapper(RegexWrapper[IRegex]):
    __slots__ = ()  # type: Slots
    re_flags = re.IGNORECASE


@register(Q)
class QWrapper(ExpressionWrapper[Q]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Model) -> bool:
        expanded_query = expand_query(obj._meta.model, self.expression)
        wrapped = wrap(expanded_query)
        return cast(SupportsPythonComparison, wrapped).as_python(obj)


class ConditionNotMet(Exception):
    pass


@register(Case)
class CaseWrapper(ExpressionWrapper[Case]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        statement = self.expression
        for case in statement.cases:  # type: When
            wrapped_case = wrap(case)
            try:
                value = wrapped_case.as_python(obj)
                break
            except ConditionNotMet:
                pass
        else:
            value = wrap(statement.default).as_python(obj)
        return value


@register(When)
class WhenWrapper(ExpressionWrapper[When]):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        statement = self.expression
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
