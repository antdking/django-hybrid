from typing import TypeVar, Union, Type, Callable

from django.db.models import Expression, F, Lookup, Q

from . import wrappers  # noqa
from .registry import registry


T_Expression = Union[Expression, F, Q, Lookup]
T_Wrappers = Union[Type[wrappers.ExpressionWrapper], Callable[[T_Expression], wrappers.ExpressionWrapper]]


def wrap(expression: T_Expression) -> wrappers.ExpressionWrapper:
    """Wrap an expression so we can control how each one works within python

    Django essentially builds a chain of expressions, which is then used to build
    a chain of SQL expressions.
    We're going to use this underlying structure, and wrap the expressions so we can
    define how an expression behaves in the python domain.

    :param expression:
    :return:
    """
    wrapper = get_wrapper(expression)
    return wrapper(expression)


def get_wrapper(expression: Union[T_Expression, Type[T_Expression]]) -> T_Wrappers:
    if not isinstance(expression, type):
        expression = type(expression)
    return registry.get(expression)
