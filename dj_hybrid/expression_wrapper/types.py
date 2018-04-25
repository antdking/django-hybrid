from typing import TYPE_CHECKING, Callable, Type, Union

from typing_extensions import Protocol

from dj_hybrid.types import SupportsPython

if TYPE_CHECKING:
    from django.db.models import Expression, F, Q, Lookup


Wrapable = Union['Expression', 'F', 'Q', 'Lookup', SupportsPython]


class Wrapper(SupportsPython, Protocol):
    def __init__(self, expression: Wrapable) -> None:
        ...


TypeWrapperOrProxy = Union[Type[Wrapper], Callable[[Wrapable], Wrapper]]
