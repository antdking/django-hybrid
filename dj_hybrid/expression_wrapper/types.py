from typing import TYPE_CHECKING, Callable, Type, Union, Any, List, TypeVar

from typing_extensions import Protocol, runtime

from dj_hybrid.types import SupportsPython, Slots

if TYPE_CHECKING:
    from dj_hybrid.expression_wrapper.base import FakeQuery
    from django.db.models import Field
    from django.db.models.sql import Query

Wrapable = Any
_T_C = TypeVar('_T_C')


class SupportsSQL(Protocol):
    __slots__ = ()  # type: Slots

    def as_sql(self, compiler: Any, connection: Any) -> str:
        ...


@runtime
class SupportsResolving(Protocol):
    __slots__ = ()  # type: Slots

    def resolve_expression(self, query: Union['Query', 'FakeQuery']) -> Wrapable:
        ...


@runtime
class SupportsConversion(Protocol):
    __slots__ = ()  # type: Slots

    @property
    def output_field(self) -> 'Field':
        ...

    def get_db_converters(self, connection: Any) -> List[Callable]:
        ...


@runtime
class SupportsCopy(Protocol):
    __slots__ = ()  # type: Slots

    def copy(self: _T_C) -> _T_C:
        ...


@runtime
class Wrapper(SupportsPython, Protocol):
    __slots__ = ()  # type: Slots

    def __init__(self, expression: Wrapable) -> None:
        ...

    def get_for_conversion(self) -> SupportsConversion:
        ...


TypeWrapperOrProxy = Union[Type[Wrapper], Callable[[Wrapable], Wrapper]]
