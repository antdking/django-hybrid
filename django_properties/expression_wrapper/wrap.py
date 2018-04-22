from typing import Type, Union

from django_properties.types import SupportsPython

from .registry import registry
from .types import TypeWrapperOrProxy, Wrapable


def wrap(expression: Wrapable) -> SupportsPython:
    """Wrap an expression so we can control how each one works within python

    Django essentially builds a chain of expressions, which is then used to build
    a chain of SQL expressions.
    We're going to use this underlying structure, and wrap the expressions so we can
    define how an expression behaves in the python domain.

    :param expression:
    :return:
    """
    if isinstance(expression, SupportsPython):
        return expression

    wrapper = get_wrapper(expression)
    return wrapper(expression)


def get_wrapper(expression: Union[Wrapable, Type[Wrapable]]) -> TypeWrapperOrProxy:
    if not isinstance(expression, type):
        expression = type(expression)
    return registry.get(expression)
