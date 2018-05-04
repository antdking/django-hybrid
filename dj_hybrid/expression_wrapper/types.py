from typing import TYPE_CHECKING, Callable, Type, Union, Any

from typing_extensions import Protocol

from dj_hybrid.types import SupportsPython, Slots

if TYPE_CHECKING:
    from django.db.models.sql import Query

Wrapable = Union['SupportsSQL', 'SupportsResolving', SupportsPython]


class SupportsSQL(Protocol):
    __slots__ = ()  # type: Slots

    def as_sql(self, compiler: Any, connection: Any) -> str:
        ...


class SupportsResolving(Protocol):
    __slots__ = ()  # type: Slots

    def resolve_expression(self, query: 'Query') -> Union['SupportsSQL', 'SupportsResolving']:
        ...


class Wrapper(SupportsPython, Protocol):
    __slots__ = ()  # type: Slots

    def __init__(self, expression: Wrapable) -> None:
        ...


TypeWrapperOrProxy = Union[Type[Wrapper], Callable[[Wrapable], Wrapper]]
