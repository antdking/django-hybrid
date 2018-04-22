from typing import Union, TYPE_CHECKING, ClassVar, Callable, Type

from typing_extensions import Protocol

from django_properties.types import SupportsPython

if TYPE_CHECKING:
    from django.db.models import Expression, F, Q, Lookup


Wrapable = Union['Expression', 'F', 'Q', 'Lookup']


class Wrapper(SupportsPython, Protocol):
    resolve_expression = None  # type: ClassVar[Wrapable]

    def __init__(self, expression: Wrapable) -> None: ...


TypeWrapperOrProxy = Union[Type[Wrapper], Callable[[Wrapable], Wrapper]]
