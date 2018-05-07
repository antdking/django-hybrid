from collections import Iterable
from contextlib import contextmanager
from functools import singledispatch
from itertools import combinations, chain

from typing import Union, Type, Any, Sequence, Callable, TypeVar

import django
from django.db.models import Lookup, Expression, Field
from django.db.models.expressions import F, Col
from django.utils.functional import cached_property

from dj_hybrid.expander import Not, Combineable
from dj_hybrid.expression_wrapper.base import ExpressionWrapper

ExceptionType = Union[BaseException, Type[BaseException]]


T = TypeVar('T')


_UNSET = object()


@contextmanager
def not_raises(exception: ExceptionType) -> None:
    try:
        yield
    except exception as e:
        raise AssertionError("Did raise: {}".format(e))


@singledispatch
def are_equal(*vals: T) -> bool:
    return all(
        v1 == v2
        for v1, v2 in combinations(vals, 2)
    )


@are_equal.register(list)
@are_equal.register(tuple)
def iterable_equal(*vals: T) -> bool:
    return all(
        type(v1) is type(v2)
        and len(v1) == len(v2)
        and all(
            are_equal(i1, i2)
            for i1, i2 in zip(v1, v2)
        )
        for v1, v2 in combinations(vals, 2)
    )


def compare_factory(*parameters: Sequence[str]) -> Callable[..., bool]:
    def comparer(*vals):
        # type: (*T) -> bool
        nonlocal parameters
        return all(
            bool(
                type(v1) is type(v2)
                and all(
                    are_equal(
                        getattr(v1, p, _UNSET),
                        getattr(v2, p, _UNSET),
                    )
                    for p in parameters
                )
            )
            for v1, v2 in combinations(vals, 2)
        )
    return comparer


are_equal.register(Combineable, compare_factory('lhs', 'rhs'))
are_equal.register(Lookup, compare_factory('lhs', 'rhs', 'bilateral_transforms'))
are_equal.register(Not, compare_factory('expression'))


_IGNORED_ATTRIBUTES = {
    '__dict__',
    '_constructor_args',
}

def compare_dicts(*vals: T):
    # This isn't strictly safe, however for our usecase, it's fine.
    # We need to not compare anything that's cached, as the other may also be cached
    cached_properties = set(k for k, v in type(vals[0]).__dict__.items() if isinstance(v, cached_property))
    attributes = set(chain.from_iterable(getattr(cls, '__slots__', ()) for cls in type(vals[0]).__mro__))
    if hasattr(vals[0], '__dict__'):
        check_dict = lambda v1, v2: len(set(v1.__dict__) - cached_properties) == len(set(v2.__dict__) - cached_properties)
        attributes |= set(vals[0].__dict__)
    else:
        check_dict = lambda v1, v2: True

    attributes -= cached_properties
    attributes -= _IGNORED_ATTRIBUTES
    comparer = compare_factory(*attributes)
    return all(
        type(v1) is type(v2)
        and check_dict(v1, v2)
        and comparer(v1, v2)
        for v1, v2 in combinations(vals, 2)
    )


are_equal.register(ExpressionWrapper, compare_dicts)


@are_equal.register(Field)
def compare_field(*vals: T) -> bool:
    return all(
        type(v1) is type(v2)
        and v1.deconstruct()[1] == v2.deconstruct()[1]
        for v1, v2 in combinations(vals, 2)
    )


are_equal.register(Col, compare_factory('alias', 'target', '_output_field_or_none'))


if django.VERSION < (2,):
    are_equal.register(F, compare_factory('name'))

    @are_equal.register(Expression)
    def compare_expression(*vals: T) -> bool:
        compare_output_field = compare_factory('_output_field_or_none')
        return all(
            type(v1) is type(v2)
            and compare_output_field(v1, v2)
            and compare_dicts(v1, v2)
            for v1, v2 in combinations(vals, 2)
        )
