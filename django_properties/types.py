from typing import Any

from typing_extensions import Protocol, runtime


@runtime
class SupportsPython(Protocol):
    def as_python(self, obj: Any) -> Any: ...


class SupportsPythonComparison(SupportsPython, Protocol):
    def as_python(self, obj: Any) -> bool: ...
