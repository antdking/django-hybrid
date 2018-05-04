from typing import Any, Tuple, Union

from typing_extensions import Protocol, runtime

Slots = Union[str, Tuple[str, ...]]


@runtime
class SupportsPython(Protocol):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> Any:
        ...


class SupportsPythonComparison(SupportsPython, Protocol):
    __slots__ = ()  # type: Slots

    def as_python(self, obj: Any) -> bool:
        ...
